"""Step 4: combine evidence, counterfactual, and policy into one bounded decision."""

from pathlib import Path

from agent_economics import (
    evaluate,
    load_baseline,
    load_outcomes,
    load_policy,
    load_rates,
    load_traces,
)

ROOT = Path(__file__).resolve().parents[1]
case = evaluate(
    load_traces(ROOT / "examples/support_trace.csv"),
    load_outcomes(ROOT / "examples/outcomes.csv"),
    load_rates(ROOT / "examples/rates.json"),
    load_baseline(ROOT / "examples/baseline.json"),
    load_policy(ROOT / "examples/policy.json"),
)

print("04 · Issue the assurance case")
print(f"Decision: {case.decision.value}")
for breach in case.breaches:
    print(f"- {breach}")
print()
