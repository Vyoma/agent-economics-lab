"""Step 3: separate optional diagnostics from decision-authoritative gates."""

from pathlib import Path

from agent_economics import CheckStatus, evaluate_bundle, load_csv_bundle

ROOT = Path(__file__).resolve().parents[1]
case = evaluate_bundle(
    load_csv_bundle(
        traces=ROOT / "examples/support_trace.csv",
        outcomes=ROOT / "examples/outcomes.csv",
        rates=ROOT / "examples/rates.json",
        baseline=ROOT / "examples/baseline.json",
        policy=ROOT / "examples/policy.json",
    )
)

print("03 · Bound runaway tasks")
for result in case.check_results:
    if result.check_id == "gate.runtime-caps" and result.status is CheckStatus.FAIL:
        print(f"GATE    {result.message}")
for finding in case.findings:
    print(f"WARNING {finding.task_id} {finding.control}")
print("Warnings explain; typed gates route.\n")
