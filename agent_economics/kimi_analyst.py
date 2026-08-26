"""
Kimi-powered assurance advisor for agent-economics-lab.

After running `agent-economics evaluate --format json`, pipe that report into
this module to get decision-specific, quantified recommendations from Kimi-k3.

Decision branches:
  ASSIST   → top-3 gate fixes ranked by threshold distance (closest gap first).
              Each fix names the gate, the exact gap, a concrete action, effort
              level, and the specific economic improvement expected.
  STOP     → viability math: what minimum change in acceptable_rate or
              cost_per_acceptable_outcome would flip to SCALE. Break-even table.
  SCALE    → sustainability watch-outs for any metric within 20% of its
              threshold (early-warning zone), plus revised policy suggestion.
  INCOMPLETE → which coverage dimension is missing and how to supply it.

Usage (CLI):
    python -m agent_economics analyse \\
        --case report.json \\
        --policy policy.json \\
        --baseline baseline.json

Usage (Python):
    from agent_economics.kimi_analyst import analyse
    result = analyse(case, policy, baseline)
    print(result.summary)
    for fix in result.fixes:
        print(fix.rank, fix.gate, fix.action)

Requires:
    MOONSHOT_API_KEY env var

Zero external dependencies — uses stdlib urllib only.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import AssuranceCase, Baseline, EconomicPolicy

logger = logging.getLogger(__name__)

_API_URL = "https://api.moonshot.ai/v1/chat/completions"
_DEFAULT_MODEL = "kimi-k3"
_TIMEOUT_S = 90
_EARLY_WARNING_PCT = 0.20  # flag metrics within 20% of threshold


# ── result types ─────────────────────────────────────────────────────────────

@dataclass
class Fix:
    rank: int
    gate: str
    gap: str
    action: str
    effort: str         # "low" | "medium" | "high"
    expected_impact: str


@dataclass
class AnalysisResult:
    decision: str
    summary: str
    fixes: list[Fix] = field(default_factory=list)
    viability_recoverable: bool | None = None   # None except for STOP
    viability_notes: str = ""
    watch_outs: list[str] = field(default_factory=list)
    revised_policy: dict[str, Any] = field(default_factory=dict)
    model_id: str = _DEFAULT_MODEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "summary": self.summary,
            "fixes": [
                {
                    "rank": f.rank,
                    "gate": f.gate,
                    "gap": f.gap,
                    "action": f.action,
                    "effort": f.effort,
                    "expected_impact": f.expected_impact,
                }
                for f in self.fixes
            ],
            "viability": {
                "recoverable": self.viability_recoverable,
                "break_even_notes": self.viability_notes,
            },
            "watch_outs": self.watch_outs,
            "revised_policy": self.revised_policy,
            "model_id": self.model_id,
        }

    def render_markdown(self) -> str:
        lines = [
            "# Kimi Assurance Analysis",
            "",
            f"**Decision: {self.decision}**",
            "",
            f"{self.summary}",
            "",
        ]
        if self.fixes:
            lines.extend(["## Recommended fixes", ""])
            for f in self.fixes:
                lines.extend([
                    f"### {f.rank}. {f.gate}",
                    f"- **Gap:** {f.gap}",
                    f"- **Action:** {f.action}",
                    f"- **Effort:** {f.effort}",
                    f"- **Expected impact:** {f.expected_impact}",
                    "",
                ])
        if self.viability_recoverable is not None:
            recoverable = "Yes" if self.viability_recoverable else "No"
            lines.extend([
                "## Viability",
                "",
                f"**Recoverable:** {recoverable}",
                "",
                self.viability_notes,
                "",
            ])
        if self.watch_outs:
            lines.extend(["## Sustainability watch-outs", ""])
            for w in self.watch_outs:
                lines.append(f"- {w}")
            lines.append("")
        if self.revised_policy:
            lines.extend([
                "## Suggested policy adjustments",
                "",
                "```json",
                json.dumps(self.revised_policy, indent=2),
                "```",
                "",
            ])
        return "\n".join(lines)


# ── prompt construction ───────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an economic assurance advisor for AI agent deployments.

You receive a structured AssuranceCase evaluation. Your job is to give the
engineering team actionable, QUANTIFIED recommendations.

Decision branches:
  ASSIST   → List the top-3 failing gates ranked by distance to threshold
              (smallest absolute gap first — easiest wins first). For each fix,
              name the gate, state the exact numerical gap, propose a specific
              action, rate effort (low/medium/high), and quantify expected impact.
  STOP     → Determine if recovery is realistic. Compute what minimum change in
              acceptable_rate or cost_per_acceptable_outcome would flip the
              decision. Produce a clear viability verdict with break-even math.
  SCALE    → Check if any metric is within 20% of its threshold (early-warning).
              List sustainability watch-outs. If any threshold looks miscalibrated
              for the observed economics, suggest a revised_policy JSON.
  INCOMPLETE → Identify missing coverage dimensions and explain exactly how to
               supply each one (which CSV column, which gate check to enable).

Rules:
- Use the exact numbers from the context. Do not invent figures.
- fixes array should contain only FAILING gates (status FAIL). Leave it empty
  if the decision is SCALE or INCOMPLETE.
- viability.recoverable: true/false for STOP, null for all other decisions.
- watch_outs: populate for SCALE; leave empty for others unless insightful.
- revised_policy: only populate if you can suggest specific threshold changes
  with a clear economic rationale. Leave empty {} if not applicable.

Respond with valid JSON ONLY — no markdown fences, no commentary:
{
  "decision": "<echoed>",
  "summary": "<one sentence root cause or key insight>",
  "fixes": [
    {
      "rank": <int>,
      "gate": "<gate.id>",
      "gap": "<e.g. 75.0% vs 80.0% threshold (−5.0pp)>",
      "action": "<specific, concrete action text>",
      "effort": "low|medium|high",
      "expected_impact": "<quantified expected result>"
    }
  ],
  "viability": {
    "recoverable": <true|false|null>,
    "break_even_notes": "<what would need to change, with numbers>"
  },
  "watch_outs": ["<string>"],
  "revised_policy": {}
}"""


