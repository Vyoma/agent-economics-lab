"""
How far is this conversion contract from producing a verdict?

The adapters deliberately refuse to invent economics. A trace tells you what a
model was called with; it cannot tell you whether the outcome was acceptable,
what the tokens cost, or what the alternative was worth. So a conversion
contract arrives with those fields blank and the operator fills them in.

That is the right refusal, and it is also the whole onboarding cost. This module
makes the cost legible: for every unfilled field it names the coverage dimension
that field feeds and therefore the gate that cannot run without it. An unfilled
contract is not a broken file, it is missing required coverage, which is the
same thing this package says about a disabled gate.

    agent-economics contract-status --contract my-contract.json
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Coverage


@dataclass(frozen=True)
class Requirement:
    """
    One field an operator must supply, and the coverage it feeds.

    `applies_when` exists because some requirements are conditional on what the
    trace actually contains. A tool price table is required only if the agent
    called tools; demanding one for a trace with no tool calls would report a
    gap that cannot be filled. Anything derivable from the trace itself is
    pre-filled by the adapter and is deliberately absent from this list.
    """

    path: str
    coverage: Coverage
    why: str
    applies_when: Callable[[dict[str, Any]], bool] | None = None

    def applies(self, document: dict[str, Any]) -> bool:
        return self.applies_when is None or self.applies_when(document)


def _has_tool_calls(document: dict[str, Any]) -> bool:
    return bool(document.get("source_inventory", {}).get("tool_call_count"))


REQUIRED_FIELDS: tuple[Requirement, ...] = tuple(
    Requirement(*spec) for spec in (
    ("tasks[].acceptable", Coverage.OUTCOME_QUALITY,
     "whether each task's outcome met your rubric"),
    ("outcome_contract.label_source", Coverage.OUTCOME_QUALITY,
     "who or what produced those labels"),
    ("outcome_contract.rubric_version", Coverage.OUTCOME_QUALITY,
     "the rubric version the labels were produced under"),
    ("pricing.price_card_id", Coverage.UNIT_ECONOMICS,
     "an identifier for the rate card you priced with"),
    ("pricing.models", Coverage.UNIT_ECONOMICS,
     "input and output price per million tokens, per model"),
    ("pricing.tools", Coverage.UNIT_ECONOMICS,
     "per-call cost for each tool the agent used", _has_tool_calls),
    ("policy.max_cost_per_acceptable_outcome_usd", Coverage.UNIT_ECONOMICS,
     "the most you will pay for one acceptable outcome"),
    ("policy.min_acceptable_rate", Coverage.OUTCOME_QUALITY,
     "the acceptable rate below which you would not ship"),
    ("policy.max_p95_task_cost_usd", Coverage.TAIL_RISK,
     "the p95 task cost you will tolerate"),
    ("policy.max_trace_cost_per_task_usd", Coverage.RUNTIME_CAPS,
     "the per-task trace cost cap"),
    ("policy.max_calls_per_task", Coverage.RUNTIME_CAPS,
     "the per-task call cap"),
    ("policy.human_hourly_cost_usd", Coverage.BUSINESS_VALUE,
     "what an hour of the human alternative costs"),
    ("policy.min_expected_net_value_per_attempt_usd", Coverage.BUSINESS_VALUE,
     "the net value per attempt below which you would not ship"),
    ("policy.min_incremental_net_value_vs_baseline_usd", Coverage.COUNTERFACTUAL,
     "how much better than the baseline you require"),
    ("tasks[].business_value_usd", Coverage.BUSINESS_VALUE,
     "what one acceptable outcome is worth"),
    ("tasks[].human_minutes", Coverage.BUSINESS_VALUE,
     "human minutes spent on each task, for the human-cost term"),
    ("tasks[].remediation_cost_usd", Coverage.BUSINESS_VALUE,
     "cost of cleaning up each unacceptable outcome"),
    ("tasks[].incident_loss_usd", Coverage.TAIL_RISK,
     "loss attributable to each task when it goes wrong"),
    ("policy.repetition_warning_threshold", Coverage.RUNTIME_CAPS,
     "how many repeated tool shapes before the diagnostic warns"),
    ("baseline.name", Coverage.COUNTERFACTUAL,
     "what you are comparing against, named"),
    ("baseline.acceptable_rate", Coverage.COUNTERFACTUAL,
     "the baseline's acceptable rate"),
    ("baseline.cost_per_attempt_usd", Coverage.COUNTERFACTUAL,
     "the baseline's cost per attempt"),
    ("baseline.value_per_acceptable_outcome_usd", Coverage.COUNTERFACTUAL,
     "the baseline's value per acceptable outcome"),
))


@dataclass(frozen=True)
class Gap:
    field: str
    coverage: str
    why: str


@dataclass(frozen=True)
class ReadinessReport:
    filled: tuple[str, ...]
    gaps: tuple[Gap, ...]

    @property
    def total(self) -> int:
        return len(self.filled) + len(self.gaps)

    @property
    def blocked_coverage(self) -> tuple[str, ...]:
        return tuple(sorted({gap.coverage for gap in self.gaps}))

    @property
    def ready(self) -> bool:
        return not self.gaps

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "fields_filled": len(self.filled),
            "fields_required": self.total,
            "blocked_coverage": list(self.blocked_coverage),
            "would_return": "SCALE, ASSIST or STOP" if self.ready else "INCOMPLETE",
            "gaps": [
                {"field": g.field, "blocks_coverage": g.coverage, "supply": g.why}
                for g in self.gaps
            ],
        }


def _resolve(document: dict[str, Any], path: str) -> Any:
    """Read a dotted path. `tasks[].x` means: every task must supply `x`."""
    if "[]" in path:
        head, _, tail = path.partition("[].")
        rows = document.get(head)
        if not isinstance(rows, list) or not rows:
            return None
        values = [row.get(tail) if isinstance(row, dict) else None for row in rows]
        return None if any(v is None or v == "" for v in values) else values
    node: Any = document
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _leaves(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _leaves(v)]
    if isinstance(value, list):
        return [leaf for v in value for leaf in _leaves(v)]
    return [value]


def _is_supplied(value: Any) -> bool:
    """
    Supplied means "the operator put something here", not "every leaf is set".

    Real rate cards carry meaningful nulls: `up_to_input_tokens: null` is an
    untiered price, `inference_geo: null` is a price that does not vary by
    region. Requiring every leaf would reject working contracts. A structure
    counts as supplied when at least one leaf carries a value, which still
    rejects the freshly generated template, whose leaves are all null.
    """
    if value is None or value == "":
        return False
    if isinstance(value, (dict, list)):
        leaves = _leaves(value)
        return bool(leaves) and any(
            leaf is not None and leaf != "" for leaf in leaves
        )
    return True


def assess(document: dict[str, Any]) -> ReadinessReport:
    filled: list[str] = []
    gaps: list[Gap] = []
    for requirement in REQUIRED_FIELDS:
        if not requirement.applies(document):
            continue
        if _is_supplied(_resolve(document, requirement.path)):
            filled.append(requirement.path)
        else:
            gaps.append(
                Gap(
                    field=requirement.path,
                    coverage=requirement.coverage.value,
                    why=requirement.why,
                )
            )
    return ReadinessReport(filled=tuple(filled), gaps=tuple(gaps))


def assess_path(path: Path) -> ReadinessReport:
    return assess(json.loads(path.read_text(encoding="utf-8")))


def render_markdown(report: ReadinessReport) -> str:
    lines = [
        "# Conversion Contract Readiness",
        "",
        f"- Operator fields supplied: **{len(report.filled)} / {report.total}**",
        f"- Verdict this contract would produce: **{report.to_dict()['would_return']}**",
        "",
    ]
    if report.ready:
        lines += [
            "Every required field is supplied. Convert it and evaluate:",
            "",
            "```bash",
            "agent-economics convert --from <adapter> --in <session> \\",
            "    --contract <this file> --out bundle.json",
            "agent-economics evaluate --bundle bundle.json --ci",
            "agent-economics mutate --bundle bundle.json --ci",
            "```",
            "",
        ]
        return "\n".join(lines)

    lines += [
        "Unfilled fields are not a malformed file. They are missing required",
        "coverage, and the engine treats missing coverage the same way it treats a",
        "disabled gate: `INCOMPLETE` is the only legal verdict until they are supplied.",
        "",
        f"Blocked coverage: {', '.join(f'`{c}`' for c in report.blocked_coverage)}",
        "",
        "| Field | Blocks coverage | What to supply |",
        "|---|---|---|",
    ]
    for gap in report.gaps:
        lines.append(f"| `{gap.field}` | `{gap.coverage}` | {gap.why} |")
    lines += [
        "",
        "None of these can be derived from a trace. A trace records what the agent",
        "did; it cannot tell you whether the outcome was acceptable, what the tokens",
        "cost you, or what the alternative was worth. Supplying them is the work, and",
        "refusing to guess them is the point.",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "REQUIRED_FIELDS",
    "Gap",
    "ReadinessReport",
    "Requirement",
    "assess",
    "assess_path",
    "render_markdown",
]
