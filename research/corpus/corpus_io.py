"""One transport policy for every freezer, instead of four undocumented ones.

The corpus is frozen by several scripts because the datasets arrive by
genuinely different routes: the datasets-server rows API, the Hugging Face
tree listing, a local JSONL the server cannot page, and a parquet mirror.
Those differences are real and the freezers keep them.

What was not real was the rest. Each script had grown its own retry loop,
and by the fourth they read 7 attempts at a 300s timeout backing off in
steps of 8 seconds, 6 at 120 backing off by 4, 6 at 120 backing off by 5,
and 6 at 180 backing off by 6. No script said why its numbers differed from
its neighbour's, because the numbers did not differ for a reason: each was
typed once and copied. Four undocumented decisions are worse than one
documented decision, so this is the one.

The policy is the most patient of the four, because the cost of being wrong
in the other direction is a half-finished freeze after an hour of fetching,
and a slower ceiling costs nothing on a request that succeeds.
"""

from __future__ import annotations

import json
import pathlib
import time
import urllib.error
import urllib.request

#: Attempts, socket timeout, and the multiplier on linear backoff. Chosen as
#: the most generous of the four policies this replaced: a large page of rows
#: legitimately takes minutes, and a small tree listing is not harmed by
#: being allowed to.
ATTEMPTS = 7
TIMEOUT_SECONDS = 300
BACKOFF_SECONDS = 8


def http_get(url: str, *, raw: bool = False, missing_ok: bool = False):
    """Fetch and decode, retrying transient failures.

    `missing_ok` turns a 404 into None, which is how the tree-walking
    freezers ask whether an optional sidecar exists. Every other failure is
    retried and then raised: a freezer that swallowed an error would write a
    short freeze that looks complete.
    """
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                payload = response.read()
                return payload if raw else json.loads(payload)
        except urllib.error.HTTPError as error:
            if error.code == 404 and missing_ok:
                return None
            last = error
            time.sleep(BACKOFF_SECONDS * (attempt + 1))
        except Exception as error:
            last = error
            time.sleep(BACKOFF_SECONDS * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def dataset_revision(dataset: str, ref: str = "") -> str:
    """The commit a freeze is pinned to. Recorded in the frozen document so
    the hashes are re-derivable by anyone at the same revision."""
    url = f"https://huggingface.co/api/datasets/{dataset}"
    if ref:
        url += f"/revision/{ref}"
    return http_get(url)["sha"]


def write_frozen(path: pathlib.Path, document: dict) -> None:
    """Sorted and one-space-indented, so a re-freeze produces a diff a human
    can read rather than a reordering. Written to a temporary file and
    renamed, because a freeze interrupted midway through a write leaves a
    truncated JSON file that every later run treats as evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
