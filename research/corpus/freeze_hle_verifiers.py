"""Freeze the HLE verifier scores: seven graders against a checkable answer.

The corpus's sharpest finding, that a proposed correctness signal agrees with
adjudication at chance, rested on one dataset, one scaffold and one model
family. That is a narrow base for a claim about outcome instruments, and the
obvious objection is generality.

This is the replication. 649 Humanity's Last Exam questions, 50 candidate
responses each, every response marked correct or not by exact match against
the published answer, and every response scored by seven models the dataset
calls verifiers. Different domain from the software-engineering entries,
different instrument (a model asked to judge, rather than tests the agent
wrote), and seven graders rather than one.

Frozen content-free: question id, category, answer type, and per response a
correctness bit and seven scores. Never the question, never a response,
never a justification. The source file is hashed so the freeze is bound to
the bytes it read.

    python3 research/corpus/freeze_hle_verifiers.py <path-to-FUSE-hle-data.jsonl>

The file is 80MB and the datasets-server serves this dataset's rows
unreliably, so the path is passed rather than fetched.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
OUT = FROZEN / "hle-verifiers.json"

DATASET = "FUSE-verifiers/HLE-Verifications"
REVISION_API = f"https://huggingface.co/api/datasets/{DATASET}"


def _score(value: object) -> float | None:
    """Scores arrive nested for some graders and flat for others."""
    if isinstance(value, list):
        value = value[0] if value else None
    return float(value) if isinstance(value, (int, float)) else None


def freeze(source: pathlib.Path, revision: str) -> dict:
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    judges = sorted(k for k in rows[0] if k.endswith("_scores"))

    frozen = []
    for row in rows:
        truth = row["is_correct"]
        scores = {}
        misaligned = []
        for judge in judges:
            values = [_score(v) for v in row[judge]]
            if len(values) != len(truth):
                # A grader that scored a different number of responses than
                # exist cannot be paired with them: the scores may belong to
                # the first n responses, or to a subset, and nothing in the
                # data says which. Excluded for this grader on this question
                # and counted, never zipped, because zip would silently
                # truncate to the shorter list and produce a paired
                # statistic over an alignment nobody established.
                misaligned.append(judge.removesuffix("_scores"))
                continue
            scores[judge] = values
        frozen.append({
            "id": row["id"],
            "category": row.get("category"),
            "answer_type": row.get("answer_type"),
            "responses": len(truth),
            "correct": [bool(t) for t in truth],
            "scores": {
                j.removesuffix("_scores"): scores[j] for j in judges
                if j in scores
            },
            "misaligned_graders": misaligned,
        })
    return {
        "dataset": DATASET,
        "revision": revision,
        "license": "apache-2.0",
        "source_file": source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "question": "do models asked to verify correctness agree with a "
                    "checkable answer",
        "schema": "corpus.hle-verifiers@1",
        "judges": [j.removesuffix("_scores") for j in judges],
        "rows": frozen,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit(__doc__.strip().splitlines()[-3].strip())
    import urllib.request

    with urllib.request.urlopen(REVISION_API, timeout=60) as response:
        revision = json.load(response)["sha"]
    document = freeze(pathlib.Path(argv[1]), revision)
    FROZEN.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    pairs = sum(r["responses"] for r in document["rows"])
    dropped = sum(len(r["misaligned_graders"]) for r in document["rows"])
    print(f"froze {len(document['rows'])} questions, {pairs:,} responses, "
          f"{len(document['judges'])} graders -> {OUT.relative_to(ROOT)}")
    print(f"excluded {dropped} (question, grader) pairs whose score list "
          "did not match the response count")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
