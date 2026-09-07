"""The corpus: every public agent-trajectory dataset this project has audited.

One dataset with findings is an anecdote. A registry of datasets each audited
the same way (same checks, same content-free frozen evidence, same refusal to
guess) is an instrument with a track record. This renders that registry from
the frozen evidence and nothing else; `make corpus` fails if the committed
document and the evidence disagree.

A clean bill is recorded with the same care as a defect. An auditor that only
ever finds problems is indistinguishable from one that manufactures them.

Checks, each applied wherever the frozen schema supports it:

  outcome census      Every distinct value of the outcome field, counted. An
                      outcome column with one value on every row is not a
                      measurement.
  re-adjudication     Where the dataset ships raw test logs beside graded-test
                      lists, resolution is re-derived from the log and compared
                      with the published label. Rows the parser cannot fully
                      read are excluded and counted, never guessed
                      (see parse_tests.py for the 186-false-positive lesson).
  duplicate arms      Transcript hashes that appear more than once, and whether
                      the label agrees with itself inside each duplicate group.
  degenerate runs     Positive outcomes on runs whose step count could not have
                      attempted the task.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
CORPUS = ROOT / "research" / "CORPUS.md"
TARSUR = ROOT / "examples" / "public-swebench" / "outcome_audit.json"
TARSUR_REVISION = "b55979d6b24850b72ae4d80f912526280cd6058a"


def outcome_census(document: dict) -> Counter:
    return Counter(json.dumps(row["outcome"]) for row in document["rows"])


def readjudication(document: dict) -> dict | None:
    graded = [row for row in document["rows"] if "graded" in row]
    if not graded:
        return None
    verdicts = Counter(row["graded"]["verdict"] for row in graded)
    agree, disagreements = 0, []
    for row in graded:
        verdict = row["graded"]["verdict"]
        if verdict not in ("RESOLVED", "UNRESOLVED"):
            continue
        if (row["outcome"] == 1.0) == (verdict == "RESOLVED"):
            agree += 1
        else:
            disagreements.append(row["instance_id"])
    return {
        "rows_with_logs": len(graded),
        "verdicts": dict(verdicts),
        "parsed": agree + len(disagreements),
        "agree": agree,
        "disagreements": disagreements,
    }


def duplicate_groups(document: dict) -> list[dict]:
    by_hash: dict[str, list[dict]] = {}
    for row in document["rows"]:
        by_hash.setdefault(row["transcript_sha256"], []).append(row)
    groups = []
    for digest, rows in sorted(by_hash.items()):
        if len(rows) < 2:
            continue
        labels = {json.dumps(row["outcome"]) for row in rows}
        groups.append(
            {"transcript_sha256": digest, "n": len(rows),
             "ids": [row["id"] for row in rows], "labels_agree": len(labels) == 1}
        )
    return groups


def degenerate_positives(document: dict) -> list[str]:
    return [
        row["id"]
        for row in document["rows"]
        if row["outcome"] in (True, 1.0) and (row.get("steps") or 0) <= 1
    ]


def _load(slug: str) -> dict:
    return json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))


SWESMITH_SLUGS = ("swesmith-tool", "swesmith-xml", "swesmith-ticks")


def nebius_sweagent_summary() -> dict:
    """Every published number for the SWE-agent-trajectories entry."""
    doc = _load("nebius-sweagent")
    rows = doc["rows"]
    by_transcript: dict[str, list] = {}
    for row in rows:
        by_transcript.setdefault(row["transcript_sha256"], []).append(row)
    dup_groups = {h: v for h, v in by_transcript.items() if len(v) > 1}
    resolved = [r for r in rows if r["outcome"] is True]
    return {
        "revision": doc["revision"],
        "rows": len(rows),
        "resolved": len(resolved),
        "duplicate_transcript_groups": len(dup_groups),
        "resolved_with_empty_patch": sum(1 for r in resolved if r["patch_empty"]),
        "resolved_with_empty_logs": sum(
            1 for r in resolved if r["eval_logs_bytes"] == 0
        ),
        "unresolved_empty_patch": sum(
            1 for r in rows if r["outcome"] is False and r["patch_empty"]
        ),
        "unresolved_empty_logs": sum(
            1 for r in rows if r["outcome"] is False and r["eval_logs_bytes"] == 0
        ),
        "repeat_attempt_pairs": sum(
            c - 1
            for c in Counter(
                r["id"] for r in rows
            ).values()
            if c > 1
        ),
    }


def nebius_openhands_summary() -> dict:
    """Every published number for the SWE-rebench-openhands entry."""
    doc = _load("nebius-openhands")
    rows = doc["rows"]

    def _kappa(subset: list) -> tuple[float, float, float]:
        agree = sum(
            1 for r in subset if (r["outcome"] == 1) == (r["cross"] == 1.0)
        )
        po = agree / len(subset)
        rr = sum(1 for r in subset if r["outcome"] == 1) / len(subset)
        pr = sum(1 for r in subset if r["cross"] == 1.0) / len(subset)
        pe = rr * pr + (1 - rr) * (1 - pr)
        positives = [r for r in subset if r["cross"] == 1.0]
        precision = (
            sum(1 for r in positives if r["outcome"] == 1) / len(positives)
        )
        return po, (po - pe) / (1 - pe), precision

    by_transcript: dict[str, list] = {}
    for row in rows:
        by_transcript.setdefault(row["transcript_sha256"], []).append(row)
    dup_groups = {h: v for h, v in by_transcript.items() if len(v) > 1}

    present = [r for r in rows if r["cross"] is not None]
    valid = [r for r in present if r["gen_tests_correct"] == 1.0]
    invalid = [r for r in present if r["gen_tests_correct"] == 0.0]
    po_all, k_all, prec_all = _kappa(present)
    po_valid, k_valid, prec_valid = _kappa(valid)
    _, k_invalid, _ = _kappa(invalid)
    max_iter = [
        r for r in rows
        if str(r.get("exit_status", "")).startswith(
            "RuntimeError: Agent reached maximum"
        )
    ]
    # The majority-class baseline, which is the number the agreement figure
    # has to beat to be worth consulting. It is not beaten. Reporting an
    # agreement rate without it is the omission this corpus keeps finding
    # elsewhere, and it stood here unremarked for four entries.
    resolved_n = sum(1 for r in present if r["outcome"] == 1)
    majority = max(resolved_n, len(present) - resolved_n) / len(present)

    # An interval on the kappa, clustered over instances because the same
    # instance appears under several runs. Published as "chance" before this
    # existed, which is wrong: chance is zero and this interval excludes it.
    # The number is reliably non-zero and far too small to act on, and those
    # are different statements.
    import random as _random
    _random.seed(20260905)
    # Per-instance 2x2 sufficient statistics, so a draw sums four integers
    # per cluster instead of rescanning 31,389 rows. A first version did the
    # latter and put 60 seconds into every test run that touched this entry.
    cells: dict[str, list[int]] = {}
    for row in present:
        cell = cells.setdefault(row["instance_id"], [0, 0, 0, 0])
        cell[(0 if row["outcome"] == 1 else 2) + (0 if row["cross"] == 1.0 else 1)] += 1
    table = list(cells.values())
    n11 = [c[0] for c in table]
    n10 = [c[1] for c in table]
    n01 = [c[2] for c in table]
    n00 = [c[3] for c in table]
    size = len(table)
    draws = []
    for _ in range(2000):
        idx = [_random.randrange(size) for _ in range(size)]
        a = sum(n11[i] for i in idx)
        b = sum(n10[i] for i in idx)
        c = sum(n01[i] for i in idx)
        d = sum(n00[i] for i in idx)
        total = a + b + c + d
        if not total:
            continue
        po = (a + d) / total
        pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (total * total)
        if pe < 1:
            draws.append((po - pe) / (1 - pe))
    draws.sort()

    return {
        "revision": doc["revision"],
        "rows": len(rows),
        "resolved": sum(1 for r in rows if r["outcome"] == 1),
        "majority_baseline": majority,
        "agreement_minus_majority": po_all - majority,
        "kappa_low": draws[int(0.025 * len(draws))],
        "kappa_high": draws[int(0.975 * len(draws))],
        "kappa_clusters": size,
        "duplicate_transcript_groups": len(dup_groups),
        "empty_patches": sum(1 for r in rows if r["patch_empty"]),
        "empty_patch_resolved": sum(
            1 for r in rows if r["patch_empty"] and r["outcome"] == 1
        ),
        "max_iteration_rows": len(max_iter),
        "max_iteration_resolved": sum(1 for r in max_iter if r["outcome"] == 1),
        "cross_present": len(present),
        "agreement": po_all,
        "kappa": k_all,
        "precision": prec_all,
        "valid_n": len(valid),
        "valid_kappa": k_valid,
        "valid_precision": prec_valid,
        "invalid_n": len(invalid),
        "invalid_kappa": k_invalid,
    }


def _auc(pairs: list) -> float | None:
    """Rank-based AUC: threshold-free, and invariant to the rubric.

    The graders score 0 to 5 against a rubric the dataset does not publish,
    so no threshold can be justified from the data. AUC asks only whether a
    higher score is more often a correct response, which is the weakest
    assumption under which a grader could be said to work at all.
    """
    ordered = sorted(pairs)
    n = len(ordered)
    ranks: dict[int, float] = {}
    index = 0
    while index < n:
        stop = index
        while stop < n and ordered[stop][0] == ordered[index][0]:
            stop += 1
        rank = (index + stop - 1) / 2 + 1
        for k in range(index, stop):
            ranks[k] = rank
        index = stop
    positives = sum(1 for _, y in ordered if y)
    negatives = n - positives
    if not positives or not negatives:
        return None
    rank_sum = sum(ranks[i] for i, (_, y) in enumerate(ordered) if y)
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def hle_verifier_summary() -> dict:
    """Seven models asked to verify correctness, against a checkable answer.

    Reported within question, not pooled. The graders' job on this dataset is
    to pick the right response among fifty candidates to the same question,
    so the statistic that matters is how well a grader ranks inside a
    question. Pooling all 32,450 responses into one ranking lets a grader
    score well by noticing that a question is easy, which is not the task.
    This entry published the pooled figure first, and pooling flattered every
    grader: the best fell from 0.653 to 0.547 and one crossed from 0.537 to
    below chance. The pooled number is kept beside it, because the gap
    between them is the size of the between-question effect and is worth
    seeing, but the within-question figure is the claim.
    """
    import random

    document = _load("hle-verifiers")
    rows = document["rows"]
    judges = document["judges"]

    random.seed(20260903)
    graders = []
    for judge in sorted(judges):
        per_question, pooled, nulls = [], [], 0
        for row in rows:
            values = row["scores"].get(judge)
            if values is None:
                continue
            nulls += sum(1 for v in values if v is None)
            pairs = [
                (float(s), bool(y))
                for s, y in zip(values, row["correct"]) if s is not None
            ]
            pooled.extend(pairs)
            # A question whose responses are all correct or all wrong cannot
            # rank anything, so it carries no information about a grader and
            # is dropped rather than scored 0.5, which would pull every
            # grader toward the middle by an amount set by the dataset.
            value = _auc(pairs)
            if value is not None:
                per_question.append(value)

        point = sum(per_question) / len(per_question)
        # Resampling questions, which are the independent unit. The mean of
        # per-question AUCs is cheap to resample once each question's AUC is
        # computed, so this runs the 6,000 draws the frontier protocol's own
        # adequacy rule requires of a seven-member family, rather than the
        # 400 that put Monte Carlo noise in the published third decimal.
        draws = sorted(
            sum(per_question[random.randrange(len(per_question))]
                for _ in per_question) / len(per_question)
            for _ in range(6000)
        )
        low = draws[int(0.025 * len(draws))]
        high = draws[int(0.975 * len(draws))]
        graders.append({
            "judge": judge,
            "pairs": len(pooled),
            "null_scores": nulls,
            "questions_scored": len(per_question),
            "auc": point,
            "low": low,
            "high": high,
            "pooled_auc": _auc(pooled),
            "indistinguishable_from_random": low <= 0.5 <= high,
        })

    correct = [y for row in rows for y in row["correct"]]
    return {
        "revision": document["revision"],
        "questions": len(rows),
        "responses": len(correct),
        "base_rate": sum(correct) / len(correct),
        "graders": graders,
        "excluded_pairs": sum(len(r["misaligned_graders"]) for r in rows),
        "best": max(graders, key=lambda g: g["auc"]),
        "worst": min(graders, key=lambda g: g["auc"]),
        "below_chance": [g["judge"] for g in graders if g["auc"] < 0.5],
        "pooled_best": max(g["pooled_auc"] for g in graders),
        "pooled_worst": min(g["pooled_auc"] for g in graders),
    }


RATINGS = ("outcomeRating", "agentRating", "communicationRating")


def _qwk(observed: list[tuple[int, int]]) -> float:
    """Quadratic-weighted kappa on (rating, rating) pairs."""
    n = len(observed)
    if not n:
        return float("nan")
    categories = sorted({v for pair in observed for v in pair})
    if len(categories) < 2:
        return float("nan")
    span = (categories[-1] - categories[0]) ** 2
    marginal_a = {c: sum(1 for a, _ in observed if a == c) for c in categories}
    marginal_b = {c: sum(1 for _, b in observed if b == c) for c in categories}
    numerator = sum(((a - b) ** 2 / span) for a, b in observed) / n
    denominator = sum(
        ((i - j) ** 2 / span) * marginal_a[i] * marginal_b[j] / n
        for i in categories for j in categories
    ) / n
    return 1 - numerator / denominator if denominator else float("nan")


def cogym_summary() -> dict:
    """Human ratings: coverage, and how far apart one person's answers run."""
    import itertools
    import statistics

    document = _load("cogym")
    rows = document["rows"]

    def agreement(first: str, second: str) -> dict:
        both = [
            (r[first], r[second]) for r in rows
            if r[first] is not None and r[second] is not None
        ]
        categories = sorted({v for pair in both for v in pair})
        n = len(both)
        observed = Counter(both)
        marginal_a = Counter(a for a, _ in both)
        marginal_b = Counter(b for _, b in both)
        span = (max(categories) - min(categories)) ** 2
        numerator = sum(
            ((i - j) ** 2 / span) * observed.get((i, j), 0)
            for i in categories for j in categories
        )
        denominator = sum(
            ((i - j) ** 2 / span) * marginal_a[i] * marginal_b[j] / n
            for i in categories for j in categories
        )
        return {
            "n": n,
            "exact": sum(1 for a, b in both if a == b) / n,
            "mean_absolute_difference": statistics.mean(
                abs(a - b) for a, b in both
            ),
            "two_or_more_apart": sum(1 for a, b in both if abs(a - b) >= 2) / n,
            # Quadratic-weighted, the standard for ordinal ratings: a
            # one-point gap should not count the same as a four-point one.
            "qwk": 1 - numerator / denominator if denominator else float("nan"),
        }

    pairs = {
        f"{a}|{b}": agreement(a, b)
        for a, b in itertools.combinations(RATINGS, 2)
    }

    # An interval on each QWK. The summary page graded 0.625 against a 0.60
    # floor and printed "yes", which is deciding pass or fail from a point
    # estimate at n=191: the failure mode this package exists to refuse,
    # executed on its own summary of itself.
    import random as _random
    _random.seed(20260905)
    for key, (first, second) in (
        (f"{a}|{b}", (a, b)) for a, b in itertools.combinations(RATINGS, 2)
    ):
        observed = [
            (r[first], r[second]) for r in rows
            if r[first] is not None and r[second] is not None
        ]
        if len(observed) < 30:
            continue
        draws = []
        for _ in range(2000):
            sample = [
                observed[_random.randrange(len(observed))]
                for _ in observed
            ]
            value = _qwk(sample)
            if value == value:
                draws.append(value)
        draws.sort()
        pairs[key]["qwk_low"] = draws[int(0.025 * len(draws))]
        pairs[key]["qwk_high"] = draws[int(0.975 * len(draws))]
    short = [
        r for r in rows if r["event_count"] <= 3 and r["agentRating"] is not None
    ]
    return {
        "revision": document["revision"],
        "rows": len(rows),
        "tasks": dict(Counter(r["task"] for r in rows)),
        "coverage": {
            key: sum(1 for r in rows if r[key] is not None) for key in RATINGS
        },
        "pairs": pairs,
        "short_sessions": len(short),
        "short_mean_rating": (
            statistics.mean(r["agentRating"] for r in short) if short else None
        ),
    }