def _build_context_from_case(
    case: AssuranceCase,
    policy: EconomicPolicy | None,
    baseline: Baseline | None,
) -> str:
    lines: list[str] = []
    accepted = sum(t.acceptable for t in case.tasks)
    n = len(case.tasks)

    lines += [
        "ASSURANCE CASE SUMMARY",
        "======================",
        f"Decision: {case.decision.value}",
        f"Tasks: {n} attempts, {accepted} acceptable ({case.acceptable_rate:.1%}), "
        f"{n - accepted} not-acceptable",
        "",
    ]

    if policy:
        lines += ["GATE RESULTS (observed vs threshold)", "--------------------------------------"]
        _inf = float("inf")

        def _gap_pp(observed: float, threshold: float, higher_is_better: bool) -> tuple[str, bool]:
            diff = observed - threshold
            if higher_is_better:
                status = "PASS" if diff >= 0 else "FAIL"
                return f"{diff:+.1f}pp", status == "FAIL"
            else:
                status = "PASS" if diff <= 0 else "FAIL"
                return f"{diff:+.4f}", status == "FAIL"

        # acceptable-rate
        ar_diff = (case.acceptable_rate - policy.min_acceptable_rate) * 100
        ar_fail = case.acceptable_rate < policy.min_acceptable_rate
        lines.append(
            f"  gate.acceptable-rate:  {case.acceptable_rate:.1%} vs {policy.min_acceptable_rate:.1%} threshold"
            f"  | gap: {ar_diff:+.1f}pp  | {'FAIL → ASSIST' if ar_fail else 'PASS'}"
        )

        # unit-economics
        if math.isfinite(case.cost_per_acceptable_outcome_usd):
            ue_diff = case.cost_per_acceptable_outcome_usd - policy.max_cost_per_acceptable_outcome_usd
            ue_fail = ue_diff > 0
            lines.append(
                f"  gate.unit-economics:   ${case.cost_per_acceptable_outcome_usd:.4f} vs ${policy.max_cost_per_acceptable_outcome_usd:.2f} threshold"
                f"  | gap: ${ue_diff:+.4f}  | {'FAIL → ASSIST' if ue_fail else 'PASS'}"
            )
        else:
            lines.append("  gate.unit-economics:   inf (0 acceptable tasks)  | FAIL → ASSIST")

        # tail-cost
        tc_diff = case.p95_task_cost_usd - policy.max_p95_task_cost_usd
        tc_fail = tc_diff > 0
        lines.append(
            f"  gate.tail-cost:        ${case.p95_task_cost_usd:.4f} vs ${policy.max_p95_task_cost_usd:.2f} threshold"
            f"  | gap: ${tc_diff:+.4f}  | {'FAIL → ASSIST' if tc_fail else 'PASS'}"
        )

        # net-value
        nv_diff = case.expected_net_value_per_attempt_usd - policy.min_expected_net_value_per_attempt_usd
        nv_fail = nv_diff < 0
        lines.append(
            f"  gate.net-value:        ${case.expected_net_value_per_attempt_usd:.4f} vs ${policy.min_expected_net_value_per_attempt_usd:.2f} threshold"
            f"  | gap: ${nv_diff:+.4f}  | {'FAIL → STOP' if nv_fail else 'PASS'}"
        )

        # counterfactual
        cf_diff = case.incremental_net_value_vs_baseline_usd - policy.min_incremental_net_value_vs_baseline_usd
        cf_fail = cf_diff < 0
        lines.append(
            f"  gate.counterfactual:   ${case.incremental_net_value_vs_baseline_usd:.4f} vs ${policy.min_incremental_net_value_vs_baseline_usd:.2f} threshold"
            f"  | gap: ${cf_diff:+.4f}  | {'FAIL → STOP' if cf_fail else 'PASS'}"
        )
        lines.append("")

        lines += [
            "POLICY THRESHOLDS",
            "-----------------",
            f"  min_acceptable_rate:             {policy.min_acceptable_rate:.1%}",
            f"  max_cost_per_acceptable_outcome: ${policy.max_cost_per_acceptable_outcome_usd:.2f}",
            f"  max_p95_task_cost:               ${policy.max_p95_task_cost_usd:.2f}",
            f"  max_trace_cost_per_task:         ${policy.max_trace_cost_per_task_usd:.4f}",
            f"  max_calls_per_task:              {policy.max_calls_per_task}",
            f"  min_expected_net_per_attempt:    ${policy.min_expected_net_value_per_attempt_usd:.2f}",
            f"  min_incremental_net_vs_baseline: ${policy.min_incremental_net_value_vs_baseline_usd:.2f}",
            f"  human_hourly_cost:               ${policy.human_hourly_cost_usd:.2f}",
            "",
        ]
    else:
        lines += ["GATE RESULTS", "------------"]
        for r in case.check_results:
            lines.append(f"  {r.check_id}: {r.status.value} — {r.message}")
        lines.append("")

    lines += [
        "ECONOMIC METRICS",
        "-----------------",
        f"  total_effective_cost:             ${case.total_effective_cost_usd:.4f}",
    ]
    if math.isfinite(case.cost_per_acceptable_outcome_usd):
        lines.append(f"  cost_per_acceptable_outcome:      ${case.cost_per_acceptable_outcome_usd:.4f}")
    else:
        lines.append("  cost_per_acceptable_outcome:      inf")
    lines += [
        f"  p95_task_cost:                    ${case.p95_task_cost_usd:.4f}",
        f"  max_task_cost:                    ${case.max_task_cost_usd:.4f}",
        f"  expected_net_per_attempt:         ${case.expected_net_value_per_attempt_usd:.4f}",
        f"  incremental_net_vs_baseline:      ${case.incremental_net_value_vs_baseline_usd:.4f}",
        "",
    ]

    if baseline:
        lines += [
            f"COUNTERFACTUAL (baseline: {baseline.name})",
            "----------------------------------------------",
            "                              Agent       Baseline",
            f"  cost_per_acceptable:        ${case.cost_per_acceptable_outcome_usd:.2f}     ${baseline.cost_per_acceptable_outcome_usd:.2f}",
            f"  expected_net_per_attempt:   ${case.expected_net_value_per_attempt_usd:.2f}      ${baseline.expected_net_value_per_attempt_usd:.2f}",
            f"  incremental_net:            ${case.incremental_net_value_vs_baseline_usd:.2f}      N/A",
            "",
        ]

    if case.breaches:
        lines += ["POLICY BREACHES", "---------------"]
        for b in case.breaches:
            lines.append(f"  — {b}")
        lines.append("")

    if case.missing_coverage:
        lines += ["MISSING COVERAGE", "----------------"]
        for c in case.missing_coverage:
            lines.append(f"  — {c}")
        lines.append("")

    # Task-level breakdown: worst-performing tasks first
    if case.tasks:
        not_acceptable = [t for t in case.tasks if not t.acceptable]
        if not_acceptable:
            lines += ["FAILING TASKS (by effective cost, descending)", "---------------------------------------------"]
            for t in sorted(not_acceptable, key=lambda t: t.effective_cost_usd, reverse=True)[:5]:
                lines.append(
                    f"  {t.task_id}: effective_cost=${t.effective_cost_usd:.4f}"
                    f"  (trace=${t.trace_cost_usd:.4f}, human=${t.human_cost_usd:.4f},"
                    f"  remediation=${t.remediation_cost_usd:.4f}, incident=${t.incident_loss_usd:.4f})"
                )
            lines.append("")

    return "\n".join(lines)


