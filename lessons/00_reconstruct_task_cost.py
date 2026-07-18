"""Step 0: reconstruct cost at the task boundary, not the API-call boundary."""

from pathlib import Path

from agent_economics import load_policy, load_rates, load_traces
from agent_economics.assurance import reconstruct_tasks
from agent_economics.io import load_outcomes

ROOT = Path(__file__).resolve().parents[1]
events = load_traces(ROOT / "examples/support_trace.csv")
rates = load_rates(ROOT / "examples/rates.json")
outcomes = load_outcomes(ROOT / "examples/outcomes.csv")
policy = load_policy(ROOT / "examples/policy.json")
tasks = reconstruct_tasks(events, outcomes, rates, policy)

final_call_cost = sum(
    [event for event in events if event.task_id == task.task_id][-1].cost(rates)
    for task in tasks
)
full_trace_cost = sum(task.trace_cost_usd for task in tasks)

print("00 · Reconstruct task cost")
print(f"Final-call-only estimate: ${final_call_cost:.4f}")
print(f"Complete trace spend:     ${full_trace_cost:.4f}")
print(f"Underestimate:            {full_trace_cost / final_call_cost:.1f}x\n")
