"""
Kimi-powered outcome labeler for agent-economics-lab.

Replaces manual outcomes.csv authoring with LLM-judged labels.
Each task is scored against a rubric; the score determines `acceptable`.
A full audit trail is written alongside the outcomes CSV.

Usage (CLI):
    python -m agent_economics judge \\
        --task-results task_results.csv \\
        --rubric rubric.json \\
        --out outcomes.csv

Usage (Python):
    from agent_economics.kimi_judge import judge
    judge("task_results.csv", "rubric.json", "outcomes.csv")

Rubric schema (rubric.json):
    {
      "rubric_id": "support-v1",
      "task_type": "describe what the agent does",
      "acceptable_threshold": 0.70,
      "business_value_usd_if_acceptable": 8.00,
      "human_minutes_if_not_acceptable": 8.0,
      "remediation_cost_usd_if_not_acceptable": 0.75,
      "incident_loss_usd_if_not_acceptable": 0.0,
      "criteria": [
        {"id": "accuracy", "question": "Did the agent correctly resolve the issue?", "weight": 0.50},
        {"id": "policy",   "question": "Did the response comply with policy?",       "weight": 0.30},
        {"id": "tone",     "question": "Was the tone professional and clear?",        "weight": 0.20}
      ]
    }

task_results.csv columns:
    task_id   — matches task IDs in traces CSV
    output    — the agent's final response or output
    context   — (optional) brief task description for the judge

Requires:
    MOONSHOT_API_KEY env var (https://platform.kimi.ai)

Zero external dependencies — uses stdlib urllib only.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import time
import urllib.error
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import kimi_client

logger = logging.getLogger(__name__)

# The request contract, retry policy, and provider live in kimi_client, the
# package's single inference egress. Re-exported here for callers and tests.
_DEFAULT_MODEL = kimi_client.DEFAULT_MODEL
_DEFAULT_REASONING_EFFORT = kimi_client.DEFAULT_REASONING_EFFORT
_REASONING_EFFORTS = kimi_client.REASONING_EFFORTS
_MAX_ATTEMPTS = kimi_client.MAX_ATTEMPTS
# The verdict JSON is tiny; the reasoning is what consumes this budget. K3 always
# reasons, and at `max` effort a budget sized for a short answer gets spent before
# any content is emitted, which surfaces as an empty-content error. K3's own
# default is 131072, so this stays well inside it while still bounding cost.
_MAX_COMPLETION_TOKENS = 32768
_TIMEOUT_S = None  # follows reasoning_effort, see kimi_client

_REQUIRED_RUBRIC_FIELDS = {
    "rubric_id",
    "task_type",
    "acceptable_threshold",
    "business_value_usd_if_acceptable",
    "human_minutes_if_not_acceptable",
    "remediation_cost_usd_if_not_acceptable",
    "criteria",
}

_OUTCOMES_FIELDNAMES = [
    "task_id",
    "acceptable",
    "business_value_usd",
    "human_minutes",
    "remediation_cost_usd",
    "incident_loss_usd",
]


# ── rubric validation ─────────────────────────────────────────────────────────

def _validate_rubric(rubric: dict) -> None:
    missing = _REQUIRED_RUBRIC_FIELDS - rubric.keys()
    if missing:
        raise ValueError(f"rubric.json is missing required fields: {sorted(missing)}")
    if not rubric["criteria"]:
        raise ValueError("rubric.json must have at least one criterion")
    for c in rubric["criteria"]:
        for f in ("id", "question", "weight"):
            if f not in c:
                raise ValueError(f"criterion {c!r} missing field {f!r}")
    total_weight = sum(c["weight"] for c in rubric["criteria"])
    if not (0.999 < total_weight < 1.001):
        raise ValueError(
            f"criterion weights must sum to 1.0 (got {total_weight:.3f})"
        )


# ── prompt construction ───────────────────────────────────────────────────────

def _build_system_prompt(rubric: dict) -> str:
    criteria_lines = "\n".join(
        f'  - id: "{c["id"]}"  weight: {c["weight"]}  '
        f'question: "{c["question"]}"'
        for c in rubric["criteria"]
    )
    return f"""\
You are an expert evaluator judging AI agent outputs for economic assurance.

Task type: {rubric["task_type"]}
Acceptable threshold: {rubric["acceptable_threshold"]} (overall_score >= threshold → acceptable)

Rubric criteria:
{criteria_lines}

For each agent output you receive, score every criterion from 0.0 to 1.0 independently.
Compute overall_score = sum(score_i * weight_i) for all criteria.
Set acceptable = overall_score >= {rubric["acceptable_threshold"]}.

