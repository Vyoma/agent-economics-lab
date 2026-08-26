"""
False-green catch on a real Claude Code trace.

Loads examples/claude-code/bundle.json — a real Claude Code session with
content-redacted privacy mode. Compares what a naive transcript reader sees
(task completion flags) against what the full economic gate pipeline says.

This is the gap that exists in every transcript-based eval tool today:
they measure what the agent *said*. We measure what the economics *are*.

Run:
    python3 real_trace_verdict.py
"""
from __future__ import annotations

import math
from pathlib import Path

from agent_economics import evaluate_bundle
from agent_economics.adapters import load_normalized_json_bundle
from agent_economics.models import CheckStatus, Decision

ROOT = Path(__file__).resolve().parent
BUNDLE_PATH = ROOT / "examples" / "claude-code" / "bundle.json"


def verdict_stats() -> dict:
    """
    Evaluate the real Claude Code trace and return the naive-vs-gated comparison.

    Separated from main() so the claim this script makes is regression-locked by
    the test suite rather than only existing in terminal output.
    """
    bundle = load_normalized_json_bundle(BUNDLE_PATH)
    case = evaluate_bundle(bundle)

    # Naive reading: just look at outcome flags
    outcomes = list(bundle.outcomes.values())
    n = len(outcomes)
    n_acceptable = sum(o.acceptable for o in outcomes)

    return {
        "bundle": bundle,
        "case": case,
        "outcomes": outcomes,
        "n": n,
        "n_acceptable": n_acceptable,
        "naive_rate": n_acceptable / n if n else 0.0,
        "total_trace_cost": sum(e.direct_cost_usd or 0.0 for e in bundle.events),
        "failed_gates": [
            r for r in case.check_results
            if r.status is CheckStatus.FAIL and r.on_failure is not None
        ],
    }


def main() -> int:
    stats = verdict_stats()
    bundle = stats["bundle"]
    case = stats["case"]
    outcomes = stats["outcomes"]
    n = stats["n"]
    n_acceptable = stats["n_acceptable"]
    naive_rate = stats["naive_rate"]
    total_trace_cost = stats["total_trace_cost"]
    failed_gates = stats["failed_gates"]

    policy = bundle.policy
    baseline = bundle.baseline
    agent_cost_per_acceptable = (
        case.cost_per_acceptable_outcome_usd
        if math.isfinite(case.cost_per_acceptable_outcome_usd)
        else float("inf")
    )
    baseline_cost_per_acceptable = baseline.cost_per_acceptable_outcome_usd

    W = 64
    print("═" * W)
    print("  REAL TRACE VERDICT — Claude Code session")
    print(f"  {len(bundle.events)} events · {n} tasks · privacy-redacted")
    print("═" * W)
    print()

    # ── Naive reading ──────────────────────────────────────────────────────
    print("  NAIVE TRANSCRIPT READING (what LangSmith / log viewers show)")
    print("  " + "─" * 54)
    for o in outcomes:
        icon = "✓" if o.acceptable else "✗"
        tag = "acceptable" if o.acceptable else "not acceptable"
        short_id = o.task_id[:16] + "…"
        print(f"    {icon}  {short_id}  →  {tag}")
    print()
    print(f"    Success rate: {naive_rate:.0%}  ({n_acceptable}/{n} tasks)")
    if naive_rate >= 0.5:
        print("    Naive verdict: 'Decent result, might be worth deploying.'")
    else:
        print("    Naive verdict: 'Needs improvement but not terrible.'")
    print()

    # ── Gated verdict ──────────────────────────────────────────────────────
    decision_icons = {
        Decision.SCALE: "🟢 SCALE",
        Decision.ASSIST: "🟡 ASSIST",
        Decision.STOP: "🔴 STOP",
        Decision.INCOMPLETE: "⬜ INCOMPLETE",
    }
    print("  AGENT-ECONOMICS-LAB GATED VERDICT")
    print("  " + "─" * 54)
    print(f"    Decision: {decision_icons[case.decision]}")
    print()

    print("  Gate results:")
    for r in case.check_results:
        icon = "  ✓" if r.status is not CheckStatus.FAIL else "  ✗"
        route = f" → {r.on_failure.value}" if r.on_failure else ""
        print(f"    {icon}  {r.check_id}: {r.message}{route}")
    print()

    # ── Economic comparison ────────────────────────────────────────────────
    print("  Economic reality:")
    print(f"    {'Metric':<38}  {'Agent':>8}  {'Baseline':>10}")
    print("    " + "─" * 58)
    print(f"    {'Acceptable rate':<38}  {case.acceptable_rate:>7.1%}  {baseline.acceptable_rate:>9.1%}")
    if math.isfinite(agent_cost_per_acceptable):
        print(f"    {'Cost per acceptable outcome':<38}  ${agent_cost_per_acceptable:>7.4f}  ${baseline_cost_per_acceptable:>9.4f}")
    print(f"    {'Expected net value per attempt':<38}  ${case.expected_net_value_per_attempt_usd:>7.4f}  ${baseline.expected_net_value_per_attempt_usd:>9.4f}")
    print(f"    {'Incremental net vs baseline':<38}  ${case.incremental_net_value_vs_baseline_usd:>7.4f}  {'N/A':>10}")
    print(f"    {'Total trace cost (all tasks)':<38}  ${total_trace_cost:>7.4f}  {'—':>10}")
    print()

    # ── Gap analysis ───────────────────────────────────────────────────────
    if failed_gates:
        print("  Why the transcript was misleading:")
        for r in failed_gates:
            print(f"    ⚠  {r.check_id}: {r.message}")
        print()
        # Specific gap for acceptable-rate
        ar_gap = (case.acceptable_rate - policy.min_acceptable_rate) * 100
        if ar_gap < 0:
            n_more_needed = math.ceil(
                (policy.min_acceptable_rate * n) - n_acceptable
            )
            print(f"    To reach SCALE: {n_more_needed} more task(s) must be acceptable")
            print(f"    (gap: {ar_gap:+.1f}pp  observed {case.acceptable_rate:.0%} vs {policy.min_acceptable_rate:.0%} threshold)")
        print()

    print("  The gap between 'passed' and 'approved to scale':")
    print(f"    Naive reader sees: {naive_rate:.0%} completion rate")
    if case.decision is not Decision.SCALE:
        print(f"    Framework sees:   {case.decision.value} — {len(failed_gates)} gate(s) blocking")
        print()
        print("  Transcript-based eval tools measure what the agent said.")
        print("  This framework measures whether the economics justify deployment.")
    else:
        print(f"    Framework agrees: {case.decision.value} — all economic gates clear")
    print()
    print(f"  Evidence digest:  {case.evidence_digest[:32]}…")
    print(f"  Contract digest:  {case.decision_contract_digest[:32]}…")
    print("═" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
