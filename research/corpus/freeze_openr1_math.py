"""Freeze OpenR1-Math-220k: two verification columns that never meet.

The corpus keeps asking whether a proxy signal agrees with a checkable one.
Answering that has needed a rare kind of dataset, one that ships the proxy
and the truth side by side on the same rows. This dataset appears to be a
third such case: it carries `correctness_math_verify`, a symbolic check
against the published answer, and `correctness_llama`, a 70B model asked
the same question, both attached to the same generations.

They cannot be compared. The judge was run only on rows where the symbolic
check had already found nothing correct, so on every row carrying both, the
symbolic column is constant. A first pass computed Cohen's kappa over those
rows, got -0.000, and very nearly published it. The number is real and means
nothing: a variable with no variance agrees with everything at chance. The
selection is recorded here, per row, so the same trap is visible to anyone
who reads the freeze rather than being rediscovered.

What survives is structural and sharper than the statistic would have been.
This is training data, not an eval. The filtering field `correctness_count`
tracks the symbolic check where it fired and the model judge where it did
not, which means the correctness of the subset the symbolic check could not
resolve rests entirely on an unaudited model, and the shipped columns give
no way to audit it.

Frozen content-free: question id, source, problem type, and per generation a
symbolic bit, a judge bit, and a reasoning-complete bit. Never the problem,
never the answer, never a generation. Every parquet shard is hashed so the
freeze is bound to the bytes it read.

    python3 research/corpus/freeze_openr1_math.py

Needs pyarrow at freeze time to project the eight small columns out of
shards whose bulk is generation text. The committed artifact is JSON that
the audit reads with the standard library, so this adds no runtime
dependency; paging the rows API instead would move 5.5GB to extract 2MB.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import tempfile
import urllib.request

FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
OUT = FROZEN / "openr1-math.json"

DATASET = "open-r1/OpenR1-Math-220k"
CONFIG, SPLIT = "default", "train"
LICENSE = "apache-2.0"
EXPECTED_ROWS = 93_733
SHARDS = 10

#: The parquet mirror is its own branch with its own revision, so both are
#: pinned: the dataset revision names what was audited, the parquet revision
#: names the bytes actually read.
INFO_API = f"https://huggingface.co/api/datasets/{DATASET}"
PARQUET_REF = "refs%2Fconvert%2Fparquet"

COLUMNS = [
    "uuid", "source", "problem_type", "question_type",
    "correctness_count", "is_reasoning_complete",
    "correctness_math_verify", "correctness_llama",
]


def _revision(ref: str = "") -> str:
    url = INFO_API + (f"/revision/{ref}" if ref else "")
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)["sha"]


def _shard_url(revision: str, index: int) -> str:
    return (
        f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/"
        f"{CONFIG}/{SPLIT}/{index:04d}.parquet"
    )


def _bools(value: object) -> list[bool] | None:
    if value is None:
        return None
    return [bool(v) for v in value]


def extract_rows(shard_rows: list[dict]) -> list[dict]:
    """Content-free rows from one shard's projected columns.

    Shared with research/corpus/verify_corpus.py, which re-derives a shard
    from upstream and compares. Verification that reimplemented this would
    be testing a second copy of the logic rather than the freeze, and the
    two would drift.
    """
    out = []
    for row in shard_rows:
        symbolic = _bools(row["correctness_math_verify"])
        judge = _bools(row["correctness_llama"])
        complete = _bools(row["is_reasoning_complete"])

        # Columns that disagree on length cannot be paired: the shorter may
        # cover the first n generations or an arbitrary subset, and nothing
        # in the data says which. Excluded and counted, never zipped,
        # because zip truncates in silence and yields a paired statistic
        # over an alignment nobody established.
        lengths = {len(c) for c in (symbolic, judge, complete) if c is not None}
        misaligned = len(lengths) > 1
        out.append({
            "uuid": row["uuid"],
            "source": row["source"],
            "problem_type": row["problem_type"],
            "question_type": row["question_type"],
            "count": row["correctness_count"],
            "n": None if misaligned or not lengths else lengths.pop(),
            "symbolic": symbolic,
            "judge": judge,
            "complete": complete,
            "misaligned": misaligned,
        })
    return out


def freeze() -> dict:
    import pyarrow.parquet as pq

    revision = _revision()
    parquet_revision = _revision(PARQUET_REF)

    rows: list[dict] = []
    shards: list[dict] = []
    for index in range(SHARDS):
        url = _shard_url(parquet_revision, index)
        digest = hashlib.sha256()
        handle, path = tempfile.mkstemp(suffix=".parquet")
        os.close(handle)
        path = pathlib.Path(path)
        try:
            with urllib.request.urlopen(url, timeout=1800) as response:
                with path.open("wb") as sink:
                    while chunk := response.read(1 << 20):
                        digest.update(chunk)
                        sink.write(chunk)
            table = pq.ParquetFile(path).read(columns=COLUMNS)
        finally:
            path.unlink(missing_ok=True)

        shard_rows = table.to_pylist()
        del table
        rows.extend(extract_rows(shard_rows))
        shards.append({
            "shard": f"{index:04d}.parquet",
            "sha256": digest.hexdigest(),
            "rows": len(shard_rows),
        })
        print(
            f"  shard {index}: {len(shard_rows):,} rows"
            f"  (total {len(rows):,})",
            file=sys.stderr,
        )

    # An expected count declared up front, so a silently short freeze is an
    # error rather than a rate computed over a population nobody checked.
    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(
            f"expected {EXPECTED_ROWS} rows, froze {len(rows)}"
        )

    return {
        "dataset": DATASET,
        "revision": revision,
        "parquet_revision": parquet_revision,
        "license": LICENSE,
        "config": CONFIG,
        "split": SPLIT,
        "expected_rows": EXPECTED_ROWS,
        "fetched_via": "parquet mirror, column projection, shards hashed",
        "columns": COLUMNS,
        "shards": shards,
        "rows": rows,
    }


if __name__ == "__main__":
    FROZEN.mkdir(parents=True, exist_ok=True)
    document = freeze()
    temporary = OUT.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, separators=(",", ":")), encoding="utf-8"
    )
    temporary.replace(OUT)
    print(f"froze {len(document['rows']):,} rows to {OUT}", file=sys.stderr)
