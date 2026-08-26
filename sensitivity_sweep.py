"""
Decision robustness analysis and baseline fragility index.

Every SCALE/ASSIST/STOP verdict is a function of economic assumptions
(incident_loss_usd, remediation_cost, baseline acceptable_rate). If those
assumptions are wrong, the verdict is wrong. This script measures:

  1. DECISION ROBUSTNESS — how many verdicts flip across a grid of economic
     assumptions (incident_loss × remediation_cost). A verdict that changes
     under plausible assumptions is a measurement artifact, not a fact.

  2. BASELINE FRAGILITY INDEX — how many counterfactual gates flip when the
     baseline acceptable_rate is perturbed by ±10%, ±25%, ±50%. If your
     baseline is a rough estimate (it always is), how confident can you be
     in counterfactual verdicts?

Uses the same 98-scenario synthetic matrix as false_green.py.

Run:
    python3 sensitivity_sweep.py
"""
from __future__ import annotations

from itertools import product

from agent_economics import (
    Baseline,
    Decision,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
    evaluate_bundle,
    make_evidence_bundle,
)
from agent_economics.models import CheckStatus
from false_green import build_evidence, scenario_matrix

# ── Sweep grids ────────────────────────────────────────────────────────────

# incident_loss_usd: from 0 (no tail risk) to 50× remediation (catastrophic)
INCIDENT_LOSS_GRID = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
# remediation_cost_usd: from 0 to 5× trace cost
REMEDIATION_COST_GRID = [0.0, 0.25, 0.5, 1.0, 2.0, 5.0]
# baseline perturbations (multiplicative on acceptable_rate)
BASELINE_PERTURBATIONS = [0.50, 0.75, 0.90, 1.10, 1.25, 1.50]
BASELINE_LABELS = ["−50%", "−25%", "−10%", "+10%", "+25%", "+50%"]


def _bar(n: int, total: int, width: int = 24) -> str:
    filled = round(width * n / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def _evaluate_with_overrides(
    scenario,
    incident_loss_override: float,
    remediation_override: float,
) -> Decision:
    """Build evidence with overridden economic params and return the decision."""
    events = []
    outcomes = {}
    for index in range(10):
        task_id = f"task-{index:02d}"
        acceptable = index < scenario.acceptable_tasks
        events.append(TraceEvent(
            task_id=task_id,
            event_id=f"event-{index:02d}",
            timestamp=f"2026-01-01T00:00:{index:02d}Z",
            event_type="model",
            name="complete_task",
            direct_cost_usd=scenario.trace_cost_usd,
        ))
        outcomes[task_id] = Outcome(
            task_id=task_id,
            acceptable=acceptable,
            business_value_usd=scenario.business_value_usd,
            human_minutes=(
                0.0 + (scenario.failure_human_minutes if not acceptable else 0.0)
            ),
            remediation_cost_usd=remediation_override if not acceptable else 0.0,
            incident_loss_usd=(incident_loss_override if index == 0 else 0.0),
        )

    policy = EconomicPolicy(
        human_hourly_cost_usd=60.0,
        min_acceptable_rate=0.80,
        max_cost_per_acceptable_outcome_usd=2.0,
        max_p95_task_cost_usd=8.0,
        max_trace_cost_per_task_usd=1.0,
        max_calls_per_task=3,
        min_expected_net_value_per_attempt_usd=0.0,
        min_incremental_net_value_vs_baseline_usd=0.0,
    )
    evidence = make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates={"unused": ModelRate(0.0, 0.0)},
        baseline=Baseline(
            name="controlled baseline",
            cost_per_attempt_usd=scenario.baseline_cost_usd,
            acceptable_rate=scenario.baseline_acceptable_rate,
            value_per_acceptable_outcome_usd=scenario.business_value_usd,
        ),
        policy=policy,
        source_id="source.sensitivity-sweep",
        source_version="1",
    )
    return evaluate_bundle(evidence).decision


def _evaluate_with_baseline_perturb(scenario, multiplier: float) -> bool:
    """Return True if counterfactual gate flips vs baseline multiplier=1.0."""
    def _run(mult: float) -> Decision:
        events = []
        outcomes = {}
        for index in range(10):
            task_id = f"task-{index:02d}"
            acceptable = index < scenario.acceptable_tasks
            events.append(TraceEvent(
                task_id=task_id,
                event_id=f"event-{index:02d}",
                timestamp=f"2026-01-01T00:00:{index:02d}Z",
                event_type="model",
                name="complete_task",
                direct_cost_usd=scenario.trace_cost_usd,
            ))
            outcomes[task_id] = Outcome(
                task_id=task_id,
                acceptable=acceptable,
                business_value_usd=scenario.business_value_usd,
                human_minutes=(scenario.failure_human_minutes if not acceptable else 0.0),
                incident_loss_usd=(scenario.tail_loss_usd if index == 0 else 0.0),
            )
        perturbed_rate = min(0.9999, max(0.0001, scenario.baseline_acceptable_rate * mult))
        policy = EconomicPolicy(
            human_hourly_cost_usd=60.0,
            min_acceptable_rate=0.80,
            max_cost_per_acceptable_outcome_usd=2.0,
            max_p95_task_cost_usd=8.0,
            max_trace_cost_per_task_usd=1.0,
            max_calls_per_task=3,
            min_expected_net_value_per_attempt_usd=0.0,
            min_incremental_net_value_vs_baseline_usd=0.0,
        )
        evidence = make_evidence_bundle(
            events=events,
            outcomes=outcomes,
            rates={"unused": ModelRate(0.0, 0.0)},
            baseline=Baseline(
                name="controlled baseline",
                cost_per_attempt_usd=scenario.baseline_cost_usd,
                acceptable_rate=perturbed_rate,
                value_per_acceptable_outcome_usd=scenario.business_value_usd,
            ),
            policy=policy,
            source_id="source.sensitivity-sweep",
            source_version="1",
        )
        case = evaluate_bundle(evidence)
        # Check if counterfactual gate flipped specifically
        for r in case.check_results:
            if "counterfactual" in r.check_id:
                return r.status is CheckStatus.FAIL
        return False

    baseline_cf_fail = _run(1.0)
    perturbed_cf_fail = _run(multiplier)
    return baseline_cf_fail != perturbed_cf_fail


