"""
Task completion rate versus economic verdict, on the checked-in Claude Code
conversion fixture.

A transcript reader answers "how many tasks finished acceptably?" The decision
contract answers "does the economics justify scaling this?" Those are different
questions, and this script prints both for the same evidence so the gap is
visible in one screen.

The fixture is `examples/claude-code/bundle.json`: a synthetic, content-redacted
Claude Code session that exercises the conversion contract. It is not a captured
production session, and nothing here is a prevalence or ROI estimate. The point
is the shape of the gap, not its size.

Run:
    python3 completion_vs_verdict.py
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

from agent_economics import CheckStatus, Decision, evaluate_bundle
from agent_economics.adapters import load_normalized_json_bundle

ROOT = Path(__file__).resolve().parent
BUNDLE_PATH = ROOT / "examples" / "claude-code" / "bundle.json"

DECISION_LABELS = {
    Decision.SCALE: "SCALE",
    Decision.ASSIST: "ASSIST",
    Decision.STOP: "STOP",
    Decision.INCOMPLETE: "INCOMPLETE",
}


def render_report(bundle_path: Path = BUNDLE_PATH) -> str:
    bundle = load_normalized_json_bundle(bundle_path)
    case = evaluate_bundle(bundle)
    policy = bundle.policy
    baseline = bundle.baseline

    outcomes = list(bundle.outcomes.values())
    task_count = len(outcomes)
    acceptable_count = sum(outcome.acceptable for outcome in outcomes)
    completion_rate = acceptable_count / task_count if task_count else 0.0
    trace_cost = math.fsum(
        event.direct_cost_usd or 0.0 for event in bundle.events
    )
    failed_gates = [
        result
        for result in case.check_results
        if result.status is CheckStatus.FAIL and result.on_failure is not None
    ]

    width = 66
    lines = [
        "=" * width,
        "  COMPLETION RATE VS ECONOMIC VERDICT",
        (
            f"  fixture: {bundle_path.parent.name}/{bundle_path.name}  "
            f"({len(bundle.events)} events, {task_count} tasks, redacted)"
        ),
        "=" * width,
        "",
        "  WHAT A TRANSCRIPT READER SEES",
        "  " + "-" * 58,
    ]
    for outcome in outcomes:
        marker = "ok  " if outcome.acceptable else "not "
        lines.append(
            f"    [{marker}] {outcome.task_id[:40]:<40} "
            f"{'acceptable' if outcome.acceptable else 'not acceptable'}"
        )
    lines.extend(
        [
            "",
            (
                f"    completion rate: {completion_rate:.0%} "
                f"({acceptable_count}/{task_count} tasks)"
            ),
            "",
            "  WHAT THE DECISION CONTRACT SAYS",
            "  " + "-" * 58,
            f"    decision: {DECISION_LABELS[case.decision]}",
            "",
            "  Gate results:",
        ]
    )
    for result in case.check_results:
        marker = "FAIL" if result.status is CheckStatus.FAIL else "pass"
        route = f"  -> {result.on_failure.value}" if result.on_failure else ""
        lines.append(f"    [{marker}] {result.check_id}: {result.message}{route}")

    lines.extend(
        [
            "",
            "  Economics:",
            f"    {'metric':<38} {'agent':>10} {'baseline':>11}",
            "    " + "-" * 60,
            (
                f"    {'acceptable rate':<38} {case.acceptable_rate:>9.1%} "
                f"{baseline.acceptable_rate:>10.1%}"
            ),
        ]
    )
    if math.isfinite(case.cost_per_acceptable_outcome_usd):
        lines.append(
            f"    {'cost per acceptable outcome':<38} "
            f"${case.cost_per_acceptable_outcome_usd:>8.4f} "
            f"${baseline.cost_per_acceptable_outcome_usd:>9.4f}"
        )
    lines.extend(
        [
            (
                f"    {'expected net value per attempt':<38} "
                f"${case.expected_net_value_per_attempt_usd:>8.4f} "
                f"${baseline.expected_net_value_per_attempt_usd:>9.4f}"
            ),
            (
                f"    {'incremental net vs baseline':<38} "
                f"${case.incremental_net_value_vs_baseline_usd:>8.4f} "
                f"{'n/a':>10}"
            ),
            (
                f"    {'total trace cost, all tasks':<38} "
                f"${trace_cost:>8.4f} {'n/a':>10}"
            ),
            "",
        ]
    )

    if failed_gates:
        lines.append("  Why the completion rate was not the whole story:")
        for result in failed_gates:
            lines.append(f"    - {result.check_id}: {result.message}")
        shortfall = policy.min_acceptable_rate - case.acceptable_rate
        if shortfall > 0:
            needed = math.ceil(
                policy.min_acceptable_rate * task_count - acceptable_count
            )
            lines.extend(
                [
                    "",
                    (
                        f"    reaching the quality gate needs {needed} more "
                        "acceptable task(s):"
                    ),
                    (
                        f"    {case.acceptable_rate:.0%} observed against a "
                        f"{policy.min_acceptable_rate:.0%} threshold "
                        f"({-shortfall * 100:+.1f}pp)"
                    ),
                ]
            )
        lines.extend(
            [
                "",
                (
                    f"    completion rate {completion_rate:.0%} but decision "
                    f"{DECISION_LABELS[case.decision]}, "
                    f"{len(failed_gates)} gate(s) blocking"
                ),
            ]
        )
    else:
        lines.append(
            f"    completion rate {completion_rate:.0%} and every economic gate "
            "clears"
        )

    lines.extend(
        [
            "",
            f"  evidence digest:  {case.evidence_digest}",
            f"  contract digest:  {case.decision_contract_digest}",
            "",
            "  Synthetic conformance fixture. Not a prevalence or ROI estimate.",
            "=" * width,
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=BUNDLE_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = render_report(args.bundle)
    if args.verify:
        if (
            not args.verify.exists()
            or args.verify.read_text(encoding="utf-8") != report
        ):
            print(f"Generated report differs from {args.verify}")
            return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
