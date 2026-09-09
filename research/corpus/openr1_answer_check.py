"""Was the judge rescuing correct answers, or admitting wrong ones?

The freeze establishes that 28,627 problems entered OpenR1-Math-220k solely
because a 70B judge overruled a symbolic verifier that had found nothing
correct. That is the whole finding's weight, and the booleans cannot carry
it: a symbolic checker that fails to parse a valid answer and a judge that
waves through a wrong one produce identical columns.

So this re-fetches. A deterministic sample of rows the judge admitted, every
shard checked against the hash the freeze recorded, the final boxed answer
pulled from the generation and compared with the published answer. One
generation per problem, the first the judge accepted, because generations
inside a problem are not independent observations.

The comparison is deliberately permissive: it tries exact match after
normalisation, then numeric equality. A permissive matcher makes its two
verdicts carry unequal weight, and the report says so rather than averaging
them. A match is strong evidence the symbolic checker missed a correct
answer. A mismatch is weak evidence of anything, because the third
instrument in the room is this parser, and this project has already
published a re-adjudicator whose 186 disagreements were all its own
blindness. Mismatches are reported as unresolved, never as judge errors.

Output is content-free: counts and a sample manifest of ids, never an
answer, never a generation.

    python3 research/corpus/openr1_answer_check.py
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
SOURCE = FROZEN / "openr1-math.json"
OUT = FROZEN / "openr1-math-answers.json"

SAMPLE = 400
DATASET = "open-r1/OpenR1-Math-220k"


def _select(rows: list[dict], size: int) -> dict[str, int]:
    """Hash-ranked, so the sample is fixed by the data and not by a seed
    anyone could have tuned after seeing the result."""
    admitted = [
        r for r in rows
        if r["judge"] is not None and not r["misaligned"] and any(r["judge"])
    ]
    admitted.sort(key=lambda r: hashlib.sha256(r["uuid"].encode()).hexdigest())
    return {r["uuid"]: r["judge"].index(True) for r in admitted[:size]}


def _boxed(text: str) -> str | None:
    """Last \\boxed{...}, brace-matched rather than regex-terminated, because
    a nested \\frac{a}{b} ends the match early and the answer comes back
    truncated into something that will never compare equal."""
    start = text.rfind(r"\boxed{")
    if start < 0:
        return None
    depth, index = 0, start + len(r"\boxed{") - 1
    while index < len(text):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + len(r"\boxed{"):index]
        index += 1
    return None


def _normalise(value: str) -> str:
    value = value.strip().strip("$").strip()
    value = re.sub(r"\\(?:left|right|!|,|;|quad|qquad)\s*", "", value)
    value = re.sub(r"\\[dt]frac", r"\\frac", value)
    value = re.sub(r"\\text\{([^}]*)\}", r"\1", value)
    value = re.sub(r"\s+", "", value)
    return value.rstrip(".").rstrip("$")


def _numeric(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        pass
    fraction = re.fullmatch(r"\\frac\{(-?[\d.]+)\}\{(-?[\d.]+)\}", value)
    if fraction:
        try:
            return float(fraction.group(1)) / float(fraction.group(2))
        except (ValueError, ZeroDivisionError):
            return None
    return None


def _classify(boxed: str | None, answer: str) -> str:
    """Why a boxed answer and a published answer differ, not merely that they
    do. A first pass reported 99.2% mismatched and implied the judge was
    admitting wrong answers. Inspection showed the gap was mostly shape: a
    generation boxing the letter B against a published value of 1, a
    published answer carrying four roots at once, a published answer already
    malformed upstream. Only the case where both sides reduce to a single
    unambiguous number carries weight against the judge, and it is the one
    category reported as such."""
    if boxed is None:
        return "no_boxed_answer"
    if _matches(boxed, answer):
        return "matches_published_answer"
    left, right = _normalise(boxed), _normalise(answer)
    if re.fullmatch(r"[A-E]", left) and not re.fullmatch(r"[A-E]", right):
        return "choice_letter_against_value"
    if re.search(r"[,;=]", right):
        return "published_answer_multivalued"
    a, b = _numeric(left), _numeric(right)
    if a is not None and b is not None:
        return "both_numeric_and_differ"
    return "unresolved_other"


def _matches(boxed: str, answer: str) -> bool:
    left, right = _normalise(boxed), _normalise(answer)
    if left == right:
        return True
    a, b = _numeric(left), _numeric(right)
    return a is not None and b is not None and abs(a - b) < 1e-9


def _download(url: str, path: pathlib.Path, attempts: int = 5) -> str:
    """Fetch a shard, returning the SHA-256 of what was written.

    A reset mid-shard leaves a truncated file, and a hash of a truncated
    file is a hash of nothing, so every attempt restarts from an empty file
    rather than resuming into a partial one. The first run of this check
    died on `ConnectionReset` at the eighth of ten shards and wrote no
    result at all, which was the correct failure and a wasted pass.
    """
    for attempt in range(attempts):
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(url, timeout=1800) as response:
                with path.open("wb") as sink:
                    while chunk := response.read(1 << 20):
                        digest.update(chunk)
                        sink.write(chunk)
            return digest.hexdigest()
        except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
            if attempt == attempts - 1:
                raise
            print(f"    retrying shard after {error!r}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def check() -> dict:
    document = json.loads(SOURCE.read_text(encoding="utf-8"))
    wanted = _select(document["rows"], SAMPLE)
    revision = document["parquet_revision"]

    import pyarrow.parquet as pq

    verdicts: Counter[str] = Counter()
    # Per-row verdicts, not just the totals. An aggregate nobody can
    # recompute is a number on trust, and frozen/ is swept row by row for
    # content, so a file carrying no rows is a file the sweep cannot check.
    records: list[dict] = []
    seen: list[str] = []
    for shard in document["shards"]:
        if not wanted:
            break
        url = (
            f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/"
            f"{document['config']}/{document['split']}/{shard['shard']}"
        )
        handle, path = tempfile.mkstemp(suffix=".parquet")
        os.close(handle)
        path = pathlib.Path(path)
        try:
            # Every fetched byte checked against the frozen hash. A shard
            # that changed under the pin invalidates the pairing, so this
            # aborts rather than checking rows against an unknown revision.
            if _download(url, path) != shard["sha256"]:
                raise SystemExit(f"{shard['shard']} does not match the freeze")
            handle = pq.ParquetFile(path)
            for batch in handle.iter_batches(
                batch_size=512, columns=["uuid", "answer", "generations"]
            ):
                for row in batch.to_pylist():
                    index = wanted.pop(row["uuid"], None)
                    if index is None:
                        continue
                    seen.append(row["uuid"])
                    generations = row["generations"] or []
                    if index >= len(generations):
                        verdict = "generation_index_absent"
                    else:
                        verdict = _classify(
                            _boxed(generations[index] or ""), row["answer"] or ""
                        )
                    verdicts[verdict] += 1
                    records.append({"id": row["uuid"], "verdict": verdict})
            del handle
        finally:
            path.unlink(missing_ok=True)
        print(f"  {shard['shard']}: {len(seen)} of {SAMPLE} resolved", file=sys.stderr)

    return {
        "dataset": DATASET,
        "parquet_revision": revision,
        "selection": "sha256(uuid) rank, first judge-accepted generation",
        "requested": SAMPLE,
        "checked": len(seen),
        "not_found": len(wanted),
        "verdicts": dict(sorted(verdicts.items())),
        "rows": records,
        "sample_ids_sha256": hashlib.sha256(
            "\n".join(sorted(seen)).encode()
        ).hexdigest(),
    }


if __name__ == "__main__":
    result = check()
    temporary = OUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUT)
    print(json.dumps(result, indent=2))