def posttrainbench_summary() -> dict:
    """Every published number for the PostTrainBench entry."""
    import statistics
    from collections import defaultdict

    document = _load("posttrainbench")
    rows = document["rows"]

    def accuracy(row: dict) -> float | None:
        value = row["accuracy"]
        return value if isinstance(value, (int, float)) else None

    usable = [r for r in rows if accuracy(r) is not None]
    judged = [r for r in rows if r["contamination"] is not None]

    by_benchmark: dict[str, dict[str, list]] = defaultdict(
        lambda: {"clean": [], "dirty": []}
    )
    for row in rows:
        value = accuracy(row)
        if value is None or row["contamination"] is None:
            continue
        by_benchmark[row["benchmark"]][
            "dirty" if row["contamination"] else "clean"
        ].append(value)

    clean_all = [v for b in by_benchmark.values() for v in b["clean"]]
    dirty_all = [v for b in by_benchmark.values() for v in b["dirty"]]
    pooled = statistics.mean(dirty_all) - statistics.mean(clean_all)

    # Weighted within-benchmark difference. The pooled figure is confounded
    # by composition: contamination concentrates on the benchmark with the
    # second-highest clean baseline, so pooling attributes that benchmark's
    # difficulty to contamination.
    comparable = [
        (name, buckets)
        for name, buckets in by_benchmark.items()
        if len(buckets["clean"]) >= 5 and len(buckets["dirty"]) >= 5
    ]
    numerator = sum(
        (statistics.mean(b["dirty"]) - statistics.mean(b["clean"]))
        * (len(b["clean"]) + len(b["dirty"]))
        for _, b in comparable
    )
    denominator = sum(len(b["clean"]) + len(b["dirty"]) for _, b in comparable)
    stratified = numerator / denominator

    worst = max(
        comparable,
        key=lambda item: len(item[1]["dirty"])
        / (len(item[1]["clean"]) + len(item[1]["dirty"])),
    )
    worst_name, worst_buckets = worst
    worst_n = len(worst_buckets["clean"]) + len(worst_buckets["dirty"])

    return {
        "revision": document["revision"],
        "rows": len(rows),
        "groups": document["groups"],
        "no_metrics_file": sum(1 for r in rows if not r["has_metrics"]),
        "malformed_metrics": sum(1 for r in rows if r["metrics_malformed"]),
        "unusable_accuracy": len(rows) - len(usable),
        "unjudged": len(rows) - len(judged),
        "judged": len(judged),
        "contaminated": sum(1 for r in judged if r["contamination"]),
        "disallowed_model": sum(1 for r in judged if r["disallowed_model"]),
        "pooled_difference": pooled,
        "stratified_difference": stratified,
        "overstatement": pooled / stratified,
        "comparable_benchmarks": len(comparable),
        "benchmarks_where_contamination_helps": sum(
            1 for _, b in comparable
            if statistics.mean(b["dirty"]) > statistics.mean(b["clean"])
        ),
        "worst_benchmark": worst_name,
        "worst_rate": len(worst_buckets["dirty"]) / worst_n,
        "worst_share_of_contamination": len(worst_buckets["dirty"]) / len(dirty_all),
        "worst_clean_mean": statistics.mean(worst_buckets["clean"]),
        "median_hours": statistics.median(
            r["duration_seconds"] for r in rows
            if isinstance(r["duration_seconds"], int)
        ) / 3600,
    }


