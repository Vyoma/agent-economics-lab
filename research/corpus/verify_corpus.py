"""Check every frozen corpus dataset against its source, not against itself.

`make verify-upstream` re-derives the tarsur385 findings from the upstream
files, which is the strongest form of check this project offers and covered
exactly one of the seven datasets in the corpus. For the other six a reader
could confirm the published figures recompute from the frozen evidence, and
nothing more: if the freeze had misread the source, every check would agree
with every other check and all of them would be wrong together.

This closes that. For each tabular dataset it re-fetches whole pages from
the upstream rows API at the revision the freeze recorded, runs the same
extractor the freeze used, and requires the result to equal the frozen row
field for field. A mismatch names the row and the field. A page that cannot
be fetched is a failure, never a skip, because "could not check" must never
read as "checked".

    python3 research/corpus/verify_corpus.py                 # a page each
    python3 research/corpus/verify_corpus.py --pages 5       # deeper
    python3 research/corpus/verify_corpus.py --slug jetbrains

Offsets are derived from the dataset's own size, evenly spaced and
deterministic, so two people running the same command check the same rows
and widening --pages only adds more. This is the one research target that
requires the network, alongside verify_upstream.py.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from freeze import (  # noqa: E402
    _ROWS_API,
    FROZEN,
    SPECS,
    _get,
    _sha_now,
)

#: Small: each page is megabytes of trajectories, and the point is a spot
#: check against the source, not a second download of the corpus.
PAGE_LENGTH = 10


def _offsets(total: int, pages: int) -> list[int]:
    """Evenly spaced and deterministic, so the sample is reproducible."""
    if pages >= total // PAGE_LENGTH:
        return list(range(0, total, PAGE_LENGTH))
    step = total // (pages + 1)
    return [min(step * (i + 1), total - PAGE_LENGTH) for i in range(pages)]


def verify(slug: str, pages: int) -> tuple[int, list[str], list[str]]:
    spec = SPECS[slug]
    frozen_path = FROZEN / f"{slug}.json"
    if not frozen_path.exists():
        return 0, [f"{slug}: no frozen evidence at {frozen_path.name}"], []
    document = json.loads(frozen_path.read_text(encoding="utf-8"))

    current = _sha_now(spec["dataset"])
    if current != document["revision"]:
        # Not a failure of the freeze: upstream moved. Verification against a
        # different revision would compare two different datasets.
        return 0, [
            f"{slug}: frozen at {document['revision'][:8]}, upstream is now "
            f"{current[:8]}; re-freeze before verifying"
        ], []

    # Positional, not keyed by id. The first version built {id: row}, which
    # silently kept one row per collision - and this corpus contains a
    # dataset whose ids repeat 4,209 times by design, several attempts at the
    # same instance-and-model pair. It then compared upstream rows against
    # whichever twin won the collision and reported ten confident mismatches
    # that were entirely its own. The freeze appends in upstream page order,
    # so row k of the evidence is row k of the source, and position is the
    # only sound correspondence available.
    frozen_rows = document["rows"]
    failures: list[str] = []
    drifted: set[str] = set()
    checked = 0
    for offset in _offsets(len(document["rows"]), pages):
        query = urllib.parse.urlencode({
            "dataset": spec["dataset"], "config": spec["config"],
            "split": spec["split"], "offset": offset, "length": PAGE_LENGTH,
        })
        try:
            page = _get(f"{_ROWS_API}?{query}")
        except RuntimeError as error:
            failures.append(f"{slug}[{offset}]: UNFETCHED ({error})")
            continue
        for index, wrapper in enumerate(page["rows"]):
            position = offset + index
            if wrapper.get("truncated_cells"):
                failures.append(
                    f"{slug}[{position}]: upstream truncated "
                    f"{wrapper['truncated_cells']}"
                )
                continue
            rederived = spec["extract"](wrapper["row"])
            checked += 1
            if position >= len(frozen_rows):
                failures.append(
                    f"{slug}[{position}]: upstream has a row the frozen "
                    "evidence does not"
                )
                continue
            frozen = frozen_rows[position]
            for field, value in rederived.items():
                if field not in frozen:
                    # The extractor grew a field after this dataset was
                    # frozen. That is schema drift, not a disagreement about
                    # what upstream says, and reporting it as a mismatch
                    # would train a reader to ignore this tool. Counted and
                    # named; a re-freeze carries the field.
                    drifted.add(field)
                    continue
                if frozen[field] != value:
                    failures.append(
                        f"{slug}[{position}] {rederived['id']}: {field} "
                        f"re-derives as "
                        f"{value!r}, frozen says {frozen[field]!r}"
                    )
    return checked, failures, sorted(drifted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=int, default=1,
                        help="pages per dataset (default 1)")
    parser.add_argument("--slug", help="verify one dataset")
    args = parser.parse_args(argv)

    slugs = [args.slug] if args.slug else sorted(
        s for s in SPECS if (FROZEN / f"{s}.json").exists()
    )
    total_checked = 0
    all_failures: list[str] = []
    for slug in slugs:
        checked, failures, drifted = verify(slug, args.pages)
        total_checked += checked
        all_failures.extend(failures)
        state = "ok" if not failures else "FAIL"
        note = (
            f"  (frozen before {', '.join(drifted)}; a re-freeze carries it)"
            if drifted else ""
        )
        print(f"{state:4s} {slug:22s} {checked:3d} rows re-derived from source{note}",
              flush=True)

    print(f"\n{total_checked} rows checked against upstream across "
          f"{len(slugs)} datasets")
    for failure in all_failures:
        print(f"FAIL {failure}", file=sys.stderr)
    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
