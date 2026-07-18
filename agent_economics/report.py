from __future__ import annotations

import json
import math

from .models import AssuranceCase


def render_markdown(case: AssuranceCase) -> str:
    accepted = sum(task.acceptable for task in case.tasks)
    lines = [
        "# Agent Economic Assurance Case",
        "",
        f"**Decision: {case.decision.value}**",
        "",
    ]
    if case.missing_coverage:
        lines.extend(
            [
                "A bounded decision cannot be issued because required assurance "
                "coverage was removed or not evaluated.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                (
                    "This is an evidence-based routing decision: SCALE autonomously, "
                    "ASSIST with human/control coverage, or STOP until the economics change."
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Assurance manifest",
            "",
            f"- Source adapter: `{case.source_manifest_id}`",
            f"- Evidence digest: `{case.evidence_digest}`",
            "- Report renderer: `renderer.markdown@1`",
            "- Enabled checks:",
        ]
    )
    lines.extend(f"  - `{check}`" for check in case.enabled_checks)
    lines.append("- Required coverage:")
    lines.extend(f"  - `{coverage}`" for coverage in case.required_coverage)
    if case.missing_coverage:
        lines.append("- **Missing coverage:**")
        lines.extend(f"  - `{coverage}`" for coverage in case.missing_coverage)

    lines.extend(
        [
            "",
            "## Observed evidence",
            "",
            "| Measure | Result |",
            "|---|---:|",
            f"| Attempts | {len(case.tasks)} |",
            f"| Acceptable outcomes | {accepted} ({case.acceptable_rate:.1%}) |",
            f"| Total effective cost | ${case.total_effective_cost_usd:.2f} |",
            (
                "| Cost per acceptable outcome | "
                f"${case.cost_per_acceptable_outcome_usd:.2f} |"
            ),
            f"| p95 effective task cost | ${case.p95_task_cost_usd:.2f} |",
            f"| Maximum effective task cost | ${case.max_task_cost_usd:.2f} |",
            (
                "| Expected net value per attempt | "
                f"${case.expected_net_value_per_attempt_usd:.2f} |"
            ),
            "",
            "Effective cost = model/tool spend + human review + remediation + incident loss.",
            "",
            "## Counterfactual",
            "",
            f"Baseline: **{case.baseline.name}**",
            "",
            "| Measure | Agent | Baseline |",
            "|---|---:|---:|",
            (
                "| Cost per acceptable outcome | "
                f"${case.cost_per_acceptable_outcome_usd:.2f} | "
                f"${case.baseline.cost_per_acceptable_outcome_usd:.2f} |"
            ),
            (
                "| Expected net value per attempt | "
                f"${case.expected_net_value_per_attempt_usd:.2f} | "
                f"${case.baseline.expected_net_value_per_attempt_usd:.2f} |"
            ),
            (
                "| Incremental net value per attempt | "
                f"${case.incremental_net_value_vs_baseline_usd:.2f} | — |"
            ),
            "",
            "## Gate results",
            "",
        ]
    )
    for result in case.check_results:
        lines.append(
            f"- **{result.status.value} · {result.check_id}:** {result.message}"
        )

    lines.extend(["", "## Policy breaches", ""])
    if case.missing_coverage:
        lines.extend(
            f"- missing required coverage: {coverage}"
            for coverage in case.missing_coverage
        )
    elif case.breaches:
        lines.extend(f"- {breach}" for breach in case.breaches)
    else:
        lines.append("- None")

    lines.extend(["", "## Diagnostic findings", ""])
    if case.findings:
        for finding in case.findings:
            lines.append(
                f"- **{finding.severity.upper()} · {finding.task_id} · "
                f"{finding.control}:** {finding.evidence}. {finding.interpretation}"
            )
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            (
                "The result is only as reliable as the trace coverage, outcome labels, "
                "cost allocation, counterfactual, enabled checks, and observation window. "
                "Removing required coverage returns INCOMPLETE. A repeated tool shape or "
                "graph cycle is a diagnostic warning—not semantic proof of a loop or deadlock."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_json(case: AssuranceCase) -> str:
    def money(value: float) -> float | None:
        return round(value, 6) if math.isfinite(value) else None

    payload = {
        "renderer": "renderer.json@1",
        "decision": case.decision.value,
        "manifest": {
            "source": case.source_manifest_id,
            "evidence_digest": case.evidence_digest,
            "enabled_checks": list(case.enabled_checks),
            "required_coverage": list(case.required_coverage),
            "missing_coverage": list(case.missing_coverage),
        },
        "metrics": {
            "attempts": len(case.tasks),
            "acceptable_rate": case.acceptable_rate,
            "total_effective_cost_usd": money(case.total_effective_cost_usd),
            "cost_per_acceptable_outcome_usd": (
                money(case.cost_per_acceptable_outcome_usd)
            ),
            "p95_task_cost_usd": money(case.p95_task_cost_usd),
            "max_task_cost_usd": money(case.max_task_cost_usd),
            "expected_net_value_per_attempt_usd": (
                money(case.expected_net_value_per_attempt_usd)
            ),
            "incremental_net_value_vs_baseline_usd": (
                money(case.incremental_net_value_vs_baseline_usd)
            ),
        },
        "checks": [
            {
                "id": result.check_id,
                "status": result.status.value,
                "message": result.message,
                "on_failure": (
                    result.on_failure.value if result.on_failure is not None else None
                ),
                "task_id": result.task_id,
            }
            for result in case.check_results
        ],
        "findings": [
            {
                "task_id": finding.task_id,
                "control": finding.control,
                "severity": finding.severity,
                "evidence": finding.evidence,
                "interpretation": finding.interpretation,
            }
            for finding in case.findings
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