def _build_context_from_report(
    report: dict[str, Any],
    policy: dict[str, Any] | None,
    baseline: dict[str, Any] | None,
) -> str:
    """Build context from evaluate --format json report dict."""
    lines: list[str] = []
    metrics = report.get("metrics", {})
    decision = report.get("decision", "UNKNOWN")
    n = metrics.get("attempts", 0)
    ar = metrics.get("acceptable_rate", 0.0)
    accepted = round(n * ar) if n else 0

    lines += [
        "ASSURANCE CASE SUMMARY",
        "======================",
        f"Decision: {decision}",
        f"Tasks: {n} attempts, {accepted} acceptable ({ar:.1%}), {n - accepted} not-acceptable",
        "",
    ]

    lines += ["GATE RESULTS", "------------"]
    for check in report.get("checks", []):
        failure_note = f" → {check['on_failure']}" if check.get("on_failure") else ""
        lines.append(f"  {check['id']}: {check['status']} — {check['message']}{failure_note}")
    lines.append("")

    lines += [
        "ECONOMIC METRICS",
        "-----------------",
        f"  total_effective_cost:             ${metrics.get('total_effective_cost_usd', 0):.4f}",
        f"  cost_per_acceptable_outcome:      ${metrics.get('cost_per_acceptable_outcome_usd') or float('inf'):.4f}",
        f"  p95_task_cost:                    ${metrics.get('p95_task_cost_usd', 0):.4f}",
        f"  max_task_cost:                    ${metrics.get('max_task_cost_usd', 0):.4f}",
        f"  expected_net_per_attempt:         ${metrics.get('expected_net_value_per_attempt_usd', 0):.4f}",
        f"  incremental_net_vs_baseline:      ${metrics.get('incremental_net_value_vs_baseline_usd', 0):.4f}",
        "",
    ]

    if policy:
        lines += [
            "POLICY THRESHOLDS",
            "-----------------",
            f"  min_acceptable_rate:             {policy.get('min_acceptable_rate', 0):.1%}",
            f"  max_cost_per_acceptable_outcome: ${policy.get('max_cost_per_acceptable_outcome_usd', 0):.2f}",
            f"  max_p95_task_cost:               ${policy.get('max_p95_task_cost_usd', 0):.2f}",
            f"  min_expected_net_per_attempt:    ${policy.get('min_expected_net_value_per_attempt_usd', 0):.2f}",
            f"  min_incremental_net_vs_baseline: ${policy.get('min_incremental_net_value_vs_baseline_usd', 0):.2f}",
            f"  human_hourly_cost:               ${policy.get('human_hourly_cost_usd', 0):.2f}",
            "",
        ]

    if baseline:
        lines += [
            f"BASELINE: {baseline.get('name', 'unknown')}",
            f"  cost_per_attempt:   ${baseline.get('cost_per_attempt_usd', 0):.2f}",
            f"  acceptable_rate:    {baseline.get('acceptable_rate', 0):.1%}",
            f"  value_per_acceptable: ${baseline.get('value_per_acceptable_outcome_usd', 0):.2f}",
            "",
        ]

    missing = report.get("manifest", {}).get("missing_coverage", [])
    if missing:
        lines += ["MISSING COVERAGE", "----------------"]
        for c in missing:
            lines.append(f"  — {c}")
        lines.append("")

    return "\n".join(lines)


