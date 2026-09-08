"""Check frozen corpus datasets against their source, not against themselves.

`make verify-upstream` re-derives the tarsur385 findings from the upstream
files, which is the strongest form of check this project offers and covered
exactly one dataset. For the others a reader could confirm the published
figures recompute from the frozen evidence, and nothing more: if the freeze
had misread the source, every check would agree with every other check and
all of them would be wrong together.

Every frozen document has a verifier, and that is enforced rather than
hoped for. Datasets frozen by a standalone `freeze_*.py` have no entry in
`freeze.SPECS`, and for a while this script skipped them and printed the
count of what it had checked, which read as the count of what exists: six of
fourteen published findings rested on evidence no reader could check against
source, including the two the front page leans on hardest. That is the exact
failure this module was written to prevent, committed by the module.

VERIFIERS now holds one callable per frozen document, each owning the
transport its freeze used, and a document without one fails the run. Each
verifier re-derives rows by calling the freezer's own extractor on freshly
fetched bytes, so what is proven is reproducibility: the same source and the
same code give the same frozen file. Re-implementing extraction inside the
verifier would test a second copy of the logic and let the two drift.

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

from collections.abc import Callable

import argparse
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import urllib.parse
import urllib.request

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


def _download(url: str, destination: pathlib.Path) -> str:
    """Stream to disk, returning the SHA-256 of every byte received. Hashing
    while writing rather than re-reading means the digest describes what
    arrived, not what a later read happened to find."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=1800) as response:
        with destination.open("wb") as sink:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                sink.write(chunk)
    return digest.hexdigest()


def _verify_hle(slug: str, pages: int) -> tuple[int, list[str], list[str]]:
    """Total rather than sampled, because it can be.

    The freeze recorded the SHA-256 of the entire source file, so this
    fetches that file at the pinned revision, checks every byte against the
    recorded digest, re-runs the freezer on what arrived, and compares all
    649 rows against what is committed. Same input and same code must give
    the same output; if they do not, either the source moved or the frozen
    file was edited, and both are things a reader should be able to detect
    without trusting this repository.
    """
    import freeze_hle_verifiers as freezer

    document = json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))
    current = _sha_now(document["dataset"])
    if current != document["revision"]:
        return 0, [
            f"{slug}: frozen at {document['revision'][:8]}, upstream is now "
            f"{current[:8]}; re-freeze before verifying"
        ], []

    url = (
        f"https://huggingface.co/datasets/{document['dataset']}/resolve/"
        f"{document['revision']}/FUSE-hle-data.jsonl"
    )
    handle, raw = tempfile.mkstemp(suffix=".jsonl")
    os.close(handle)
    path = pathlib.Path(raw)
    try:
        digest = _download(url, path)
        if digest != document["source_sha256"]:
            return 0, [
                f"{slug}: upstream source hashes {digest[:12]}, freeze "
                f"recorded {document['source_sha256'][:12]}"
            ], []
        rederived = freezer.freeze(path, document["revision"])
    finally:
        path.unlink(missing_ok=True)

    failures = []
    frozen_rows = {row["id"]: row for row in document["rows"]}
    fresh_rows = {row["id"]: row for row in rederived["rows"]}
    if set(frozen_rows) != set(fresh_rows):
        missing = sorted(set(frozen_rows) - set(fresh_rows))[:3]
        extra = sorted(set(fresh_rows) - set(frozen_rows))[:3]
        failures.append(
            f"{slug}: row ids differ (only frozen: {missing}, only fresh: {extra})"
        )
    for key in sorted(set(frozen_rows) & set(fresh_rows)):
        if frozen_rows[key] != fresh_rows[key]:
            failures.append(f"{slug}/{key}: re-derived row differs from frozen")
            if len(failures) > 5:
                break
    return len(frozen_rows), failures, []