def swesmith_summary() -> dict:
    """Every published number for the SWE-smith entry, from frozen rows alone."""
    splits = {slug: _load(slug) for slug in SWESMITH_SLUGS}
    all_rows = [(slug, row) for slug, doc in splits.items() for row in doc["rows"]]

    by_transcript: dict[str, list] = {}
    for slug, row in all_rows:
        by_transcript.setdefault(row["transcript_sha256"], []).append((slug, row))
    duplicate_groups_ = {h: v for h, v in by_transcript.items() if len(v) > 1}
    label_disagreeing = sum(
        1 for v in duplicate_groups_.values()
        if len({json.dumps(r["outcome"]) for _, r in v}) > 1
    )
    tool_xml_overlap = sum(
        1 for v in duplicate_groups_.values()
        if {s for s, _ in v} >= {"swesmith-tool", "swesmith-xml"}
    )
    if any(
        "swesmith-ticks" in {s for s, _ in v} and len({s for s, _ in v}) > 1
        for v in duplicate_groups_.values()
    ):
        raise AssertionError(
            "swesmith: ticks now shares transcripts across splits; "
            "rewrite the duplication paragraph"
        )

    xml_seen: dict[str, dict] = {}
    xml_identical_dupes = 0
    for row in splits["swesmith-xml"]["rows"]:
        prev = xml_seen.get(row["id"])
        if prev is not None:
            if (prev["transcript_sha256"], prev["outcome"]) == (
                row["transcript_sha256"], row["outcome"]
            ):
                xml_identical_dupes += 1
        else:
            xml_seen[row["id"]] = row

    def _repo(instance_id: str) -> str:
        return instance_id.split(".")[0].split("__")[-1]

    by_patch: dict[str, list] = {}
    for _, row in all_rows:
        if not row["patch_empty"]:
            by_patch.setdefault(row["patch_sha256"], []).append(row)
    cross_repo = {
        h: v for h, v in by_patch.items()
        if len({_repo(r["instance_id"]) for r in v}) > 1
    }

    total = len(all_rows)
    resolved = sum(1 for _, r in all_rows if r["outcome"] is True)
    empty = sum(1 for _, r in all_rows if r["patch_empty"])
    resolved_empty = sum(
        1 for _, r in all_rows if r["patch_empty"] and r["outcome"] is True
    )
    check = json.loads(
        (FROZEN / "swesmith-patch-check.json").read_text(encoding="utf-8")
    )
    widest = max(check["groups"], key=lambda g: len(g["rows"]))
    return {
        "revision": splits["swesmith-tool"]["revision"],
        "rows": total,
        "split_rows": {slug: len(doc["rows"]) for slug, doc in splits.items()},
        "resolved": resolved,
        "duplicate_groups": len(duplicate_groups_),
        "label_disagreeing_groups": label_disagreeing,
        "tool_xml_overlap": tool_xml_overlap,
        "xml_identical_duplicate_rows": xml_identical_dupes,
        "empty_rate": empty / total,
        "resolved_empty_rate": resolved_empty / resolved,
        "cross_repo_patch_groups": len(cross_repo),
        "cross_repo_patch_rows": sum(len(v) for v in cross_repo.values()),
        "check_groups": check["groups_checked"],
        "check_nontrivial": check["groups_nontrivial"],
        "check_foreign": check["groups_with_a_row_whose_patch_touches_foreign_paths"],
        "check_failures": len(check["failures"]),
        "check_total_cross_repo": check["cross_repo_groups_total"],
        "widest_rows": len(widest["rows"]),
        "widest_bytes": widest["rows"][0]["patch_bytes"],
        "widest_repos": sorted({r["repo"] for r in widest["rows"]}),
    }


def _tarsur_summary() -> dict:
    """The registry row for the dataset audited before this module existed.

    Derived from its frozen evidence so the registry cannot drift from it; the
    full analysis stays in research/OUTCOME_AUDIT.md.
    """
    document = json.loads(TARSUR.read_text(encoding="utf-8"))
    arms = document["arms"]
    rows = sum(len(v) for v in arms.values())
    unconfirmed = [
        arm for arm, arm_rows in arms.items()
        if all(isinstance(r["scores_resolved"], str) for r in arm_rows)
    ]
    return {"rows": rows, "arms": len(arms), "unconfirmed_arms": unconfirmed}