Respond with valid JSON only — no markdown, no commentary, exactly this structure:
{{
  "task_id": "<echoed from input>",
  "criterion_scores": {{{", ".join(f'"{c["id"]}": <float>' for c in rubric["criteria"])}}},
  "overall_score": <float>,
  "acceptable": <true|false>,
  "rationale": "<one sentence explaining the key factor in your verdict>"
}}"""


def _build_user_message(task_id: str, output: str, context: str) -> str:
    parts = [f"task_id: {task_id}"]
    if context:
        parts.append(f"context: {context}")
    parts.append(f"agent output:\n{output}")
    return "\n".join(parts)


# ── Kimi API call ─────────────────────────────────────────────────────────────

def _verdict_schema(rubric: dict) -> dict[str, Any]:
    """Return a strict JSON schema for one task verdict.

    Structured output is the forcing function. Asking for JSON in the prompt and
    hoping makes a parse failure indistinguishable from a genuine rejection,
    because both land in the unacceptable fallback. A schema the server enforces
    removes that failure mode from the label pipeline.

    Shape and type only. Moonshot Flavored JSON Schema accepts `type`, `enum`,
    and `required` as its validation keywords, so numeric range constraints
    cannot be expressed here: a schema carrying `minimum` or `maximum` is
    rejected with HTTP 400 and never reaches the model. The `[0.0, 1.0]` bounds
    are stated in the description for the model and enforced by
    `_validate_verdict` after parsing.
    """
    criterion_ids = [criterion["id"] for criterion in rubric["criteria"]]
    score_property = {
        "type": "number",
        "description": "Score from 0.0 to 1.0 inclusive.",
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "task_verdict",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "task_id",
                    "criterion_scores",
                    "overall_score",
                    "acceptable",
                    "rationale",
                ],
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Echoed from the input.",
                    },
                    "criterion_scores": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": criterion_ids,
                        "properties": {
                            criterion_id: dict(score_property)
                            for criterion_id in criterion_ids
                        },
                    },
                    "overall_score": {
                        "type": "number",
                        "description": (
                            "Weighted sum of criterion scores, 0.0 to 1.0 "
                            "inclusive."
                        ),
                    },
                    "acceptable": {
                        "type": "boolean",
                        "description": (
                            "True when overall_score meets the acceptable "
                            "threshold."
                        ),
                    },
                    "rationale": {
                        "type": "string",
                        "description": "One sentence naming the deciding factor.",
                    },
                },
            },
        },
    }


def _validate_verdict(verdict: dict[str, Any], rubric: dict) -> None:
    """Enforce the bounds the schema cannot express.

    MFJS has no numeric range keyword, so an out-of-range score would otherwise
    flow into the economics unchallenged. A violation raises ValueError, which
    the caller treats as a failed judgment for that task rather than as data.
    """
    for field in ("criterion_scores", "overall_score", "acceptable"):
        if field not in verdict:
            raise ValueError(f"verdict is missing required field {field!r}")
    if not isinstance(verdict["acceptable"], bool):
        raise ValueError("verdict field 'acceptable' must be a boolean")

    scores = verdict["criterion_scores"]
    if not isinstance(scores, dict):
        raise ValueError("verdict field 'criterion_scores' must be an object")
    expected = {criterion["id"] for criterion in rubric["criteria"]}
    if set(scores) != expected:
        raise ValueError(
            "verdict criterion_scores keys "
            f"{sorted(scores)} do not match rubric criteria {sorted(expected)}"
        )

    for label, value in list(scores.items()) + [
        ("overall_score", verdict["overall_score"])
    ]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"verdict score {label!r} must be a number")
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(
                f"verdict score {label!r} is {value}, outside [0.0, 1.0]"
            )


def _call_kimi(
    system_prompt: str,
    user_message: str,
    *,
    api_key: str,
    model: str,
    response_format: dict[str, Any] | None = None,
    reasoning_effort: str = _DEFAULT_REASONING_EFFORT,
    rubric: dict | None = None,
) -> dict[str, Any]:
    """Score one task through the package's single inference egress.

    The system prompt is identical for every task in a run and is sent first, so
    Moonshot's automatic context caching can reuse it across the batch. Keep
    per-task content in the user message; do not interpolate it into the system
    prompt, or the cacheable prefix changes on every call.
    """
    verdict = kimi_client.call_kimi_json(
        system_prompt,
        user_message,
        api_key=api_key,
        model=model,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
        max_completion_tokens=_MAX_COMPLETION_TOKENS,
        timeout_s=_TIMEOUT_S,
    )
    if rubric is not None:
        _validate_verdict(verdict, rubric)
    return verdict


# ── outcome row builder ───────────────────────────────────────────────────────

def _build_outcome_row(
    task_id: str,
    kimi_resp: dict,
    rubric: dict,
    model_id: str,
    reasoning_effort: str = _DEFAULT_REASONING_EFFORT,
) -> tuple[dict, dict]:
    """Returns (outcomes_row, audit_row)."""
    acceptable = bool(kimi_resp.get("acceptable", False))
    incident_loss = float(rubric.get("incident_loss_usd_if_not_acceptable", 0.0))

    if acceptable:
        outcomes_row = {
            "task_id": task_id,
            "acceptable": "true",
            "business_value_usd": str(rubric["business_value_usd_if_acceptable"]),
            "human_minutes": "0",
            "remediation_cost_usd": "0",
            "incident_loss_usd": "0",
        }
    else:
        outcomes_row = {
            "task_id": task_id,
            "acceptable": "false",
            "business_value_usd": "0",
            "human_minutes": str(rubric["human_minutes_if_not_acceptable"]),
            "remediation_cost_usd": str(rubric["remediation_cost_usd_if_not_acceptable"]),
            "incident_loss_usd": str(incident_loss),
        }

    audit_row = {
        "task_id": task_id,
        "model_id": model_id,
        "reasoning_effort": reasoning_effort,
        "output_contract": "json_schema/strict",
        "rubric_id": rubric["rubric_id"],
        "overall_score": kimi_resp.get("overall_score"),
        "criterion_scores": kimi_resp.get("criterion_scores", {}),
        "acceptable": acceptable,
        "rationale": kimi_resp.get("rationale", ""),
        "label_source": f"kimi-judge@{rubric['rubric_id']}",
    }
    return outcomes_row, audit_row


def _error_outcome_row(task_id: str, rubric: dict, error: str) -> tuple[dict, dict]:
    """Safe fallback when Kimi call fails — counts as unacceptable."""
    # No outcomes row. A task the judge never evaluated has produced no
    # evidence about its outcome, and "acceptable: false" is a verdict, not an
    # absence. Writing one folds a judge outage into the acceptable rate, where
    # it is indistinguishable from a genuinely bad result. kimi_eval already
    # refuses this on the evaluation side ("an outage must not be reported as
    # strictness"); this is the same rule on the labelling side.
    outcomes_row = None
    audit_row = {
        "task_id": task_id,
        "model_id": "error",
        "rubric_id": rubric.get("rubric_id", "unknown"),
        "overall_score": None,
        "criterion_scores": {},
        "acceptable": False,
        "rationale": f"Judge call failed: {error}",
        "label_source": "kimi-judge@error",
    }
    return outcomes_row, audit_row


class UnjudgedTasks(RuntimeError):
    """
    Raised when the judge could not evaluate every task.

    The default is to refuse rather than to emit a partial outcomes file,
    because the file is evidence: once a task is missing from it, whoever builds
    a bundle downstream cannot tell an outage from a task that was never
    submitted. Pass `allow_unjudged=True` to write the file anyway, in which
    case the unjudged tasks are omitted rather than labelled, so the mismatch
    between traces and outcomes fails closed at bundle validation.
    """

    def __init__(self, task_ids: Sequence[str], total: int) -> None:
        self.task_ids = tuple(task_ids)
        super().__init__(
            f"{len(self.task_ids)} of {total} task(s) could not be judged after "
            f"retries: {', '.join(self.task_ids)}. These produced no evidence "
            "about their outcome and are not labelled unacceptable. Retry, or "
            "pass allow_unjudged=True to write the remaining labels and omit "
            "these, which will fail closed when a bundle is built."
        )


# ── public API ────────────────────────────────────────────────────────────────

def judge(
    task_results_path: str | Path,
    rubric_path: str | Path,
    out_path: str | Path,
    *,
    model: str = _DEFAULT_MODEL,
    rate_limit: int = 5,
    reasoning_effort: str = _DEFAULT_REASONING_EFFORT,
    allow_unjudged: bool = False,
) -> None:
    """
    Label agent task outcomes using Kimi.

    Reads task_results_path (CSV: task_id, output, context?),
    scores each task against rubric_path,
    writes outcomes CSV to out_path (compatible with agent_economics evaluate).
    Writes audit sidecar to out_path.with_suffix('.audit.json').

    Verdicts are forced through a strict JSON schema derived from the rubric, so
    a malformed response is a server-side error rather than a silent
    unacceptable label. Transient HTTP failures are retried before falling back.

    Raises RuntimeError if MOONSHOT_API_KEY is not set.
    Raises ValueError if rubric is malformed or reasoning_effort is unknown.
    """
    kimi_client.validate_reasoning_effort(reasoning_effort)
    api_key = kimi_client.require_api_key()

    rubric = json.loads(Path(rubric_path).read_text())
    _validate_rubric(rubric)

    tasks = []
    with open(task_results_path, newline="") as f:
        for row in csv.DictReader(f):
            tasks.append({
                "task_id": row["task_id"].strip(),
                "output": row.get("output", "").strip(),
                "context": row.get("context", "").strip(),
            })

    if not tasks:
        raise ValueError(f"No tasks found in {task_results_path}")

    system_prompt = _build_system_prompt(rubric)
    response_format = _verdict_schema(rubric)
    sleep_s = (1.0 / rate_limit) if rate_limit > 0 else 0.0

    outcome_rows: list[dict] = []
    unjudged: list[str] = []
    audit_rows: list[dict] = []

    for i, task in enumerate(tasks):
        if i > 0 and sleep_s:
            time.sleep(sleep_s)

        task_id = task["task_id"]
        try:
            user_msg = _build_user_message(task_id, task["output"], task["context"])
            kimi_resp = _call_kimi(
                system_prompt,
                user_msg,
                api_key=api_key,
                model=model,
                response_format=response_format,
                reasoning_effort=reasoning_effort,
                rubric=rubric,
            )
            out_row, audit_row = _build_outcome_row(
                task_id, kimi_resp, rubric, model, reasoning_effort
            )
            verdict = "✓" if out_row["acceptable"] == "true" else "✗"
            logger.info(
                "judge %s/%s  %s  %s  score=%.2f  %s",
                i + 1, len(tasks), verdict, task_id,
                kimi_resp.get("overall_score", 0),
                kimi_resp.get("rationale", "")[:60],
            )
        # KimiRequestError is deliberately not caught. A rejected schema, a bad
        # key, or an unknown model is a defect in the request, not a verdict
        # about the task. Swallowing it would relabel every task unacceptable and
        # report a 0% acceptable_rate that looks like real data.
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as e:
            logger.warning(
                "judge failed for %s after retries: %s. Not labelled; the task "
                "produced no evidence about its outcome.",
                task_id,
                e,
            )
            out_row, audit_row = _error_outcome_row(task_id, rubric, str(e))

        if out_row is not None:
            outcome_rows.append(out_row)
        else:
            unjudged.append(task_id)
        audit_rows.append(audit_row)

    if unjudged and not allow_unjudged:
        raise UnjudgedTasks(unjudged, len(tasks))

    # Write outcomes.csv
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_OUTCOMES_FIELDNAMES)
        writer.writeheader()
        writer.writerows(outcome_rows)

    # Write audit sidecar
    audit_path = out_path.with_name(out_path.stem + ".audit.json")
    audit_path.write_text(json.dumps(audit_rows, indent=2))

    # The rate is over tasks that were actually judged. Dividing by every task
    # submitted would report an outage as strictness, which is the same error
    # the outcomes file no longer makes.
    n_judged = len(outcome_rows)
    n_acceptable = sum(1 for r in outcome_rows if r["acceptable"] == "true")
    summary = (
        f"Judged {n_judged} of {len(tasks)} tasks: "
        f"{n_acceptable} acceptable, {n_judged - n_acceptable} not acceptable.  "
        f"Rate: {n_acceptable / n_judged:.0%}" if n_judged else
        f"Judged 0 of {len(tasks)} tasks."
    )
    if unjudged:
        summary += (
            f"\n{len(unjudged)} task(s) could not be judged and are omitted "
            "rather than labelled: " + ", ".join(unjudged)
        )
    print(f"{summary}\nOutcomes → {out_path}\nAudit    → {audit_path}")


# ── CLI entry point ───────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Label agent task outcomes using Kimi. Writes outcomes.csv."
    )
    p.add_argument("--task-results", required=True, help="CSV with task_id, output, context?")
    p.add_argument("--rubric", required=True, help="rubric.json path")
    p.add_argument("--out", required=True, help="Output outcomes.csv path")
    p.add_argument("--model", default=_DEFAULT_MODEL)
    p.add_argument("--rate-limit", type=int, default=5,
                   help="Max Kimi API calls per second (0 = unlimited)")
    p.add_argument("--reasoning-effort", choices=_REASONING_EFFORTS,
                   default=_DEFAULT_REASONING_EFFORT,
                   help="Kimi K3 reasoning depth (default: max)")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        judge(args.task_results, args.rubric, args.out,
              model=args.model, rate_limit=args.rate_limit,
              reasoning_effort=args.reasoning_effort)
        return 0
    except (RuntimeError, ValueError, OSError) as e:
        print(f"Error: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