#: One verifier per frozen document. The rows-API family shares `verify`;
#: the rest own their transport because they were frozen through it. A
#: frozen document with no entry here fails the run: for a while they were
#: simply skipped, and the count of what had been checked read as the count
#: of what exists.
def _verify_openr1(slug: str, pages: int) -> tuple[int, list[str], list[str]]:
    """Re-derive whole shards from the parquet mirror.

    The freeze recorded a SHA-256 per shard, so `pages` shards are chosen by
    hash rank, fetched at the pinned parquet revision, checked byte for
    byte, and re-extracted with the freezer's own row builder. Shards are
    ordered with their row counts, so each one's slice of the frozen
    document is exact and the comparison is total within the shard rather
    than a sample inside it.
    """
    import freeze_openr1_math as freezer

    document = json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))
    current = _sha_now(document["dataset"])
    if current != document["revision"]:
        return 0, [
            f"{slug}: frozen at {document['revision'][:8]}, upstream is now "
            f"{current[:8]}; re-freeze before verifying"
        ], []

    shards = document["shards"]
    offsets, running = [], 0
    for shard in shards:
        offsets.append(running)
        running += shard["rows"]

    chosen = sorted(
        range(len(shards)),
        key=lambda i: hashlib.sha256(shards[i]["shard"].encode()).hexdigest(),
    )[:max(1, pages)]

    checked, failures, bytes_only = 0, [], []
    for index in chosen:
        shard = shards[index]
        url = (
            f"https://huggingface.co/datasets/{document['dataset']}/resolve/"
            f"{document['parquet_revision']}/{document['config']}/"
            f"{document['split']}/{shard['shard']}"
        )
        handle, raw = tempfile.mkstemp(suffix=".parquet")
        os.close(handle)
        path = pathlib.Path(raw)
        try:
            digest = _download(url, path)
            if digest != shard["sha256"]:
                failures.append(
                    f"{slug}/{shard['shard']}: upstream hashes {digest[:12]}, "
                    f"freeze recorded {shard['sha256'][:12]}"
                )
                continue
            # The byte check above is the provenance claim and needs
            # nothing installed. Re-extracting the rows additionally proves
            # the freeze is reproducible from those bytes, and that needs
            # pyarrow to read a parquet column. Where it is absent the
            # weaker check still runs and the report says which was done,
            # rather than reporting a row count nobody computed.
            try:
                import pyarrow.parquet as pq
            except ImportError:
                bytes_only.append(shard["shard"])
                continue
            table = pq.ParquetFile(path).read(columns=freezer.COLUMNS)
            fresh = freezer.extract_rows(table.to_pylist())
        finally:
            path.unlink(missing_ok=True)

        frozen_slice = document["rows"][offsets[index]:offsets[index] + shard["rows"]]
        if len(fresh) != len(frozen_slice):
            failures.append(
                f"{slug}/{shard['shard']}: {len(fresh)} rows upstream, "
                f"{len(frozen_slice)} frozen"
            )
            continue
        for fresh_row, frozen_row in zip(fresh, frozen_slice):
            checked += 1
            if fresh_row != frozen_row:
                failures.append(
                    f"{slug}/{shard['shard']}/{frozen_row['uuid']}: "
                    "re-derived row differs from frozen"
                )
                if len(failures) > 5:
                    break
    if bytes_only:
        print(
            f"     {slug}: {len(bytes_only)} shard(s) checked byte for byte "
            "against the freeze; install pyarrow to also re-extract their "
            "rows", flush=True,
        )
    return checked, failures, []


def _verify_cogym(slug: str, pages: int) -> tuple[int, list[str], list[str]]:
    """Re-fetch whole session files and re-run the freezer's extractor.

    One file per session, so a hash-ranked sample of sessions is fetched at
    the pinned revision and each re-extracted with `freeze_cogym._row`. A
    session that cannot be fetched counts as a failure: "could not check"
    must never read as "checked", which is the rule this module exists for.
    """
    import freeze_cogym as freezer

    document = json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))
    current = _sha_now(document["dataset"])
    if current != document["revision"]:
        return 0, [
            f"{slug}: frozen at {document['revision'][:8]}, upstream is now "
            f"{current[:8]}; re-freeze before verifying"
        ], []

    rows = {row["id"]: row for row in document["rows"]}
    chosen = sorted(
        rows, key=lambda i: hashlib.sha256(i.encode()).hexdigest()
    )[:max(1, pages) * 5]

    checked, failures = 0, []
    for identifier in chosen:
        name = f"session_{identifier}.json"
        url = (
            f"https://huggingface.co/datasets/{document['dataset']}/resolve/"
            f"{document['revision']}/{urllib.parse.quote(name)}"
        )
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                payload = response.read()
        except Exception as error:
            failures.append(f"{slug}/{identifier}: UNFETCHED ({error})")
            continue
        checked += 1
        if freezer._row(name, payload) != rows[identifier]:
            failures.append(
                f"{slug}/{identifier}: re-derived row differs from frozen"
            )
    return checked, failures, []


