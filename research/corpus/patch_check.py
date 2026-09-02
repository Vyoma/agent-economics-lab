"""Establish whether the cross-repo shared patches are trivial, row by row.

The frozen SWE-smith evidence shows 266 non-empty patch contents that each
appear verbatim under instances from two or more different repositories. That
is either a misaligned column or nothing: a one-line whitespace diff could
legitimately be produced for two unrelated repositories, and the freeze kept
hashes, not lengths, so the frozen evidence alone cannot tell those apart.
An earlier draft of this corpus nearly published 186 parser artifacts as
findings; this check exists so a hash coincidence is not published as one.

For a deterministic sample of the cross-repo groups (hash-ranked, so two
people running this check the same groups), every involved row is re-fetched
by its frozen position and reduced to content-free facts: the patch's byte
length, whether it parses as a unified diff, the number of files it touches,
and whether any touched path's top-level component plausibly belongs to the
instance's repository (matching the repo name or its underscore/dash
variants). The patch bytes themselves are hashed against the frozen hash and
discarded.

A sampled row whose patch matches its frozen hash, exceeds a trivial length,
and touches paths foreign to its instance's repository is a verified
misalignment. A row that cannot be fetched or whose hash does not match is a
failure of this check, never a silent skip.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
OUT = FROZEN / "swesmith-patch-check.json"

DATASET = "SWE-bench/SWE-smith-trajectories"
SLUGS = ("swesmith-tool", "swesmith-xml", "swesmith-ticks")
_ROWS_API = "https://datasets-server.huggingface.co/rows"

#: Below this, a byte-identical diff across repositories is unremarkable.
TRIVIAL_BYTES = 200


def _get(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                return json.load(response)
        except Exception as error:  # retried, then re-raised
            last = error
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def _fetch_row(split: str, index: int) -> dict:
    query = urllib.parse.urlencode(
        {"dataset": DATASET, "config": "default", "split": split,
         "offset": index, "length": 1}
    )
    page = _get(f"{_ROWS_API}?{query}")
    wrapper = page["rows"][0]
    if wrapper.get("truncated_cells"):
        raise RuntimeError(f"{split}[{index}]: truncated cells")
    return wrapper["row"]


def repo_of(instance_id: str) -> str:
    """`pandas-dev__pandas.95280573.func_pm...` -> `pandas`."""
    return instance_id.split(".")[0].split("__")[-1]


def diff_paths(patch: str) -> list[str]:
    return re.findall(r"^diff --git a/(\S+)", patch, re.M)


def path_matches_repo(path: str, repo: str) -> bool:
    """Whether a diff path's top component could belong to the repository.

    Deliberately generous: the repo name, its dash/underscore variants, and
    the src-layout prefix all count, and `tests`/`setup.py`-style top-level
    files are treated as matching anything. Generosity here biases the check
    against the finding, which is the direction a check should be biased.
    """
    top = path.split("/")[0].lower()
    variants = {repo.lower(), repo.lower().replace("-", "_"), repo.lower().replace("_", "")}
    if top in variants or top.replace("-", "_") in variants:
        return True
    if top in {"src", "lib", "tests", "test", "docs"} or "/" not in path:
        return True
    return any(v in top or top in v for v in variants if len(v) > 3 and len(top) > 3)


def cross_repo_groups() -> dict[str, list[tuple[str, int, dict]]]:
    """hash -> [(split, row_index, frozen_row)] for groups spanning repos."""
    by_patch: dict[str, list[tuple[str, int, dict]]] = defaultdict(list)
    for slug in SLUGS:
        document = json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))
        for index, row in enumerate(document["rows"]):
            if not row["patch_empty"]:
                by_patch[row["patch_sha256"]].append((document["split"], index, row))
    return {
        digest: members
        for digest, members in by_patch.items()
        if len({m[2]["instance_id"] for m in members}) > 1
        and len({repo_of(m[2]["instance_id"]) for m in members}) > 1
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--groups", type=int, default=50,
                        help="cross-repo groups to verify, hash-ranked (default 50)")
    args = parser.parse_args(argv)

    groups = cross_repo_groups()
    sample = sorted(groups)[: args.groups]
    findings, failures = [], []
    for digest in sample:
        members = groups[digest]
        checked = []
        for split, index, frozen in members:
            try:
                row = _fetch_row(split, index)
            except RuntimeError as error:
                failures.append(f"{split}[{index}]: UNFETCHED ({error})")
                continue
            patch = row.get("patch") or ""
            live = hashlib.sha256(patch.encode()).hexdigest()
            if live != digest:
                failures.append(
                    f"{split}[{index}]: patch hash {live[:12]} != frozen {digest[:12]}"
                )
                continue
            if row.get("instance_id") != frozen["instance_id"]:
                failures.append(f"{split}[{index}]: instance moved upstream")
                continue
            repo = repo_of(frozen["instance_id"])
            paths = diff_paths(patch)
            checked.append({
                "split": split,
                "row_index": index,
                "instance_id": frozen["instance_id"],
                "repo": repo,
                "outcome": frozen["outcome"],
                "patch_bytes": len(patch.encode()),
                "is_unified_diff": bool(paths),
                "files_touched": len(paths),
                "any_path_matches_repo": any(
                    path_matches_repo(p, repo) for p in paths
                ),
            })
        if len(checked) >= 2:
            findings.append({
                "patch_sha256": digest,
                "trivial": all(m["patch_bytes"] < TRIVIAL_BYTES for m in checked),
                "rows": checked,
            })
            print(
                f"group {digest[:12]}: {len(checked)} rows, "
                f"{checked[0]['patch_bytes']}B, "
                f"repos {sorted({m['repo'] for m in checked})}, "
                f"path-matches {[m['any_path_matches_repo'] for m in checked]}",
                flush=True,
            )

    nontrivial = [g for g in findings if not g["trivial"]]
    misaligned = [
        g for g in nontrivial
        if sum(1 for m in g["rows"] if not m["any_path_matches_repo"]) >= 1
    ]
    document = {
        "dataset": DATASET,
        "question": "are the cross-repo shared patches trivial collisions or misaligned rows",
        "trivial_bytes_threshold": TRIVIAL_BYTES,
        "cross_repo_groups_total": len(groups),
        "groups_checked": len(findings),
        "groups_nontrivial": len(nontrivial),
        "groups_with_a_row_whose_patch_touches_foreign_paths": len(misaligned),
        "failures": failures,
        "groups": findings,
    }
    OUT.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"\n{len(findings)}/{len(sample)} groups checked; "
        f"{len(nontrivial)} non-trivial; {len(misaligned)} with foreign-path rows; "
        f"{len(failures)} failures -> {OUT.relative_to(ROOT)}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