# ── Kimi API call ─────────────────────────────────────────────────────────────

def _call_kimi_analyst(
    context: str,
    *,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 2048,
        "reasoning_effort": "high",   # analyst needs real economic reasoning
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
    }
    req = urllib.request.Request(
        _API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        body = json.loads(resp.read())
    content = body["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise RuntimeError(
            f"Kimi returned empty content. "
            f"Tokens used: {body.get('usage', {}).get('completion_tokens', '?')}. "
            "Try increasing max_tokens."
        )
    return json.loads(content)


def _parse_result(kimi_resp: dict[str, Any], model_id: str) -> AnalysisResult:
    fixes = [
        Fix(
            rank=f.get("rank", i + 1),
            gate=f.get("gate", ""),
            gap=f.get("gap", ""),
            action=f.get("action", ""),
            effort=f.get("effort", "medium"),
            expected_impact=f.get("expected_impact", ""),
        )
        for i, f in enumerate(kimi_resp.get("fixes") or [])
    ]
    viability = kimi_resp.get("viability") or {}
    return AnalysisResult(
        decision=kimi_resp.get("decision", "UNKNOWN"),
        summary=kimi_resp.get("summary", ""),
        fixes=fixes,
        viability_recoverable=viability.get("recoverable"),
        viability_notes=viability.get("break_even_notes", ""),
        watch_outs=list(kimi_resp.get("watch_outs") or []),
        revised_policy=dict(kimi_resp.get("revised_policy") or {}),
        model_id=model_id,
    )


def _get_api_key() -> str:
    key = os.environ.get("MOONSHOT_API_KEY")
    if not key:
        raise RuntimeError(
            "MOONSHOT_API_KEY not set. "
            "Get a key at https://platform.kimi.ai and export it."
        )
    return key


# ── public API ────────────────────────────────────────────────────────────────

def analyse(
    case: AssuranceCase,
    policy: EconomicPolicy | None = None,
    baseline: Baseline | None = None,
    *,
    model: str = _DEFAULT_MODEL,
) -> AnalysisResult:
    """
    Analyse an AssuranceCase and return Kimi-generated recommendations.

    policy and baseline are optional but unlock precise gap math.
    Raises RuntimeError if MOONSHOT_API_KEY is not set.
    """
    api_key = _get_api_key()
    context = _build_context_from_case(case, policy, baseline)
    logger.debug("kimi_analyst: calling %s with %d-char context", model, len(context))
    kimi_resp = _call_kimi_analyst(context, api_key=api_key, model=model)
    result = _parse_result(kimi_resp, model)
    logger.info("kimi_analyst: decision=%s summary=%s", result.decision, result.summary[:80])
    return result


def analyse_report(
    report: dict[str, Any],
    policy: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    *,
    model: str = _DEFAULT_MODEL,
) -> AnalysisResult:
    """
    Analyse a JSON report dict (from `evaluate --format json`).

    Suitable for the CLI pipeline: load the JSON file, pass the dict here.
    Raises RuntimeError if MOONSHOT_API_KEY is not set.
    """
    api_key = _get_api_key()
    context = _build_context_from_report(report, policy, baseline)
    logger.debug("kimi_analyst: calling %s with %d-char context", model, len(context))
    kimi_resp = _call_kimi_analyst(context, api_key=api_key, model=model)
    result = _parse_result(kimi_resp, model)
    logger.info("kimi_analyst: decision=%s summary=%s", result.decision, result.summary[:80])
    return result


# ── CLI entry point ───────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Analyse an assurance case and get Kimi recommendations."
    )
    p.add_argument("--case", required=True,
                   help="JSON report from `evaluate --format json`")
    p.add_argument("--policy", help="policy.json for precise threshold gaps")
    p.add_argument("--baseline", help="baseline.json for counterfactual context")
    p.add_argument("--model", default=_DEFAULT_MODEL)
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p.add_argument("--out", help="Output path (default: stdout)")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        report = json.loads(Path(args.case).read_text())
        policy = json.loads(Path(args.policy).read_text()) if args.policy else None
        baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else None
        result = analyse_report(report, policy, baseline, model=args.model)
    except (RuntimeError, ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        return 2

    output = json.dumps(result.to_dict(), indent=2) if args.format == "json" else result.render_markdown()
    if args.out:
        Path(args.out).write_text(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