def _verify_posttrainbench(slug: str, pages: int) -> tuple[int, list[str], list[str]]:
    """Re-derive whole runs from the files that produced them.

    Each row is one run directory, so a hash-ranked sample of runs is
    re-read at the pinned revision through the freezer's own `_run_row`,
    which fetches the same files the freeze did. An unreadable run is a
    failure rather than a skip.
    """
    import freeze_posttrainbench as freezer

    document = json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))
    current = _sha_now(document["dataset"])
    if current != document["revision"]:
        return 0, [
            f"{slug}: frozen at {document['revision'][:8]}, upstream is now "
            f"{current[:8]}; re-freeze before verifying"
        ], []

    # `id` is "<group>/<run>", which is exactly what _run_row takes.
    rows = {row["id"]: row for row in document["rows"]}
    chosen = sorted(
        rows, key=lambda k: hashlib.sha256(k.encode()).hexdigest()
    )[:max(1, pages) * 3]

    checked, failures = 0, []
    for key in chosen:
        group, run = key.split("/", 1)
        try:
            fresh = freezer._run_row(group, run)
        except Exception as error:
            failures.append(f"{slug}/{group}/{run}: UNFETCHED ({error})")
            continue
        if fresh is None:
            failures.append(f"{slug}/{group}/{run}: upstream no longer yields a row")
            continue
        checked += 1
        if fresh != rows[key]:
            differing = sorted(
                k for k in set(fresh) | set(rows[key])
                if fresh.get(k) != rows[key].get(k)
            )
            failures.append(
                f"{slug}/{group}/{run}: re-derived row differs on {differing}"
            )
    return checked, failures, []


VERIFIERS: dict[str, "Callable[[str, int], tuple[int, list[str], list[str]]]"] = {
    **{slug: verify for slug in SPECS},
    "hle-verifiers": _verify_hle,
    "openr1-math": _verify_openr1,
    "cogym": _verify_cogym,
    "posttrainbench": _verify_posttrainbench,
}

#: Not datasets: derived sidecars produced by a check, verified by the test
#: that recomputes the figure they carry.
SIDECARS: frozenset[str] = frozenset({
    "openr1-math-answers", "swesmith-patch-check",
})

#: Frozen documents that are not published as corpus entries and so carry no
#: finding to verify. A partial freeze is evidence of nothing.
NOT_PUBLISHED: frozenset[str] = frozenset({"kwai-klear.partial"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=int, default=1,
                        help="pages per dataset (default 1)")
    parser.add_argument("--slug", help="verify one dataset")
    args = parser.parse_args(argv)

    frozen = sorted(
        path.stem for path in FROZEN.glob("*.json")
        if path.stem not in SIDECARS and path.stem not in NOT_PUBLISHED
    )
    # A frozen document with no verifier is a failure, not a line in a list
    # of reasons it could not be checked. That list existed, and the count
    # of what had been checked read as the count of what exists.
    unregistered = sorted(set(frozen) - set(VERIFIERS))
    slugs = [args.slug] if args.slug else sorted(set(frozen) & set(VERIFIERS))

    total_checked = 0
    all_failures: list[str] = []
    for slug in slugs:
        checked, failures, drifted = VERIFIERS[slug](slug, args.pages)
        total_checked += checked
        all_failures.extend(failures)
        state = "ok" if not failures else "FAIL"
        note = (
            f"  (frozen before {', '.join(drifted)}; a re-freeze carries it)"
            if drifted else ""
        )
        print(f"{state:4s} {slug:22s} {checked:4d} rows re-derived from source{note}",
              flush=True)

    scope = f"{len(slugs)} of {len(frozen)}" if not args.slug else "1 selected"
    print(f"\n{total_checked} rows checked against upstream across "
          f"{scope} frozen datasets")
    for slug in unregistered:
        print(
            f"FAIL {slug}: frozen evidence with no upstream verifier. Every "
            "published finding must be re-derivable from source; add one to "
            "VERIFIERS or do not publish the entry.", file=sys.stderr,
        )
    all_failures.extend(unregistered)
    for failure in all_failures:
        print(f"FAIL {failure}", file=sys.stderr)
    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
