"""
Mutation score for agent-economics-lab's evaluation harness.

Standard mutation testing asks: "if I inject a bug, does your test suite catch it?"
Here, the "bugs" are gate removals — the kind that happen every day when a check
is disabled during an incident, a new deployment skips a module, or a team quietly
removes an expensive evaluator.

We inject 588 gate-removal mutations (6 gates × 98 scenarios). For each mutation:
  KILLED   — the harness still catches the regression (fixed-contract returns INCOMPLETE)
  SURVIVED — the mutation produces a false SCALE verdict (harness blind spot)

A 100% mutation score means every gate is load-bearing: removing any one of them
is immediately detected. A < 100% score names the exact blind spot.

Run:
    python3 mutation_score.py
"""
from __future__ import annotations

import sys
from false_green import GATE_DISABLEMENTS, build_evidence, run_benchmark, scenario_matrix
from agent_economics import Decision


def _bar(n: int, total: int, width: int = 20) -> str:
    filled = round(width * n / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def main() -> int:
    print("Running 588 gate-removal mutations...", flush=True)
    rows = run_benchmark()
    scenarios = scenario_matrix()
    n_scenarios = len(scenarios)
    n_total = len(rows)

    # --- Fixed-contract mutation score ---
    # KILLED = fixed engine detects the mutation (returns non-SCALE when full was non-SCALE)
    # SURVIVED = fixed engine misses (returns SCALE after gate removal)
    fixed_killed = sum(
        1 for r in rows
        if not (
            r["full_decision"] != Decision.SCALE.value
            and r["fixed_contract_decision"] == Decision.SCALE.value
        )
    )
    fixed_score = fixed_killed / n_total

    # --- Dynamic-coverage engine: how many mutations it lets through ---
    dynamic_survived = sum(1 for r in rows if r["false_scale_transition"] == "true")
    dynamic_killed = n_total - dynamic_survived
    dynamic_score = dynamic_killed / n_total

    # --- Per-gate breakdown ---
    gate_stats: dict[str, dict] = {}
    for dim, check_id in GATE_DISABLEMENTS.items():
        dim_rows = [r for r in rows if r["disabled_coverage_dimension"] == dim]
        fixed_k = sum(
            1 for r in dim_rows
            if not (
                r["full_decision"] != Decision.SCALE.value
                and r["fixed_contract_decision"] == Decision.SCALE.value
            )
        )
        dyn_survived = sum(1 for r in dim_rows if r["false_scale_transition"] == "true")
        gate_stats[dim] = {
            "total": len(dim_rows),
            "fixed_killed": fixed_k,
            "dyn_survived": dyn_survived,
        }

    # --- Print results ---
    W = 60
    print("═" * W)
    print("  MUTATION SCORE — agent-economics-lab harness hardness")
    print("═" * W)
    print(f"  {n_total} mutations injected  ({n_scenarios} scenarios × {len(GATE_DISABLEMENTS)} gate removals)")
    print()
    print(f"  Fixed-contract engine   {fixed_killed:>3}/{n_total}  killed  ({fixed_score:.1%})  ← oracle")
    print(f"  Dynamic-coverage engine {dynamic_killed:>3}/{n_total}  killed  ({dynamic_score:.1%})  ← status quo")
    print()

    print("  Per-gate: fixed-contract kill rate  (100% = gate removal always detected)")
    print(f"  {'Gate':<25}  {'Killed':>8}   {'Score':>6}  Bar")
    print("  " + "─" * 55)
    for dim, st in gate_stats.items():
        k, t = st["fixed_killed"], st["total"]
        bar = _bar(k, t)
        print(f"  {dim:<25}  {k:>3}/{t:<3}   {k/t:>5.1%}  {bar}")

    print()
    print("  Per-gate: dynamic-coverage survivors (mutations that produce false SCALE)")
    print(f"  {'Gate':<25}  {'Survived':>9}   {'Rate':>6}  Bar")
    print("  " + "─" * 55)
    for dim, st in sorted(gate_stats.items(), key=lambda x: -x[1]["dyn_survived"]):
        s, t = st["dyn_survived"], st["total"]
        bar = _bar(s, t)
        marker = "  ← blind spot" if s > 0 else ""
        print(f"  {dim:<25}  {s:>3}/{t:<3}   {s/t:>5.1%}  {bar}{marker}")

    print()
    verdict = "✓ PERFECT" if fixed_score == 1.0 else f"✗ GAPS FOUND"
    print(f"  HARNESS MUTATION SCORE: {fixed_score:.1%}  {verdict}")
    print()
    if dynamic_survived:
        print(f"  The dynamic-coverage engine lets {dynamic_survived} mutations survive.")
        print(f"  Those are real deployments that would receive a false SCALE verdict.")
    print()
    print("  A mutation score < 100% names your exact blind spot.")
    print("  'All enabled checks passed' ≠ 'all required checks passed.'")
    print("═" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
