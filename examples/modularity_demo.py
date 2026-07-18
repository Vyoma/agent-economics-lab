"""Delete an optional check, fail safely on required removal, then add a gate."""

from pathlib import Path

from agent_economics import (
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Decision,
    default_checks,
    evaluate_bundle,
    load_csv_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
evidence = load_csv_bundle(
    traces=ROOT / "examples/support_trace.csv",
    outcomes=ROOT / "examples/outcomes.csv",
    rates=ROOT / "examples/rates.json",
    baseline=ROOT / "examples/baseline.json",
    policy=ROOT / "examples/policy.json",
)
checks = default_checks()


def no_failed_events(view):
    failed = [event.event_id for event in view.events if event.status != "ok"]
    return CheckOutput(
        results=(
            CheckResult(
                check_id="gate.no-failed-events",
                status=CheckStatus.FAIL if failed else CheckStatus.PASS,
                message=f"failed events: {', '.join(failed) if failed else 'none'}",
                on_failure=Decision.STOP if failed else None,
            ),
        )
    )


custom_gate = CheckSpec(
    id="gate.no-failed-events",
    version="1-local",
    mode=CheckMode.GATE,
    covers=frozenset(),
    run=no_failed_events,
)

default_case = evaluate_bundle(evidence, checks)
without_diagnostic = evaluate_bundle(
    evidence,
    tuple(check for check in checks if check.id != "diagnostic.repeated-tool-shape"),
)
without_required = evaluate_bundle(
    evidence,
    tuple(check for check in checks if check.id != "gate.acceptable-rate"),
)
with_custom = evaluate_bundle(evidence, checks + (custom_gate,))

print("EXPLICIT COMPOSITION")
for check in checks:
    print(f"  {check.manifest_id}")
print(f"\nDEFAULT              {default_case.decision.value}")
print(
    "DELETE DIAGNOSTIC  "
    f"{without_diagnostic.decision.value} "
    f"({len(default_case.findings)} -> {len(without_diagnostic.findings)} findings)"
)
print(
    "DELETE REQUIRED    "
    f"{without_required.decision.value} "
    f"(missing: {', '.join(without_required.missing_coverage)})"
)
print(
    "ADD CUSTOM GATE    "
    f"{with_custom.decision.value} "
    f"({with_custom.enabled_checks[-1]})"
)