def _comparable(openr1: dict) -> int:
    """Cases where both sides reduce to one unambiguous number, which is the
    only subset the boxed-answer comparison can speak about."""
    verdicts = openr1["answer_check"]["verdicts"]
    return (verdicts.get("both_numeric_and_differ", 0)
            + verdicts.get("matches_published_answer", 0))


def openr1_math_summary() -> dict:
    """Two verification columns arranged so they can never be compared."""
    import random

    document = _load("openr1-math")
    rows = document["rows"]

    aligned = [r for r in rows if not r["misaligned"]]
    dual = [r for r in aligned if r["judge"] is not None]
    solo = [r for r in aligned if r["judge"] is None]

    # The selection that makes a paired statistic impossible: on every row
    # carrying both columns the symbolic checker found nothing correct, so
    # it has no variance there. A first pass computed Cohen's kappa over
    # these rows and got -0.000, which is what a constant always scores.
    violations = sum(1 for r in dual if any(r["symbolic"]))

    dual_generations = sum(len(r["judge"]) for r in dual)
    accepted = sum(sum(r["judge"]) for r in dual)
    solo_generations = sum(len(r["symbolic"]) for r in solo)
    solo_correct = sum(sum(r["symbolic"]) for r in solo)

    # Problems cluster their generations, so the bootstrap resamples
    # problems. Treating generations as independent would give an interval
    # roughly half as wide as the data supports.
    random.seed(20260904)
    clusters = [(sum(r["judge"]), len(r["judge"])) for r in dual]
    draws = []
    for _ in range(400):
        picked = [clusters[random.randrange(len(clusters))] for _ in clusters]
        total = sum(d for _, d in picked)
        if total:
            draws.append(sum(n for n, _ in picked) / total)
    draws.sort()

    by_source: dict[str, list[int]] = {}
    for row in dual:
        bucket = by_source.setdefault(row["source"], [0, 0])
        bucket[0] += sum(row["judge"])
        bucket[1] += len(row["judge"])
    strata = sorted(
        (
            {"source": s, "generations": d, "accepted": n, "rate": n / d}
            for s, (n, d) in by_source.items() if d >= 200
        ),
        key=lambda s: -s["generations"],
    )

    answers = json.loads(
        (FROZEN / "openr1-math-answers.json").read_text(encoding="utf-8")
    )

    return {
        "rows": len(rows),
        "misaligned": len(rows) - len(aligned),
        "answer_check": answers,
        "dual_signal_rows": len(dual),
        "symbolic_only_rows": len(solo),
        "selection_violations": violations,
        "count_tracks_judge": sum(
            1 for r in dual if sum(r["judge"]) == r["count"]
        ),
        "count_tracks_symbolic": sum(
            1 for r in solo if sum(r["symbolic"]) == r["count"]
        ),
        "dual_generations": dual_generations,
        "judge_accepted": accepted,
        "judge_acceptance_rate": accepted / dual_generations,
        "acceptance_ci": [draws[int(0.025 * len(draws))],
                          draws[int(0.975 * len(draws))]],
        "symbolic_only_rate": solo_correct / solo_generations,
        "admitted_on_judge_alone": sum(1 for r in dual if r["count"] > 0),
        "strata": strata,
        "revision": document["revision"],
        "parquet_revision": document["parquet_revision"],
        "license": document["license"],
    }


#: Every section of research/CORPUS.md, in the order it appears. This was
#: one 569-line list literal with loops spliced through it, so a heading
#: in the rendered page could only be traced back to the code that made
#: it by scrolling until the prose matched. One function per heading now.

def _entry_preamble(coderforge: dict, cf_re: dict, hle: dict, openr1: dict, cogym: dict, ptb: dict, smith: dict, sweagent: dict, openhands: dict, jetbrains: dict, tarsur: dict) -> list[str]:
    """The header and the registry table: one row per dataset audited."""
    out = [
        "# The corpus: public agent-trajectory datasets, audited",
        "",
        "Every dataset here was audited under the same discipline:",
        "content-free evidence frozen at a named revision, checks from the",
        "same family, and a refusal to guess at what the evidence does not",
        "establish, excluded and counted instead. A clean bill",
        "is a result, recorded with the same care as a defect; an auditor that",
        "only ever finds problems is indistinguishable from one that",
        "manufactures them.",
        "",
        "What the entries say jointly, rather than one at a time, is in",
        "[what the audits say together](PATTERNS.md).",
        "",
        "Every result here is also in the [findings index](FINDINGS.md), one",
        "citable line each with a stable identifier, a priority date, and the",
        "command that checks it.",
        "",
        "Entries are open to third parties under one written contract:",
        "[contributing an audit](../docs/contributing-an-audit.md). An entry",
        "that satisfies it gets merged no matter who submits it; one that",
        "does not gets returned no matter who submits it, including us.",
        "",
        "Each dataset is an independent public upload; an arm or model name",
        "inside one identifies a set of runs in that dataset, not a number any",
        "vendor published, and nothing here is a measurement of a model.",
        "",
        "| dataset | revision | rows | what the audit found |",
        "|---|---|---:|---|",
        (
            f"| [tarsur385/swebench-verified-trajectories]"
            f"(https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) "
            f"| `{TARSUR_REVISION[:8]}` | {tarsur['rows']:,} "
            f"| {len(tarsur['unconfirmed_arms'])} of {tarsur['arms']} arms never confirmed by its "
            "cross-check; one duplicated arm pair, labels 91.2% self-consistent "
            "([full audit](OUTCOME_AUDIT.md)) |"
        ),
        (
            "| [togethercomputer/CoderForge-Preview-32B…]"
            "(https://huggingface.co/datasets/togethercomputer/"
            "CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories) "
            f"| `{coderforge['revision'][:8]}` | {len(coderforge['rows'])} "
            "| clean: reward re-derives from the raw logs on all "
            f"{cf_re['parsed']} parseable rows |"
        ),
        (
            "| [FUSE-verifiers/HLE-Verifications]"
            "(https://huggingface.co/datasets/FUSE-verifiers/HLE-Verifications) "
            f"| `{hle['revision'][:8]}` | {hle['questions']} "
            f"| seven models asked to verify correctness reach"
            f" within-question AUC {hle['worst']['auc']:.3f} to"
            f" {hle['best']['auc']:.3f} against a checkable answer; four of"
            " the seven have intervals containing 0.5 |"
        ),
        (
            "| [open-r1/OpenR1-Math-220k]"
            "(https://huggingface.co/datasets/open-r1/OpenR1-Math-220k) "
            f"| `{openr1['revision'][:8]}` | {openr1['rows']:,} "
            f"| {openr1['dual_signal_rows']:,} problems entered the published "
            "training set on a model judge's word alone, on rows where the "
            "symbolic checker had found nothing correct |"
        ),
        (
            "| [SALT-NLP/cogym-real-trajectories]"
            "(https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) "
            f"| `{cogym['revision'][:8]}` | {cogym['rows']} "
            "| the only human-rated entry: one person's ratings of one "
            f"session agree exactly {cogym['pairs']['outcomeRating|agentRating']['exact']:.0%} "
            "of the time, and the communication rating exists on "
            f"{cogym['coverage']['communicationRating'] / cogym['rows']:.0%} of sessions |"
        ),
        (
            "| [aisa-group/PostTrainBench-Trajectories]"
            "(https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) "
            f"| `{ptb['revision'][:8]}` | {ptb['rows']:,} "
            f"| {ptb['unusable_accuracy']} runs carry no usable outcome; the "
            "contamination judge's apparent effect on scores is "
            f"{ptb['overstatement']:.1f}x smaller once benchmark composition "
            "is held fixed |"
        ),
        (
            "| [SWE-bench/SWE-smith-trajectories]"
            "(https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) "
            f"| `{smith['revision'][:8]}` | {smith['rows']:,} "
            f"| labels self-consistent across every duplicate; the `patch` "
            f"column is not row-aligned ({smith['cross_repo_patch_groups']} "
            "verbatim cross-repository patch groups); "
            f"{smith['xml_identical_duplicate_rows']:,} duplicate rows in one "
            "split |"
        ),
        (
            "| [nebius/SWE-agent-trajectories]"
            "(https://huggingface.co/datasets/nebius/SWE-agent-trajectories) "
            f"| `{sweagent['revision'][:8]}` | {sweagent['rows']:,} "
            "| clean: every coherence probe passes; resolved rows always "
            "carry a patch and evaluation logs; no duplicate transcripts |"
        ),
        (
            "| [nebius/SWE-rebench-openhands-trajectories]"
            "(https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories) "
            f"| `{openhands['revision'][:8]}` | {openhands['rows']:,} "
            "| clean labels; its recorded generated-test signal measures "
            f"kappa {openhands['kappa']:.2f} against adjudication over "
            f"{openhands['cross_present']:,} runs, and agree"
            f" {abs(openhands['agreement_minus_majority']) * 100:.1f} points"
            " less often than the majority-class baseline |"
        ),
        (
            "| [JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified]"
            "(https://huggingface.co/datasets/JetBrains-Research/"
            "agent-trajectories-swe-bench-test-minus-verified) "
            f"| `{jetbrains['revision'][:8]}` | {len(jetbrains['rows']):,} "
            f"| `resolved` column present, populated on 0 rows |"
        ),
    ]
    return out



