"""Freeze content-free audit evidence from a public trajectory dataset.

One command per dataset, network required once, everything downstream offline:

    python3 research/corpus/freeze.py coderforge
    python3 research/corpus/freeze.py jetbrains

Per row it keeps identifiers, outcome fields, step counts, SHA-256 hashes of
the content it refuses to copy, and — where the dataset ships raw test logs
beside graded-test lists — the re-adjudication verdict those logs support.
No prompts, no responses, no patches, no logs are stored.

Rows come from the Hugging Face datasets-server, which serves the dataset's
current revision and takes no revision parameter. That would be an unpinned
measurement, so the freeze brackets the fetch: it records the repository's
commit SHA before the first page and refuses to write anything if the SHA
after the last page differs. The frozen file then names the exact commit all
of its rows came from.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

from parse_tests import readjudicate  # type: ignore[import-not-found]

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"

_ROWS_API = "https://datasets-server.huggingface.co/rows"
_INFO_API = "https://huggingface.co/api/datasets"


def _get(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                return json.load(response)
        except Exception as error:  # retried, then re-raised
            last = error
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def _sha_now(dataset: str) -> str:
    return _get(f"{_INFO_API}/{urllib.parse.quote(dataset, safe='/')}")["sha"]


def _rows(dataset: str, config: str, split: str) -> list[dict]:
    fetched: list[dict] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {"dataset": dataset, "config": config, "split": split,
             "offset": offset, "length": 100}
        )
        page = _get(f"{_ROWS_API}?{query}")
        for wrapper in page["rows"]:
            if wrapper.get("truncated_cells"):
                raise RuntimeError(
                    f"row {offset} truncated cells {wrapper['truncated_cells']}: "
                    "a hash of a truncated cell would be a hash of nothing"
                )
            fetched.append(wrapper["row"])
        offset += len(page["rows"])
        if offset >= page.get("num_rows_total", 0) or not page["rows"]:
            return fetched


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _coderforge(row: dict) -> dict:
    ds = json.loads(row["ds"]) if isinstance(row.get("ds"), str) else (row.get("ds") or {})
    f2p, p2p = ds.get("FAIL_TO_PASS"), ds.get("PASS_TO_PASS")
    if isinstance(f2p, str):
        f2p = json.loads(f2p)
    if isinstance(p2p, str):
        p2p = json.loads(p2p)
    log = row.get("test_output") or ""
    frozen = {
        "id": row.get("trajectory_id"),
        "instance_id": ds.get("instance_id"),
        "outcome": row.get("reward"),
        "steps": row.get("num_steps"),
        "transcript_sha256": _sha256(_canonical(row.get("messages"))),
        "patch_sha256": _sha256(row.get("output_patch") or ""),
        "log_sha256": _sha256(log),
        "log_bytes": len(log.encode()),
    }
    if f2p is not None and p2p is not None and log:
        frozen["graded"] = {
            "f2p_n": len(f2p),
            "p2p_n": len(p2p),
            **readjudicate(log, f2p, p2p),
        }
    return frozen


def _jetbrains(row: dict) -> dict:
    return {
        "id": row.get("instance_id"),
        "instance_id": row.get("instance_id"),
        "outcome": row.get("resolved"),
        "cross": row.get("exit_status"),
        "steps": row.get("n_turns"),
        "transcript_sha256": _sha256(_canonical(row.get("messages"))),
    }


SPECS = {
    "coderforge": {
        "dataset": (
            "togethercomputer/"
            "CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories"
        ),
        "config": "trajectory",
        "split": "train",
        "expected_rows": 500,
        "outcome_field": "reward",
        "cross_field": None,
        "extract": _coderforge,
        "license": "apache-2.0",
    },
    "jetbrains": {
        "dataset": "JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified",
        "config": "default",
        "split": "train",
        "expected_rows": 1785,
        "outcome_field": "resolved",
        "cross_field": "exit_status",
        "extract": _jetbrains,
        "license": "apache-2.0",
    },
}


def freeze(slug: str) -> pathlib.Path:
    spec = SPECS[slug]
    sha_before = _sha_now(spec["dataset"])
    rows = _rows(spec["dataset"], spec["config"], spec["split"])
    sha_after = _sha_now(spec["dataset"])
    if sha_before != sha_after:
        raise RuntimeError(
            f"{spec['dataset']} moved {sha_before[:8]} -> {sha_after[:8]} "
            "during the fetch; the pages are not one snapshot. Re-run."
        )
    if len(rows) != spec["expected_rows"]:
        raise RuntimeError(
            f"{spec['dataset']}: fetched {len(rows)} rows, expected "
            f"{spec['expected_rows']}. A partial arm is a sample presented "
            "as a census; refusing to freeze it."
        )
    document = {
        "dataset": spec["dataset"],
        "revision": sha_before,
        "config": spec["config"],
        "split": spec["split"],
        "outcome_field": spec["outcome_field"],
        "cross_field": spec["cross_field"],
        "license": spec["license"],
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fetched_via": "datasets-server /rows, revision bracketed by repo SHA",
        "rows": [spec["extract"](row) for row in rows],
    }
    FROZEN.mkdir(exist_ok=True)
    path = FROZEN / f"{slug}.json"
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in SPECS:
        print(f"usage: freeze.py {{{'|'.join(SPECS)}}}", file=sys.stderr)
        return 2
    path = freeze(argv[1])
    print(f"froze {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    sys.exit(main(sys.argv))
