"""Step 2: compare the agent with the process it would actually replace."""

from pathlib import Path

from agent_economics import (
    load_baseline,
    load_outcomes,
    load_policy,
    load_rates,
    load_traces,
)
from agent_economics.assurance import reconstruct_tasks

ROOT = Path(__file__).resolve().parents[1]
events = load_traces(ROOT / "examples/support_trace.csv")
outcomes = load_outcomes(ROOT / "examples/outcomes.csv")
policy = load_policy(ROOT / "examples/policy.json")
tasks = reconstruct_tasks(
    events, outcomes, load_rates(ROOT / "examples/rates.json"), policy
)
baseline = load_baseline(ROOT / "examples/baseline.json")

agent_net = (
    sum(task.business_value_usd for task in tasks)
    - sum(task.effective_cost_usd for task in tasks)
) / len(tasks)
baseline_net = baseline.expected_net_value_per_attempt_usd
incremental = agent_net - baseline_net

print("02 · Compare a named counterfactual")
print(f"Agent net value / attempt:   ${agent_net:.2f}")
print(f"{baseline.name} / attempt: ${baseline_net:.2f}")
print(f"Incremental value:           ${incremental:.2f}")
print(
    "Counterfactual gate:        "
    f"{'PASS' if incremental >= policy.min_incremental_net_value_vs_baseline_usd else 'FAIL'}\n"
)