def _entry_coderforge(cf_census: dict, cf_re: dict) -> list[str]:
    """A clean bill, re-derived from the raw evaluation logs."""
    out = [
        "",
        "## togethercomputer/CoderForge-Preview-32B, SWE-bench Verified, 500 rows",
        "",
        "The dataset ships the raw evaluation log and the graded-test lists",
        "beside every published `reward`, which permits the strongest check in",
        "this corpus: re-deriving each label from the log instead of comparing",
        "two fields the same pipeline wrote.",
        "",
        f"On every one of the **{cf_re['parsed']} rows the parser could fully",
        "read, the re-derived resolution equals the published reward**:",
        f"{len(cf_re['disagreements'])} disagreements. The published rate on those rows is",
        "confirmed, not merely self-consistent.",
        "",
        "The refusals, counted: "
        f"{cf_re['verdicts'].get('UNPARSED', 0)} rows use log formats the parser does not",
        f"read and {cf_re['verdicts'].get('AMBIGUOUS', 0)} depend on whether XFAIL",
        "counts as a pass, so they are",
        "excluded, not guessed. The first draft of this parser read only",
        "pytest's format and would have reported 186 false disagreements on",
        "Django's; a graded test the parser cannot locate now makes the row",
        "UNPARSED, never a finding.",
        "",
        f"Outcome census: {dict(sorted(cf_census.items()))}. No duplicate",
        "transcripts. No positive outcome on a run of one step or fewer.",
    ]
    return out



