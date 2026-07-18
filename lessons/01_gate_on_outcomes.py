"""Step 1: divide total effective cost by acceptable outcomes, not attempts."""

from pathlib import Path

from agent_economics import load_outcomes, load_policy, load_rates, load_traces
from agent_economics.assurance import reconstruct_tasks

ROOT = Path(__file__).resolve().parents[1]
events = load_traces(ROOT / "examples/support_trace.csv")
outcomes = load_outcomes(ROOT / "examples/outcomes.csv")
tasks = reconstruct_tasks(
    events,
    outcomes,
    load_rates(ROOT / "examples/rates.json"),
    load_policy(ROOT / "examples/policy.json"),
)

accepted = sum(task.acceptable for task in tasks)
total_effective_cost = sum(task.effective_cost_usd for task in tasks)
cost_per_acceptable = total_effective_cost / accepted

print("01 · Gate on acceptable outcomes")
print(f"Acceptable:                  {accepted}/{len(tasks)}")
print(f"Total effective cost:        ${total_effective_cost:.2f}")
print(f"Cost / acceptable outcome:   ${cost_per_acceptable:.2f}\n")