def sweep_stats() -> dict:
    """
    Run both sweeps and return the counts.

    Separated from main() so the robustness and fragility numbers are
    regression-locked by the test suite rather than only existing in terminal
    output. The baseline fragility map is computed once and reused, rather than
    recomputing the -25% and -50% columns for the summary lines.
    """
    scenarios = scenario_matrix()
    n = len(scenarios)

    flip_counts: list[int] = []
    for scenario in scenarios:
        base_decision = evaluate_bundle(build_evidence(scenario)).decision
        flip_counts.append(
            sum(
                1
                for inc, rem in product(INCIDENT_LOSS_GRID, REMEDIATION_COST_GRID)
                if _evaluate_with_overrides(scenario, inc, rem) != base_decision
            )
        )

    fragility = {
        mult: sum(1 for s in scenarios if _evaluate_with_baseline_perturb(s, mult))
        for mult in BASELINE_PERTURBATIONS
    }

    return {
        "n": n,
        "grid_size": len(INCIDENT_LOSS_GRID) * len(REMEDIATION_COST_GRID),
        "flip_counts": flip_counts,
        "robust": sum(1 for f in flip_counts if f == 0),
        "fragile": sum(1 for f in flip_counts if 1 <= f < 3),
        "brittle": sum(1 for f in flip_counts if f >= 3),
        "max_flips": max(flip_counts, default=0),
        "fragility": fragility,
    }


def main() -> int:
    n = len(scenario_matrix())
    grid_size = len(INCIDENT_LOSS_GRID) * len(REMEDIATION_COST_GRID)

    W = 64
    print("═" * W)
    print("  SENSITIVITY SWEEP — decision robustness analysis")
    print("═" * W)
    print(
        f"  {n} scenarios  ×  {grid_size}-cell economic grid "
        f"({len(INCIDENT_LOSS_GRID)} incident × {len(REMEDIATION_COST_GRID)} remediation)"
    )
    print(f"  Sweeping incident_loss ∈ [{INCIDENT_LOSS_GRID[0]}..{INCIDENT_LOSS_GRID[-1]}]  ×")
    print(f"          remediation    ∈ [{REMEDIATION_COST_GRID[0]}..{REMEDIATION_COST_GRID[-1]}]")
    print()
    print("  Computing... (this takes a few seconds)", flush=True)

    stats = sweep_stats()
    robust = stats["robust"]
    fragile = stats["fragile"]
    brittle = stats["brittle"]
    max_flips = stats["max_flips"]
    fragility = stats["fragility"]

    # ── Part 1: decision flip counts ───────────────────────────────────────
    print()
    print("  DECISION ROBUSTNESS across economic assumption grid")
    print("  " + "─" * 56)
    print(f"  {'ROBUST  (0 flips)':<22} {robust:>4}/{n}  {_bar(robust,n)}  {robust/n:.1%}")
    print(f"  {'FRAGILE (1-2 flips)':<22} {fragile:>4}/{n}  {_bar(fragile,n)}  {fragile/n:.1%}")
    print(f"  {'BRITTLE (≥3 flips)':<22} {brittle:>4}/{n}  {_bar(brittle,n)}  {brittle/n:.1%}")
    print()
    print(f"  Max flips for a single scenario: {max_flips}/{grid_size}")
    if brittle:
        print(f"  ⚠  {brittle} scenarios produce a verdict that is an economic")
        print("     assumption artifact, not a stable empirical result.")
        print("     Never surface a SCALE verdict with flip_count ≥ 3 without")
        print("     a sensitivity report alongside it.")

    # ── Part 2: baseline fragility ─────────────────────────────────────────
    print()
    print("  BASELINE FRAGILITY INDEX  (perturb baseline acceptable_rate)")
    print("  " + "─" * 56)

    for mult, label in zip(BASELINE_PERTURBATIONS, BASELINE_LABELS, strict=True):
        flips = fragility[mult]
        pct = flips / n
        warn = "  ← critical" if pct > 0.25 else ""
        print(
            f"  {label:>4} baseline error  →  {flips:>3}/{n} counterfactual gate flips  "
            f"{_bar(flips,n,18)}  {pct:.1%}{warn}"
        )

    print()
    bf_50, bf_25 = fragility[0.50], fragility[0.75]
    if bf_25 > 0:
        print(f"  ⚠  A 25% error in your baseline flips {bf_25}/{n} gates ({bf_25/n:.1%}).")
    if bf_50 > 0:
        print(f"     A 50% error in your baseline flips {bf_50}/{n} gates ({bf_50/n:.1%}).")
    print()
    print("  Your baseline is always an estimate. These are its error bars.")
    print("  Report the fragility index alongside every SCALE verdict.")
    print("═" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