def _entry_hle(hle: dict) -> list[str]:
    """Seven graders against a checkable answer, ranked within question."""
    out = [
        "",
        "## FUSE-verifiers/HLE-Verifications, "
        f"{hle['questions']} questions and {hle['responses']:,} graded responses",
        "",
        "A second negative result on an outcome instrument, and deliberately",
        "not called a replication of AEL-2026-008. That entry measured",
        "whether an agent's own generated tests passing predicts hidden-test",
        "resolution: an execution signal, scored by agreement. This measures",
        "whether a model's quality score ranks answer-key correctness: a",
        "graded judgment, scored by rank. Different construct, different",
        "instrument class, different statistic. Two weak results about two",
        "different things are two results, not one confirmed twice, and the",
        "generality of the corpus rests on that distinction being kept.",
        "",
        "649 Humanity's Last Exam questions, 50 candidate responses each.",
        "Every response is marked correct or not by matching the published",
        "answer, and every response is scored 0 to 5 by seven models the",
        f"dataset calls verifiers. The base rate is {hle['base_rate']:.1%},",
        "so this is a near-balanced problem rather than one where a constant",
        "answer scores well.",
        "",
        "| verifier | scored | questions | within-question AUC | 95% CI"
        " | pooled |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for grader in sorted(hle["graders"], key=lambda g: g["auc"]):
        note = " *" if grader["indistinguishable_from_random"] else ""
        out.append(
            f"| `{grader['judge']}` | {grader['pairs']:,} "
            f"| {grader['questions_scored']} "
            f"| {grader['auc']:.3f}{note} | [{grader['low']:.3f}, "
            f"{grader['high']:.3f}] | {grader['pooled_auc']:.3f} |"
        )
    out += [
        "",
        "\\* interval contains 0.5, so that grader is not distinguishable",
        "from random at ranking within a question. Four of seven are.",
        "",
        "**Why within question, and why the pooled column is worse.** These",
        "graders exist to pick the right response among fifty candidates to",
        "the same question, so the question is the unit and the statistic is",
        "how well a grader ranks inside one. Pooling all responses into a",
        "single ranking lets a grader score well by detecting that a question",
        "is easy, which is not the job. This entry published the pooled",
        f"figure first, and it flattered every grader: the range was"
        f" {hle['pooled_worst']:.3f} to {hle['pooled_best']:.3f}"
        f" pooled and is {hle['worst']['auc']:.3f} to"
        f" {hle['best']['auc']:.3f} within question, with"
        f" `{hle['below_chance'][0] if hle['below_chance'] else ''}` crossing"
        " below chance. The gap between the two columns is the size of the",
        "between-question difficulty effect, which is why both are shown.",
        "",
        "**Why AUC and not an accuracy.** The graders score against a rubric",
        "the dataset does not publish, so no threshold can be justified from",
        "the data, and picking one would be choosing how generous to be. AUC",
        "asks only whether a higher score is more often a correct response,",
        "which is the weakest assumption under which a grader could be said",
        "to work at all. It is not comparable to the agreement floors in",
        "SPEC section 7.2, which govern chance-corrected agreement",
        "coefficients and held-out accuracy; there is no AUC floor in that",
        "contract, and reading one across metric families is the category",
        "error this project has already published once.",
        "",
        "**Why the intervals are wide.** 32,450 responses sit inside 649",
        "questions and are not independent, so the bootstrap resamples",
        "questions rather than responses. Treating the responses as",
        "independent would give intervals several times too tight and would",
        "be the error this corpus most often finds elsewhere. The draw count",
        "is 6,000, set by the resample-adequacy rule the frontier protocol",
        "already applies to a family this size; an earlier 400 put Monte",
        "Carlo noise in the published third decimal.",
        "",
        "**Prior work.** That model judges are imperfect is established:"
        " MT-Bench measured judge agreement with human preference,",
        "RewardBench scores reward models against it, and position,",
        "verbosity and self-preference bias each have a literature. What",
        "those measure is a judge against human preference on a curated set.",
        "This measures a shipped dataset's own scoring columns against an",
        "answer key, per question, at a pinned revision, and reports what a",
        "consumer of that dataset would get. The result is a census of",
        "published data, not a leaderboard entry, and it is not evidence",
        "that model grading cannot work.",
        "",
        "**What it does not establish.** Every response was generated by one",
        "model, so this measures graders on that model's output rather than",
        "on output in general. The ground truth is exact matching against a",
        "published answer, with a model used to parse answer formats, so it",
        "is checkable but not untouched by a model. HLE is adversarially",
        f"hard by construction. And one (question, grader) pair of"
        f" {hle['questions'] * len(hle['graders']):,}",
        "was excluded because that grader scored 47 of 50 responses and",
        "nothing in the data says which 47; the alignment is unknowable, so",
        "it is dropped and counted rather than zipped, which would have",
        "silently truncated to the shorter list.",
        "",
        "**One grader is mostly absent, and it is the top row.**"
        f" `gemini-3-flash` carries no score on"
        f" {next(g['null_scores'] for g in hle['graders'] if g['judge'] == 'gemini-3-flash'):,}"
        " of the 32,450 responses, scoring"
        f" {next(g['questions_scored'] for g in hle['graders'] if g['judge'] == 'gemini-3-flash')}"
        " of 538 rankable questions. Its figure is computed on the subset it",
        "did score, the missingness is not random with respect to outcome,",
        "and the direction of the resulting bias is unknown. It is left in",
        "the table with its coverage stated rather than dropped, because",
        "dropping the highest scorer without saying so would be the more",
        "flattering choice.",
        "",
        "Evidence: [frozen/hle-verifiers.json](corpus/frozen/hle-verifiers.json),",
        "content-free, carrying the SHA-256 of the source file it read.",
    ]
    return out



def _entry_openr1(openr1: dict) -> list[str]:
    """Two verification columns arranged so they can never be compared."""
    out = [
        "",
        "## open-r1/OpenR1-Math-220k, "
        f"{openr1['rows']:,} problems in a published training set",
        "",
        "The two entries above needed a rare kind of dataset, one shipping a",
        "proxy signal and a checkable one on the same rows. This dataset",
        "appears to be a third. It carries `correctness_math_verify`, a",
        "symbolic check against the published answer, and",
        "`correctness_llama`, a 70B model asked the same question, both",
        "attached to the same generations.",
        "",
        "They cannot be compared. The judge was run only where the symbolic",
        "check had already found nothing correct, and the freeze bears that",
        f"out exactly: across the {openr1['dual_signal_rows']:,} rows carrying both columns, the",
        "number with even one symbolically correct generation is",
        f"{openr1['selection_violations']}. The symbolic column is constant there, and a constant",
        "agrees with everything at chance. A first pass computed Cohen's",
        "kappa over these rows, got -0.000, and nearly published it.",
        "",
        "What survives is structural, and it matters more than the statistic",
        "would have. This is training data, not an evaluation. The filtering",
        "field `correctness_count` equals the judge's count on all",
        f"{openr1['count_tracks_judge']:,} dual-signal rows and the symbolic count on all",
        f"{openr1['count_tracks_symbolic']:,} others, without exception. So"
        f" {openr1['admitted_on_judge_alone']:,} problems,",
        f"{openr1['admitted_on_judge_alone'] / openr1['rows']:.1%} of the published set, are present only because the",
        "judge overruled a checker that had rejected every candidate. The",
        f"judge accepted {openr1['judge_accepted']:,} of {openr1['dual_generations']:,} rejected generations,",
        f"{openr1['judge_acceptance_rate']:.1%} (95% CI"
        f" {openr1['acceptance_ci'][0]:.1%} to {openr1['acceptance_ci'][1]:.1%}, bootstrapped over",
        "problems, since generations cluster inside them). The rate is flat",
        f"across every source stratum, {min(s['rate'] for s in openr1['strata']):.1%} to"
        f" {max(s['rate'] for s in openr1['strata']):.1%}, so it is not one",
        "problem set's quirk.",
        "",
        "This is not evidence that the judge is wrong. A symbolic checker",
        "that cannot parse a valid answer and a judge that waves through an",
        "invalid one produce the same two columns. Distinguishing them needs",
        "the answers themselves, so a verification pass re-fetched",
        f"{sum(openr1['answer_check']['verdicts'].values()):,} admitted generations, selected by hash rank,",
        "every shard checked against the SHA-256 the freeze recorded, and",
        "compared the final boxed answer with the published one:",
        "",
    ]
    for verdict, count in sorted(
        openr1["answer_check"]["verdicts"].items(), key=lambda kv: -kv[1]
    ):
        out.append(f"- {verdict.replace('_', ' ')}: {count}")
    out += [
        "",
        "It does not settle the question, and it is reported as failing to.",
        "Most of the gap is shape rather than substance: a generation boxing",
        "a multiple-choice letter against a published value, or a published",
        "answer carrying several roots at once. Of the"
        f" {sum(openr1['answer_check']['verdicts'].values())} checked, only"
        f" {_comparable(openr1)} reduce to an unambiguous number on both"
        " sides at all, and of those"
        f" {openr1['answer_check']['verdicts'].get('both_numeric_and_differ', 0)}"
        f" disagree: {openr1['answer_check']['verdicts'].get('both_numeric_and_differ', 0) / _comparable(openr1):.0%}"
        " of the comparable cases, not the"
        f" {openr1['answer_check']['verdicts'].get('both_numeric_and_differ', 0) / sum(openr1['answer_check']['verdicts'].values()):.1%}"
        " a reader gets by dividing into everything. This entry published"
        " the second figure first, which mixes \"could not compare\" into"
        " \"compared and agreed\" and is the denominator error the corpus"
        " finds elsewhere. The honest reading is that the comparable subset"
        " is small and mostly disagrees, and that answer-format"
        " heterogeneity is itself the likeliest reason the symbolic check"
        " failed here to begin with.",
        "Only where both sides reduce",
        "to a single unambiguous number and differ does the comparison bear",
        "on the judge, and this project has already published a",
        "re-adjudicator whose 186 disagreements were every one its own",
        "parser's blindness, so the parser here is treated as the third",
        "instrument in the room rather than the referee.",
        "",
        "The finding is therefore about provenance, not accuracy: the",
        "correctness of a third of a widely used training set rests on an",
        "unaudited model judgment, and the shipped columns are arranged so",
        "that no one downloading it can audit that judgment against the",
        "checkable signal sitting beside it.",
        "",
        "Evidence: [frozen/openr1-math.json](corpus/frozen/openr1-math.json)",
        "and [frozen/openr1-math-answers.json]"
        "(corpus/frozen/openr1-math-answers.json), content-free, carrying the",
        "SHA-256 of every parquet shard read.",
    ]
    return out



def _entry_cogym(cogym: dict) -> list[str]:
    """Human ratings against each other, the only non-coding entry."""
    out = [
        "",
        "## SALT-NLP/cogym-real-trajectories, "
        f"{cogym['rows']} human-agent sessions",
        "",
        "Every other entry here audits a coding agent, and every outcome",
        "instrument in them is automated: a cross-check column, a",
        "re-adjudication from logs, model-generated tests, an LLM judge.",
        "This is neither. 228 real human-agent collaboration sessions across",
        f"{', '.join(sorted(cogym['tasks']))}, where the outcome labels were",
        "typed by the person who was in the session. It is the one entry",
        "whose instrument is the thing every other instrument gets validated",
        "against.",
        "",
        "**What a rating covers.** Overall satisfaction is on every session,",
        "the artifact rating on "
        f"{cogym['coverage']['outcomeRating'] / cogym['rows']:.0%}, and the",
        "communication rating on only "
        f"{cogym['coverage']['communicationRating'] / cogym['rows']:.0%} - "
        f"{cogym['coverage']['communicationRating']} sessions, not 228. A",
        "reader computing communication quality from this dataset is",
        "computing it over a fifth of it, and the schema does not say so.",
        "",
        "**How far apart one person's answers run.** These are different",
        "questions, so they are not expected to match, and this is emphatically",
        "not a test-retest measurement: nobody was asked the same thing twice.",
        "What it bounds is how much a single number labelled \"the human",
        "rating\" can carry.",
        "",
        "| pair | n | exact | mean gap | 2+ apart | quadratic-weighted kappa |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, stats in cogym["pairs"].items():
        first, second = key.split("|")
        out.append(
            f"| {first} vs {second} | {stats['n']} "
            f"| {stats['exact']:.0%} | {stats['mean_absolute_difference']:.2f} "
            f"| {stats['two_or_more_apart']:.0%} | {stats['qwk']:.3f} |"
        )
    out += [
        "",
        "The artifact rating and overall satisfaction, the two closest of the",
        "three, land at quadratic-weighted kappa "
        f"{cogym['pairs']['outcomeRating|agentRating']['qwk']:.3f} - just",
        "above the 0.60 floor this package demands of an automated outcome",
        "instrument before it will issue a green decision, and they disagree",
        "by two points or more on "
        f"{cogym['pairs']['outcomeRating|agentRating']['two_or_more_apart']:.0%}",
        "of sessions. The point is not that people are unreliable. It is that",
        "human judgement of one session is several numbers rather than one,",
        "so any instrument validated against \"human agreement\" inherits",
        "whichever question was asked, and datasets rarely record which.",
        "",
        "**A suspicion that died at base rate**, recorded because the",
        "pipeline is supposed to kill these before they are published: very",
        "short sessions rated highly would suggest satisfaction untethered",
        f"from work done. There are {cogym['short_sessions']} sessions of",
        "three events or fewer, mean rating "
        f"{cogym['short_mean_rating']:.1f}. Four sessions establish nothing.",
        "",
        "Evidence: [frozen/cogym.json](corpus/frozen/cogym.json), content-free",
        "and more carefully than usual because these are real people - "
        "ratings, counts and hashes, never the query, the feedback text, or",
        "the event log.",
    ]
    return out



def _entry_posttrainbench(ptb: dict) -> list[str]:
    """A contamination effect that mostly survives pooling, and does not."""
    out = [
        "",
        "## aisa-group/PostTrainBench-Trajectories, "
        f"{ptb['rows']:,} autonomous runs",
        "",
        "The most-downloaded agent-trajectory dataset on the hub, and the",
        "only entry here that is not a table. Each row is a run in which an",
        "agent was given a base model, an evaluation script and ten hours on",
        "an H100, and had to make the model better: the open-ended shape the",
        "field keeps proposing as the successor to benchmarks. Three",
        "independent signals per run make it auditable - a measured accuracy",
        "from the evaluation script, an LLM judge's verdict on whether the",
        "agent contaminated its training data, and a wall clock against a",
        "priced budget.",
        "",
        "**A finding that does not survive its own stratification.**",
        "Contaminated runs score far better than clean ones:",
        f"a pooled difference of {ptb['pooled_difference']:+.3f} accuracy.",
        "Published as it stands, that is a headline about cheating paying",
        "twenty points. It is mostly composition. Contamination is not",
        f"spread evenly: {ptb['worst_rate']:.0%} of `{ptb['worst_benchmark']}`",
        f"runs are flagged, {ptb['worst_share_of_contamination']:.0%} of all",
        f"contamination sits there, and `{ptb['worst_benchmark']}` has a",
        f"clean-run mean of {ptb['worst_clean_mean']:.3f} against a corpus",
        "where most benchmarks sit near 0.2. Pooling therefore credits that",
        "benchmark's easiness to contamination. Holding benchmark fixed and",
        "weighting by size, the difference is",
        f"{ptb['stratified_difference']:+.3f} - smaller by a factor of",
        f"{ptb['overstatement']:.1f} - and contaminated runs beat clean ones",
        f"in only {ptb['benchmarks_where_contamination_helps']} of",
        f"{ptb['comparable_benchmarks']} benchmarks with enough of both to",
        "compare. The honest statement is that this dataset does not show",
        "contamination reliably paying, and that anyone computing the pooled",
        "number gets an answer an order of magnitude too large.",
        "",
        "**What is missing, counted rather than dropped.**",
        f"{ptb['no_metrics_file']} runs ship no metrics file and",
        f"{ptb['malformed_metrics']} ship one that is not valid JSON, so",
        f"{ptb['unusable_accuracy']} of {ptb['rows']:,} runs",
        f"({ptb['unusable_accuracy'] / ptb['rows']:.1%}) carry no usable",
        f"outcome at all. A further {ptb['unjudged']} runs carry no",
        "contamination verdict, so they are neither clean nor flagged; a",
        "leaderboard built from this dataset has to decide what to do with",
        "them, and the dataset does not say.",
        "",
        "**The judge is an instrument, and nothing here validates it.**",
        f"It flags {ptb['contaminated']} of {ptb['judged']:,} judged runs as",
        f"contaminated and {ptb['disallowed_model']} as having trained a",
        "disallowed base model. Those verdicts govern whether a run counts.",
        "No agreement measurement against human adjudication ships with the",
        "dataset, so the flags are unvalidated in exactly the way",
        "[AEL-2026-008](FINDINGS.md) measured elsewhere. This is a gap in",
        "what can be established, not a claim that the judge is wrong.",
        "",
        f"Median run length is {ptb['median_hours']:.1f} hours of H100 time",
        "against a ten-hour cap. Evidence:",
        "[frozen/posttrainbench.json](corpus/frozen/posttrainbench.json);",
        "every figure recomputes offline with `make corpus`.",
    ]
    return out



def _entry_swesmith(smith: dict) -> list[str]:
    """A patch column that is not row-aligned, and duplicated transcripts."""
    out = [
        "",
        "## SWE-bench/SWE-smith-trajectories, three splits, "
        f"{smith['rows']:,} rows",
        "",
        "The official SWE-bench organisation's training-trajectory release,",
        "behind their published SWE-agent-LM-32B. Its card's prose describes",
        "5,017 trajectories and its size category says 1K-10K; the dataset",
        f"serves {smith['rows']:,} rows ("
        + ", ".join(
            f"{n:,} {slug.split('-')[1]}"
            for slug, n in sorted(smith["split_rows"].items())
        )
        + ").",
        "",
        "**What is clean, stated with the same care as the defects.** The",
        "outcome labels agree with themselves everywhere: across all",
        f"{smith['duplicate_groups']:,} duplicate-transcript groups,",
        f"{smith['label_disagreeing_groups']} label disagreements. And the",
        "\"resolved with an empty patch\" suspicion the first rows raised",
        "dies at base rate: the patch field is empty on "
        f"{smith['empty_rate']:.1%} of all rows and "
        f"{smith['resolved_empty_rate']:.1%} of resolved ones, so emptiness",
        "is a population artifact of the column, not a property of the label.",
        "",
        "**Duplication.** The xml split contains",
        f"{smith['xml_identical_duplicate_rows']:,} rows that are verbatim",
        "duplicates of other rows in the same split, identical in id,",
        f"transcript, and label. {smith['tool_xml_overlap']:,} transcripts",
        "appear byte-identically in both the tool and xml splits, so",
        "training on both sees those examples twice. None involve ticks.",
        "",
        "**The `patch` column is not row-aligned.**",
        f"{smith['cross_repo_patch_groups']} distinct non-empty patch",
        f"contents, covering {smith['cross_repo_patch_rows']:,} rows, each",
        "appear verbatim under instances from two or more different",
        "repositories. A hash collision on a trivial diff would explain",
        "that, so a verification pass re-fetched every row of the first",
        f"{smith['check_groups']} hash-ranked groups of the",
        f"{smith['check_total_cross_repo']} and reduced each patch to",
        f"content-free facts: {smith['check_nontrivial']} of",
        f"{smith['check_groups']} are non-trivial unified diffs,",
        f"{smith['check_foreign']} contain rows whose patch touches paths",
        "foreign to the instance's repository under a deliberately generous",
        f"matcher, and one {smith['widest_bytes']}-byte patch appears under",
        f"{smith['widest_rows']} rows spanning "
        f"{' and '.join(smith['widest_repos'])}",
        f"({smith['check_failures']} fetch or hash failures). Whatever the",
        "column records, it is not reliably the fix for its row.",
        "",
        "The scope of that claim, stated precisely: the model was fine-tuned",
        "on `messages`, not `patch`, so this is a defect in an auxiliary",
        "column a consumer might filter or evaluate by, not evidence that",
        "the training signal or the labels are wrong. Evidence:",
        "[frozen/swesmith-*.json](corpus/frozen/) and",
        "[frozen/swesmith-patch-check.json](corpus/frozen/swesmith-patch-check.json);",
        "reproduce the verification with `python3 research/corpus/patch_check.py`.",
    ]
    return out



def _entry_sweagent(sweagent: dict) -> list[str]:
    """A clean bill across 80,036 rows."""
    out = [
        "",
        "## nebius/SWE-agent-trajectories, "
        f"{sweagent['rows']:,} rows",
        "",
        "SWE-agent runs over SWE-bench-style tasks with the outcome label,",
        "the generated patch, and the raw evaluation logs beside every row.",
        f"{sweagent['resolved']:,} of {sweagent['rows']:,} rows are marked",
        "resolved, and every coherence probe this corpus knows passes:",
        "",
        f"- All {sweagent['resolved']:,} resolved rows carry a non-empty",
        f"  patch ({sweagent['resolved_with_empty_patch']} exceptions) and",
        "  non-empty evaluation logs",
        f"  ({sweagent['resolved_with_empty_logs']} exceptions). Empty",
        f"  patches ({sweagent['unresolved_empty_patch']:,}) and empty logs",
        f"  ({sweagent['unresolved_empty_logs']:,}) occur only on unresolved",
        "  rows, under exactly the exit statuses that should produce them",
        "  (context exhaustion, early exit, submitted-no-patch).",
        f"- {sweagent['duplicate_transcript_groups']} duplicate transcripts",
        f"  across all {sweagent['rows']:,} rows.",
        "",
        "A clean bill, with its strength stated precisely: this is",
        "coherence, weaker than the CoderForge entry's re-adjudication,",
        "because the dataset does not ship the graded-test lists a",
        "re-derivation needs. One artifact of ours, recorded so nobody",
        "mistakes it for a finding: the frozen id is instance::model, which",
        f"repeats {sweagent['repeat_attempt_pairs']:,} times because the",
        "dataset legitimately holds several attempts per pair; the",
        "transcripts are all distinct.",
    ]
    return out



def _entry_openhands(sweagent: dict, openhands: dict) -> list[str]:
    """Model-generated tests against adjudication: the sharpest result here."""
    out = [
        "",
        "## nebius/SWE-rebench-openhands-trajectories, "
        f"{openhands['rows']:,} rows",
        "",
        "OpenHands runs where each row records the adjudicated `resolved`",
        "label and, on some rows, whether the model's own generated tests",
        "passed. The labels are coherent: only",
        f"{openhands['empty_patches']} empty patches, every one unresolved;",
        "runs that hit the iteration cap resolve at",
        f"{openhands['max_iteration_resolved'] / openhands['max_iteration_rows']:.0%}",
        f"against {openhands['resolved'] / openhands['rows']:.0%} overall;",
        f"{openhands['duplicate_transcript_groups']} duplicate transcripts.",
        "",
        "**What the dataset makes measurable is the interesting part.**",
        "Model-generated tests are widely proposed as a cheap outcome",
        "instrument. Here both signals sit on the same",
        f"{openhands['cross_present']:,} rows, which is a validity",
        "measurement at scale:",
        "",
        f"- Raw agreement {openhands['agreement']:.1%}, against a"
        f" majority-class baseline of"
        f" {openhands['majority_baseline']:.1%}: consulting the proxy is"
        f" **{openhands['agreement_minus_majority'] * 100:+.1f} points**"
        " against always answering with the commoner label.",
        f"- Cohen's kappa **{openhands['kappa']:.3f}**, 95% CI"
        f" [{openhands['kappa_low']:.3f}, {openhands['kappa_high']:.3f}]"
        f" bootstrapped over {openhands['kappa_clusters']:,} instances."
        " Reliably above zero and far too small to act on. This entry said"
        " \"indistinguishable from guessing\" before the interval existed,"
        " which was wrong in the direction of overstating: chance is zero"
        " and this excludes zero. The useful statement is the line above"
        " it, that the signal is worse than the baseline it has to beat.",
        "- Conditioned on the generated tests themselves being judged",
        f"  correct ({openhands['valid_n']:,} rows): kappa",
        f"  {openhands['valid_kappa']:.3f}, precision",
        f"  {openhands['valid_precision']:.3f}. Better, and still a sixth",
        "  of the 0.60 kappa floor this package requires of an outcome",
        "  instrument.",
        "- Where the generated tests were judged incorrect",
        f"  ({openhands['invalid_n']:,} rows): kappa",
        f"  {openhands['invalid_kappa']:.3f}, pure noise - and that is",
        "  the majority of rows carrying the signal.",
        "",
        "Scope, stated exactly: this measures the generated-test *method*,",
        "not a defect of the dataset - recording both signals side by side",
        "is what made the measurement possible at all, and the signal is",
        f"absent on {openhands['rows'] - openhands['cross_present']:,} rows,",
        "so nothing here extrapolates to them. Evidence:",
        "[frozen/nebius-sweagent.json](corpus/frozen/) and",
        "[frozen/nebius-openhands.json](corpus/frozen/); every figure",
        "recomputes offline.",
    ]
    return out



def _entry_jetbrains(jetbrains: dict, jb_census: dict, jb_cross: dict) -> list[str]:
    """An outcome column populated on no row at all."""
    out = [
        "",
        "## JetBrains-Research, SWE-bench test-minus-verified, 1,785 rows",
        "",
        f"The `resolved` column is null on all {len(jetbrains['rows']):,} rows. "
        f"{jb_cross.get('Submitted', 0):,} runs report",
        f"`exit_status` \"Submitted\" and {jb_cross.get('LimitsExceeded', 0)}",
        "\"LimitsExceeded\"; none carries an",
        "adjudicated outcome. That is not an accusation: publishing",
        "trajectories without scoring them is a legitimate choice, and the",
        "column is honestly null rather than defaulted to a flattering value.",
        "It is a warning to consumers: a resolution rate computed from this",
        "dataset divides by zero scored runs, and any figure quoted from it",
        "was made somewhere else.",
        "",
        "No duplicate transcripts. Outcome census: "
        f"{dict(sorted(jb_census.items()))}.",
    ]
    return out



def _entry_closing() -> list[str]:
    """How an entry gets here, and what the freeze refuses to copy."""
    out = [
        "",
        "## How an entry gets here",
        "",
        "`research/corpus/freeze.py` fetches rows at a revision bracketed by",
        "the repository SHA (refusing a snapshot that moved mid-fetch, a",
        "partial arm, or a truncated cell), keeps identifiers, outcome fields,",
        "step counts, and SHA-256 hashes of the content it refuses to copy,",
        "and, where raw logs ship beside graded-test lists, the",
        "re-adjudication verdict. `research/corpus/audit.py` renders this",
        "document from the frozen evidence alone; `make corpus` fails when the",
        "two disagree. No prompts, responses, patches, or logs are stored.",
        "",
    ]
    return out

def render() -> str:
    coderforge = _load("coderforge")
    jetbrains = _load("jetbrains")
    tarsur = _tarsur_summary()
    smith = swesmith_summary()
    ptb = posttrainbench_summary()
    cogym = cogym_summary()
    hle = hle_verifier_summary()
    openr1 = openr1_math_summary()
    sweagent = nebius_sweagent_summary()
    openhands = nebius_openhands_summary()

    cf_re = readjudication(coderforge)
    cf_census = outcome_census(coderforge)
    jb_census = outcome_census(jetbrains)
    jb_cross = Counter(row["cross"] for row in jetbrains["rows"])

    for slug, doc in (("coderforge", coderforge), ("jetbrains", jetbrains)):
        if duplicate_groups(doc) or degenerate_positives(doc):
            # Neither dataset currently trips these; if a re-freeze ever does,
            # the registry must say so rather than render a stale clean bill.
            raise AssertionError(f"{slug}: new finding in frozen evidence; rewrite its entry")

    lines: list[str] = []
    lines += _entry_preamble(coderforge, cf_re, hle, openr1, cogym, ptb, smith, sweagent, openhands, jetbrains, tarsur)
    lines += _entry_coderforge(cf_census, cf_re)
    lines += _entry_hle(hle)
    lines += _entry_openr1(openr1)
    lines += _entry_cogym(cogym)
    lines += _entry_posttrainbench(ptb)
    lines += _entry_swesmith(smith)
    lines += _entry_sweagent(sweagent)
    lines += _entry_openhands(sweagent, openhands)
    lines += _entry_jetbrains(jetbrains, jb_census, jb_cross)
    lines += _entry_closing()
    return "\n".join(lines)


def main() -> int:
    sys.stdout.write(render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
