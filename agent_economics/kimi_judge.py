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
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_API_URL = "https://api.moonshot.ai/v1/chat/completions"
_DEFAULT_MODEL = "kimi-k3"
_TIMEOUT_S = 45

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

def _call_kimi(
    system_prompt: str,
    user_message: str,
    *,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 512,
        "reasoning_effort": "low",  # labeling; deep reasoning adds no value
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
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
    return json.loads(content)


# ── outcome row builder ───────────────────────────────────────────────────────

def _build_outcome_row(
    task_id: str,
    kimi_resp: dict,
    rubric: dict,
    model_id: str,
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
    outcomes_row = {
        "task_id": task_id,
        "acceptable": "false",
        "business_value_usd": "0",
        "human_minutes": "0",
        "remediation_cost_usd": "0",
        "incident_loss_usd": "0",
    }
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


# ── public API ────────────────────────────────────────────────────────────────

def judge(
    task_results_path: str | Path,
    rubric_path: str | Path,
    out_path: str | Path,
    *,
    model: str = _DEFAULT_MODEL,
    rate_limit: int = 5,
) -> None:
    """
    Label agent task outcomes using Kimi.

    Reads task_results_path (CSV: task_id, output, context?),
    scores each task against rubric_path,
    writes outcomes CSV to out_path (compatible with agent_economics evaluate).
    Writes audit sidecar to out_path.with_suffix('.audit.json').

    Raises RuntimeError if MOONSHOT_API_KEY is not set.
    Raises ValueError if rubric is malformed.
    """
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MOONSHOT_API_KEY not set. "
            "Get a key at https://platform.kimi.ai and export it."
        )

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
    sleep_s = (1.0 / rate_limit) if rate_limit > 0 else 0.0

    outcome_rows: list[dict] = []
    audit_rows: list[dict] = []

    for i, task in enumerate(tasks):
        if i > 0 and sleep_s:
            time.sleep(sleep_s)

        task_id = task["task_id"]
        try:
            user_msg = _build_user_message(task_id, task["output"], task["context"])
            kimi_resp = _call_kimi(
                system_prompt, user_msg, api_key=api_key, model=model
            )
            out_row, audit_row = _build_outcome_row(task_id, kimi_resp, rubric, model)
            verdict = "✓" if out_row["acceptable"] == "true" else "✗"
            logger.info(
                "judge %s/%s  %s  %s  score=%.2f  %s",
                i + 1, len(tasks), verdict, task_id,
                kimi_resp.get("overall_score", 0),
                kimi_resp.get("rationale", "")[:60],
            )
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("judge failed for %s: %s — marking unacceptable", task_id, e)
            out_row, audit_row = _error_outcome_row(task_id, rubric, str(e))

        outcome_rows.append(out_row)
        audit_rows.append(audit_row)

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

    n_acceptable = sum(1 for r in outcome_rows if r["acceptable"] == "true")
    print(
        f"Judged {len(tasks)} tasks: "
        f"{n_acceptable} acceptable, {len(tasks) - n_acceptable} not acceptable.  "
        f"Rate: {n_acceptable/len(tasks):.0%}\n"
        f"Outcomes → {out_path}\n"
        f"Audit    → {audit_path}"
    )


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
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        judge(args.task_results, args.rubric, args.out,
              model=args.model, rate_limit=args.rate_limit)
        return 0
    except (RuntimeError, ValueError, OSError) as e:
        print(f"Error: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
