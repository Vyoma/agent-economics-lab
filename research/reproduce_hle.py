"""Reproduce the grader result from nothing. One file, no repository.

    python3 research/reproduce_hle.py

Downloads the public dataset, checks its bytes, and computes the headline
figure from scratch: how well seven models asked to verify correctness rank
candidate responses inside a question. Nothing here imports this project,
because the point is to need none of it. If this disagrees with what
research/CORPUS.md publishes, the published number is wrong.

Everything a reader has to trust is in this file. The AUC is twenty lines,
the bootstrap is ten, and the download is checked against a hash you can
compare with the dataset page. The rest of the repository is machinery for
doing this over many datasets and keeping the numbers from drifting; none of
it is required to check the claim.

Standard library only. About four minutes, most of it an 83MB download.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import urllib.request

DATASET = "FUSE-verifiers/HLE-Verifications"
REVISION = "e838b3dd7a12c78c292453e66de15a9c35340c36"
SOURCE = "FUSE-hle-data.jsonl"
#: SHA-256 of the source file at that revision, so you know you read the
#: same bytes this project read. A different digest means the dataset moved,
#: not that the check failed.
EXPECTED_SHA256 = "659361e91b957063b95f7fdd18a9821773f3fde6db67b932f6a9a47e3fe4f0d5"

DRAWS = 6000
CONFIDENCE = 0.95


def fetch() -> list[dict]:
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{SOURCE}"
    print(f"downloading {SOURCE} at {REVISION[:8]} ...", file=sys.stderr, flush=True)
    digest = hashlib.sha256()
    chunks = []
    with urllib.request.urlopen(url, timeout=1800) as response:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            chunks.append(chunk)
    got = digest.hexdigest()
    print(f"sha256 {got[:16]}  {'matches' if got == EXPECTED_SHA256 else 'DIFFERS'}",
          file=sys.stderr)
    if got != EXPECTED_SHA256:
        print("upstream has changed; figures below describe different bytes",
              file=sys.stderr)
    raw = b"".join(chunks)
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def auc(pairs: list[tuple[float, bool]]) -> float | None:
    """How often a higher score belongs to a correct response.

    0.5 is a coin. Ties take the mid-rank, which is decisive rather than
    incidental here: most graders emit six integer levels across fifty
    responses, so nearly every comparison inside a question is a tie.
    Returns None when a question is all-correct or all-wrong, because such a
    question cannot rank anything and scoring it 0.5 would drag every grader
    toward the middle by an amount the dataset chose, not the grader.
    """
    ordered = sorted(pairs)
    positives = sum(1 for _, correct in ordered if correct)
    negatives = len(ordered) - positives
    if not positives or not negatives:
        return None
    ranks: dict[int, float] = {}
    index = 0
    while index < len(ordered):
        stop = index
        while stop < len(ordered) and ordered[stop][0] == ordered[index][0]:
            stop += 1
        for position in range(index, stop):
            ranks[position] = (index + stop - 1) / 2 + 1
        index = stop
    rank_sum = sum(ranks[i] for i, (_, correct) in enumerate(ordered) if correct)
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def score(value: object) -> float | None:
    if isinstance(value, list):
        value = value[0] if value else None
    return float(value) if isinstance(value, (int, float)) else None


def main() -> int:
    rows = fetch()
    judges = sorted(key for key in rows[0] if key.endswith("_scores"))
    print(f"{len(rows)} questions, {len(judges)} graders\n", file=sys.stderr)

    # alpha / 2k, because seven simultaneous interval claims are a family and
    # at a nominal 95% each the chance one is wrong is about 30%.
    alpha = (1 - CONFIDENCE) / (2 * len(judges))
    random.seed(20260903)

    results = []
    for judge in judges:
        per_question, pooled = [], []
        for row in rows:
            truth = [bool(t) for t in row["is_correct"]]
            values = [score(v) for v in row[judge]]
            if len(values) != len(truth):
                continue  # a grader that scored a different count cannot be paired
            pairs = [(v, t) for v, t in zip(values, truth) if v is not None]
            pooled.extend(pairs)
            value = auc(pairs)
            if value is not None:
                per_question.append(value)

        point = sum(per_question) / len(per_question)
        draws = sorted(
            sum(per_question[random.randrange(len(per_question))]
                for _ in per_question) / len(per_question)
            for _ in range(DRAWS)
        )
        low = draws[int(alpha * DRAWS)]
        high = draws[int((1 - alpha) * DRAWS)]
        results.append((judge.removesuffix("_scores"), point, low, high,
                        auc(pooled), len(per_question)))

    results.sort(key=lambda r: r[1])
    width = max(len(r[0]) for r in results)
    print(f"{'grader':{width}}  within-q   95% CI (family)    pooled  questions")
    for name, point, low, high, pooled_auc, questions in results:
        flag = " *" if low <= 0.5 <= high else "  "
        print(f"{name:{width}}  {point:8.3f}{flag} [{low:.3f}, {high:.3f}]"
              f"  {pooled_auc:8.3f}  {questions:9d}")

    chance = sum(1 for _, _, low, high, _, _ in results if low <= 0.5 <= high)
    print(f"\n* interval contains 0.5: {chance} of {len(results)} graders cannot be "
          "told from random at ranking within a question.")
    print(f"within-question range {results[0][1]:.3f} to {results[-1][1]:.3f}; "
          f"pooling all responses into one ranking instead reports "
          f"{min(r[4] for r in results):.3f} to {max(r[4] for r in results):.3f}, "
          "because a grader can score there by noticing a question is easy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
