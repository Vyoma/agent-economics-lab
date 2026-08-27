"""Eval for the Kimi outcome judge.

The judge decides `acceptable`, which is the input the economics are most
sensitive to: swapping label sources on the support fixture moved the verdict from
ASSIST to STOP and flipped the sign of net value. A component with that much
leverage and no eval is the weakest link in the pipeline.

This scores judge labels against a hand-authored eval set whose expected labels
follow from the rubric's own weighting. It reports agreement, per-class precision
and recall, a confusion matrix, and a per-category breakdown so a failure is
diagnosable rather than just low.

What it does not do: establish accuracy against production ground truth. The
expected labels are a claim, and constructed cases are easier than real ones.
Treat a strong score as a smoke test, not as permission to skip human agreement
checks on your own data.

    python3 kimi_eval.py                  # live, needs MOONSHOT_API_KEY
    python3 kimi_eval.py --predictions p.json   # score a saved run, no network
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
EVAL_SET = ROOT / "research/eval/judge-eval-set.json"
RUBRIC = ROOT / "examples/kimi-judge/rubric.json"


@dataclass(frozen=True)
class Metrics:
    """Agreement between predicted and expected labels.

    `positive` is "acceptable". Recall on the negative class matters most here: a
    judge that waves through an unacceptable outcome inflates the acceptable rate
    and can turn a STOP into a SCALE.
    """

    total: int
    scored: int
    errors: int
    agreements: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @property
    def agreement_rate(self) -> float:
        return self.agreements / self.scored if self.scored else 0.0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        if not (self.precision + self.recall):
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    @property
    def negative_recall(self) -> float:
        """Share of unacceptable cases correctly refused."""
        denominator = self.true_negative + self.false_positive
        return self.true_negative / denominator if denominator else 0.0

    @property
    def false_accept_rate(self) -> float:
        """The dangerous error: unacceptable work labelled acceptable."""
        denominator = self.true_negative + self.false_positive
        return self.false_positive / denominator if denominator else 0.0


def load_eval_set(path: Path = EVAL_SET) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def score(
    cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, bool | None],
) -> Metrics:
    """Compare predictions to expected labels.

    A `None` prediction is an error, counted separately rather than folded into
    the confusion matrix. Scoring a failed call as a rejection would make an
    outage look like strictness.
    """
    tp = fp = tn = fn = errors = 0
    for case in cases:
        predicted = predictions.get(case["task_id"])
        if predicted is None:
            errors += 1
            continue
        expected = bool(case["expected_acceptable"])
        if expected and predicted:
            tp += 1
        elif expected and not predicted:
            fn += 1
        elif not expected and predicted:
            fp += 1
        else:
            tn += 1
    return Metrics(
        total=len(cases),
        scored=tp + fp + tn + fn,
        errors=errors,
        agreements=tp + tn,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
    )


def by_category(
    cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, bool | None],
) -> dict[str, dict[str, int]]:
    buckets: dict[str, dict[str, int]] = {}
    for case in cases:
        bucket = buckets.setdefault(
            case["category"], {"cases": 0, "agreed": 0, "errors": 0}
        )
        bucket["cases"] += 1
        predicted = predictions.get(case["task_id"])
        if predicted is None:
            bucket["errors"] += 1
        elif bool(predicted) == bool(case["expected_acceptable"]):
            bucket["agreed"] += 1
    return buckets


def disagreements(
    cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, bool | None],
) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        predicted = predictions.get(case["task_id"])
        if predicted is None or bool(predicted) == bool(case["expected_acceptable"]):
            continue
        rows.append(
            {
                "task_id": case["task_id"],
                "category": case["category"],
                "expected": bool(case["expected_acceptable"]),
                "predicted": bool(predicted),
                "kind": (
                    "false accept" if predicted else "false reject"
                ),
            }
        )
    return rows


def render_report(
    document: Mapping[str, Any],
    predictions: Mapping[str, bool | None],
    *,
    model: str,
    reasoning_effort: str,
) -> str:
    cases = document["cases"]
    metrics = score(cases, predictions)
    width = 70
    lines = [
        "=" * width,
        "  JUDGE EVAL  agreement with hand-authored expected labels",
        "=" * width,
        f"  eval set   {document['eval_id']}@{document['eval_version']}",
        f"  rubric     {document['rubric_id']}",
        f"  judge      {model}  reasoning_effort={reasoning_effort}",
        (
            f"  cases      {metrics.total} "
            f"({document['acceptable_cases']} acceptable, "
            f"{document['unacceptable_cases']} unacceptable)"
        ),
        "",
        "  AGREEMENT",
        "  " + "-" * (width - 4),
        f"    agreement rate        {metrics.agreement_rate:>7.1%}  "
        f"({metrics.agreements}/{metrics.scored})",
        f"    precision (accept)    {metrics.precision:>7.1%}",
        f"    recall (accept)       {metrics.recall:>7.1%}",
        f"    f1 (accept)           {metrics.f1:>7.1%}",
        f"    recall (reject)       {metrics.negative_recall:>7.1%}",
        f"    false-accept rate     {metrics.false_accept_rate:>7.1%}  "
        "<- inflates acceptable_rate",
        f"    judge errors          {metrics.errors:>7}",
        "",
        "  CONFUSION MATRIX",
        "  " + "-" * (width - 4),
        "                      predicted accept   predicted reject",
        f"    expected accept   {metrics.true_positive:>16}   "
        f"{metrics.false_negative:>16}",
        f"    expected reject   {metrics.false_positive:>16}   "
        f"{metrics.true_negative:>16}",
        "",
        "  BY CATEGORY",
        "  " + "-" * (width - 4),
    ]
    for category, bucket in sorted(by_category(cases, predictions).items()):
        rate = bucket["agreed"] / bucket["cases"] if bucket["cases"] else 0.0
        note = f"  errors={bucket['errors']}" if bucket["errors"] else ""
        lines.append(
            f"    {category:<24} {bucket['agreed']}/{bucket['cases']}  "
            f"{rate:>6.0%}{note}"
        )

    rows = disagreements(cases, predictions)
    lines.extend(["", "  DISAGREEMENTS", "  " + "-" * (width - 4)])
    if not rows:
        lines.append("    none")
    for row in rows:
        lines.append(
            f"    {row['task_id']:<10} {row['category']:<24} {row['kind']}"
        )
    lines.extend(
        [
            "",
            "  " + document["claim_boundary"].replace("\n", " "),
            "=" * width,
            "",
        ]
    )
    return "\n".join(lines)


def run_live(
    document: Mapping[str, Any], *, model: str, reasoning_effort: str
) -> tuple[dict[str, bool | None], dict[str, Any]]:
    """Judge every eval case through the shipping judge path."""
    import time

    from agent_economics import kimi_client
    from agent_economics.kimi_judge import (
        _build_system_prompt,
        _build_user_message,
        _call_kimi,
        _validate_rubric,
        _verdict_schema,
    )

    api_key = kimi_client.require_api_key()
    kimi_client.validate_reasoning_effort(reasoning_effort)
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    _validate_rubric(rubric)
    system_prompt = _build_system_prompt(rubric)
    response_format = _verdict_schema(rubric)

    cases = document["cases"]
    timeout = kimi_client.timeout_for(reasoning_effort)
    # Announce before the first request. K3 at max effort can reason for minutes,
    # and silence during that window is indistinguishable from a hang.
    print(
        f"  judging {len(cases)} cases with {model} at "
        f"reasoning_effort={reasoning_effort}",
        flush=True,
    )
    print(
        f"  per-call timeout {timeout}s, up to {kimi_client.MAX_ATTEMPTS} attempts. "
        "Deep reasoning is slow; expect minutes, not seconds.",
        flush=True,
    )
    print(flush=True)

    predictions: dict[str, bool | None] = {}
    verdicts: dict[str, Any] = {}
    started = time.monotonic()
    for index, case in enumerate(cases, 1):
        task_id = case["task_id"]
        case_started = time.monotonic()
        try:
            verdict = _call_kimi(
                system_prompt,
                _build_user_message(task_id, case["output"], case["context"]),
                api_key=api_key,
                model=model,
                response_format=response_format,
                reasoning_effort=reasoning_effort,
                rubric=rubric,
            )
            predictions[task_id] = bool(verdict["acceptable"])
            verdicts[task_id] = verdict
            mark = "accept" if predictions[task_id] else "reject"
            agree = (
                "ok  " if predictions[task_id] == case["expected_acceptable"]
                else "MISS"
            )
            print(
                f"  {index:>2}/{len(cases)} {agree} {task_id:<10} {mark:<7} "
                f"score={verdict.get('overall_score')}  "
                f"{time.monotonic() - case_started:.0f}s",
                flush=True,
            )
        except Exception as error:
            predictions[task_id] = None
            verdicts[task_id] = {"error": str(error)}
            print(
                f"  {index:>2}/{len(cases)} ERR  {task_id:<10} "
                f"{time.monotonic() - case_started:.0f}s  {error}",
                flush=True,
            )
    print(f"\n  elapsed {time.monotonic() - started:.0f}s", flush=True)
    return predictions, verdicts


def _report_stability(
    document: Mapping[str, Any],
    *,
    repeats: int,
    model: str,
    reasoning_effort: str,
) -> int:
    """Judge every case `repeats` times and report whether verdicts hold.

    A verdict two hundredths from the threshold is not a measurement, it is a coin
    toss with a bias. Reporting a single agreement rate over such cases overstates
    what is known, so this separates stable verdicts from unstable ones.
    """
    runs: list[dict[str, bool | None]] = []
    scores: dict[str, list[float]] = {}
    for attempt in range(1, repeats + 1):
        print(f"  run {attempt}/{repeats}", flush=True)
        predictions, verdicts = run_live(
            document, model=model, reasoning_effort=reasoning_effort
        )
        runs.append(predictions)
        for task_id, verdict in verdicts.items():
            value = verdict.get("overall_score")
            if isinstance(value, (int, float)):
                scores.setdefault(task_id, []).append(float(value))
        print()

    width = 70
    print("=" * width)
    print("  VERDICT STABILITY  same case, repeated judgments")
    print("=" * width)
    print(f"  {repeats} runs of {len(document['cases'])} cases")
    print()
    print(f"  {'case':<12} {'expected':<9} {'verdicts':<12} {'scores':<28} stable")
    print("  " + "-" * (width - 4))
    unstable = 0
    for case in document["cases"]:
        task_id = case["task_id"]
        observed = [run.get(task_id) for run in runs]
        distinct = {value for value in observed if value is not None}
        stable = len(distinct) <= 1
        unstable += not stable
        seen = scores.get(task_id, [])
        spread = (
            f"{min(seen):.2f}-{max(seen):.2f}" if seen else "n/a"
        )
        accepts = sum(1 for value in observed if value is True)
        print(
            f"  {task_id:<12} {case['expected_acceptable']!s:<9} "
            f"{accepts}/{len(observed)} accept  {spread:<28} "
            f"{'yes' if stable else 'NO'}"
        )
    print()
    if unstable:
        print(
            f"  {unstable} case(s) changed verdict between identical runs. A single "
            "agreement"
        )
        print("  rate over those cases is noise, not a measurement.")
    else:
        print("  Every verdict held across all runs.")
    print("=" * width)
    return 1 if unstable else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", type=Path, default=EVAL_SET)
    parser.add_argument(
        "--predictions",
        type=Path,
        help="Score a saved {task_id: bool} JSON file instead of calling the API.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help=(
            "Judge each case N times and report verdict stability and score spread. "
            "A case near the threshold can flip between runs, which makes a single "
            "score an unreliable summary."
        ),
    )
    parser.add_argument(
        "--only",
        help="Comma-separated task ids to judge. Re-check one disagreement cheaply.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Judge only the first N cases. Use for a cheap smoke run first.",
    )
    parser.add_argument("--model", default="kimi-k3")
    parser.add_argument(
        "--reasoning-effort", choices=("low", "high", "max"), default="max"
    )
    parser.add_argument("--output", type=Path, help="Write the report here.")
    parser.add_argument(
        "--save-predictions", type=Path, help="Write raw labels for later scoring."
    )
    parser.add_argument(
        "--save-verdicts",
        type=Path,
        help="Write full verdicts including rationales and per-criterion scores.",
    )
    parser.add_argument(
        "--min-agreement",
        type=float,
        help="Exit non-zero if the agreement rate falls below this.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document = load_eval_set(args.eval_set)
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        selected = [c for c in document["cases"] if c["task_id"] in wanted]
        missing = wanted - {c["task_id"] for c in selected}
        if missing:
            print(f"Unknown task ids: {sorted(missing)}")
            return 2
        document = dict(document)
        document["cases"] = selected
        document["case_count"] = len(selected)
        document["acceptable_cases"] = sum(
            1 for c in selected if c["expected_acceptable"]
        )
        document["unacceptable_cases"] = len(selected) - document["acceptable_cases"]
    if args.limit:
        limited = list(document["cases"])[: args.limit]
        document = dict(document)
        document["cases"] = limited
        document["case_count"] = len(limited)
        document["acceptable_cases"] = sum(
            1 for c in limited if c["expected_acceptable"]
        )
        document["unacceptable_cases"] = len(limited) - document["acceptable_cases"]

    if args.predictions:
        raw = json.loads(args.predictions.read_text(encoding="utf-8"))
        predictions: dict[str, bool | None] = {
            key: (None if value is None else bool(value))
            for key, value in raw.items()
        }
    elif args.repeat > 1:
        return _report_stability(
            document,
            repeats=args.repeat,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
    else:
        predictions, verdicts = run_live(
            document, model=args.model, reasoning_effort=args.reasoning_effort
        )
        print()
        # Show the reasoning for anything that disagreed, while it is still free.
        for row in disagreements(document["cases"], predictions):
            verdict = verdicts.get(row["task_id"], {})
            print(f"  {row['task_id']} {row['kind']}:")
            print(f"    overall_score    {verdict.get('overall_score')}")
            print(f"    criterion_scores {verdict.get('criterion_scores')}")
            print(f"    rationale        {verdict.get('rationale')}")
            print()

    report = render_report(
        document,
        predictions,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
    )
    print(report, end="")

    if args.save_verdicts and not args.predictions:
        args.save_verdicts.parent.mkdir(parents=True, exist_ok=True)
        args.save_verdicts.write_text(
            json.dumps(verdicts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.save_predictions:
        args.save_predictions.parent.mkdir(parents=True, exist_ok=True)
        args.save_predictions.write_text(
            json.dumps(predictions, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")

    metrics = score(document["cases"], predictions)
    if args.min_agreement is not None and metrics.agreement_rate < args.min_agreement:
        print(
            f"Agreement {metrics.agreement_rate:.1%} is below the required "
            f"{args.min_agreement:.1%}."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
