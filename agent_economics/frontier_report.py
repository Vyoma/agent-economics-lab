"""Portable renderers for an Economic Assurance Frontier case."""

from __future__ import annotations

import html
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .frontier import (
    FrontierCase,
    FrontierDecision,
    canonical_float,
    frontier_payload,
)


def _money(value: float) -> str:
    if not math.isfinite(value):
        return "N/A"
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"${amount:.2f}"


def render_frontier_markdown(case: FrontierCase) -> str:
    candidate_count = len(case.plan.candidate_arms)
    tail_draws = (
        case.plan.bootstrap_samples
        * (1 - case.plan.confidence_level)
        / (2 * candidate_count)
        if candidate_count
        else None
    )
    if case.decision is FrontierDecision.ADOPT:
        outcome = f"ADOPT `{case.selected_arm}`"
        explanation = (
            "This is the lowest-cost tested candidate that satisfied the predeclared "
            "breakage-risk, cost-reduction, evidence-completeness, and assurance rules."
        )
    elif case.decision is FrontierDecision.HOLD:
        outcome = "HOLD"
        reference = next(
            (arm for arm in case.arms if arm.arm_id == case.plan.reference_arm), None
        )
        if reference and reference.assurance_decision == "SCALE":
            explanation = (
                "No tested candidate satisfied every predeclared quality, cost, and "
                "assurance rule. No switch is supported by this experiment."
            )
        else:
            explanation = (
                "No tested candidate is cleared, and the reference configuration is "
                "not cleared for scaling. This report makes no deployment recommendation."
            )
    else:
        outcome = "INCOMPLETE"
        explanation = (
            "A frontier decision cannot be issued because the frozen experiment "
            "family or its required evidence is incomplete."
        )

    lines = [
        "# Economic Assurance Frontier",
        "",
        f"**Decision: {outcome}**",
        "",
        explanation,
        "",
        "## Frozen experiment plan",
        "",
        f"- Experiment: `{case.plan.experiment_id}`",
        f"- Reference arm: `{case.plan.reference_arm}`",
        f"- Plan digest: `{case.plan.plan_digest}`",
        f"- Task manifest: `{case.plan.task_manifest_path}`",
        f"- Frozen task-manifest digest: `{case.plan.task_manifest_digest}`",
        f"- Paired-task minimum: {case.plan.min_paired_tasks}",
        f"- Maximum harmful-regression risk: {case.plan.max_breakage_rate:.1%}",
        f"- Minimum full-cost reduction: {case.plan.min_cost_reduction_rate:.1%}",
        f"- Target nominal familywise confidence: {case.plan.confidence_level:.1%}",
        f"- Paired bootstrap resamples: {case.plan.bootstrap_samples}",
        f"- Bootstrap seed: {case.plan.seed}",
        f"- Expected adjusted-tail draws: "
        f"{tail_draws:.1f}" if tail_draws is not None else "- Expected adjusted-tail draws: N/A",
        "- Portable numeric precision: 12 significant digits",
        "",
    ]
    if case.problems:
        lines.extend(["## Completeness failures", ""])
        lines.extend(f"- {problem}" for problem in case.problems)
        lines.append("")

    lines.extend(
        [
            "## Tested configurations",
            "",
            "| Arm | Assurance | N | Acceptable | Mean full cost | Cost / acceptable | Net value / attempt | Pareto |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for arm in case.arms:
        lines.append(
            f"| `{arm.arm_id}` | {arm.assurance_decision} | {arm.paired_tasks} | "
            f"{arm.acceptable_rate:.1%} | {_money(arm.mean_effective_cost_usd)} | "
            f"{_money(arm.cost_per_acceptable_outcome_usd)} | "
            f"{_money(arm.expected_net_value_per_attempt_usd)} | "
            f"{'dominated' if arm.dominated else 'frontier'} |"
        )

    if case.comparisons:
        lines.extend(
            [
                "",
                "## Paired evidence against the reference",
                "",
                "| Candidate | Harmful regressions | Breakage UCB | Quality delta | Cost reduction | Cost reduction LCB | Eligible |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for comparison in case.comparisons:
            lines.append(
                f"| `{comparison.candidate_arm}` | "
                f"{comparison.harmful_regressions}/{comparison.paired_tasks} | "
                f"{comparison.breakage_rate_upper:.1%} | "
                f"{comparison.acceptable_rate_delta:+.1%} | "
                f"{comparison.mean_cost_reduction_rate:.1%} | "
                f"{comparison.cost_reduction_rate_lower:.1%} | "
                f"{'yes' if comparison.eligible else 'no'} |"
            )
        lines.extend(["", "### Rejection reasons", ""])
        rejected = [comparison for comparison in case.comparisons if comparison.reasons]
        if rejected:
            for comparison in rejected:
                lines.append(f"- `{comparison.candidate_arm}`:")
                lines.extend(f"  - {reason}" for reason in comparison.reasons)
        else:
            lines.append("- None")

    lines.extend(
        [
            "",
            "## Statistical method",
            "",
            case.method,
            "",
            "The breakage estimand is the absolute paired-population rate of tasks "
            "accepted by the reference and rejected by the candidate, with all matched "
            "tasks in the denominator. The exact upper bound prevents a small sample with zero "
            "observed regressions from appearing certain. Paired resampling preserves "
            "the task-level relationship between reference and candidate costs. The "
            "bootstrap endpoint and its nominal confidence target are approximate and "
            "include Monte Carlo error.",
            "",
            "## Evidence manifests",
            "",
        ]
    )
    lines.extend(f"- `{arm.arm_id}`: `{arm.evidence_digest}`" for arm in case.arms)
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This report identifies the lowest-cost tested configuration that satisfies "
            "the declared rule on this frozen matched dataset. It does not establish a "
            "causal effect unless route assignment was randomized or counterbalanced. "
            "It does not validate the outcome rubric, prove production generalization, "
            "or infer an exact breakpoint between untested configurations. Missing arms, "
            "task fingerprints, rubric versions, cost evidence, or assurance coverage "
            "fail closed.",
            "",
        ]
    )
    return "\n".join(lines)


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return canonical_float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def render_frontier_json(case: FrontierCase) -> str:
    return json.dumps(
        _json_safe(frontier_payload(case)),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def render_frontier_svg(case: FrontierCase) -> str:
    width, height = 760, 430
    left, right, top, bottom = 84, 36, 46, 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    costs = [arm.mean_effective_cost_usd for arm in case.arms] or [0.0]
    qualities = [arm.acceptable_rate for arm in case.arms] or [0.0]
    min_cost = min(costs)
    max_cost = max(costs)
    cost_span = max(max_cost - min_cost, 0.01)
    min_quality = max(0.0, min(qualities) - 0.03)
    max_quality = min(1.0, max(qualities) + 0.03)
    quality_span = max(max_quality - min_quality, 0.01)

    def x_position(value: float) -> float:
        return left + (value - min_cost) / cost_span * plot_width

    def y_position(value: float) -> float:
        return top + (max_quality - value) / quality_span * plot_height

    selected = case.selected_arm
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Economic Assurance Frontier</title>',
        '<desc id="desc">Acceptable outcome rate versus mean full effective cost for tested agent configurations.</desc>',
        '<rect width="100%" height="100%" fill="#0d1117" rx="14"/>',
        '<text x="24" y="30" fill="#f0f6fc" font-family="ui-monospace,monospace" font-size="18" font-weight="700">Economic Assurance Frontier</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#8b949e"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#8b949e"/>',
        f'<text x="{left + plot_width / 2:.1f}" y="{height - 22}" text-anchor="middle" fill="#c9d1d9" font-family="ui-sans-serif,sans-serif" font-size="13">Mean full effective cost per attempt (USD)</text>',
        f'<text x="20" y="{top + plot_height / 2:.1f}" transform="rotate(-90 20 {top + plot_height / 2:.1f})" text-anchor="middle" fill="#c9d1d9" font-family="ui-sans-serif,sans-serif" font-size="13">Acceptable outcome rate</text>',
    ]
    for step in range(5):
        fraction = step / 4
        x_value = min_cost + fraction * cost_span
        x = x_position(x_value)
        parts.extend(
            [
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#21262d"/>',
                f'<text x="{x:.1f}" y="{top + plot_height + 22}" text-anchor="middle" fill="#8b949e" font-family="ui-monospace,monospace" font-size="11">{_money(x_value)}</text>',
            ]
        )
        y_value = min_quality + fraction * quality_span
        y = y_position(y_value)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#21262d"/>',
                f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" fill="#8b949e" font-family="ui-monospace,monospace" font-size="11">{y_value:.0%}</text>',
            ]
        )
    for arm in case.arms:
        x = x_position(arm.mean_effective_cost_usd)
        y = y_position(arm.acceptable_rate)
        color = "#3fb950" if arm.arm_id == selected else ("#8b949e" if arm.dominated else "#58a6ff")
        radius = 8 if arm.arm_id == selected else 6
        label = html.escape(arm.arm_id)
        label_on_left = x > left + plot_width - 135
        label_x = x - 10 if label_on_left else x + 10
        label_anchor = "end" if label_on_left else "start"
        parts.extend(
            [
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" stroke="#f0f6fc" stroke-width="1"/>',
                f'<text x="{label_x:.1f}" y="{y - 10:.1f}" text-anchor="{label_anchor}" fill="#f0f6fc" font-family="ui-monospace,monospace" font-size="11">{label}</text>',
            ]
        )
    parts.append("</svg>\n")
    return "\n".join(parts)
