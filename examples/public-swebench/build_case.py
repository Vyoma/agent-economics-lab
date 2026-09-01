"""Build the public SWE-bench AssuranceCase and paired frontier."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from agent_economics.adapters import (
    normalized_json_document,
)
from agent_economics.assurance import evaluate_bundle, percentile
from agent_economics.evidence import make_evidence_bundle
from agent_economics.frontier import run_frontier
from agent_economics.frontier_report import (
    render_frontier_json,
    render_frontier_markdown,
    render_frontier_svg,
)
from agent_economics.models import (
    Baseline,
    EconomicPolicy,
    Outcome,
    TaskIdentity,
    TraceEvent,
)
from agent_economics.report import render_markdown

ROOT = Path(__file__).resolve().parent
SOURCE_ID = "source.public-swebench-mini-agent"
SOURCE_VERSION = "1"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_source(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("runs.json must contain an object")
    if raw.get("schema") != "public.swebench-paired-runs@1":
        raise ValueError("runs.json has an unsupported schema")
    tasks = raw.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 20:
        raise ValueError("runs.json must contain exactly 20 paired tasks")
    task_ids = [row.get("task_id") for row in tasks if isinstance(row, dict)]
    if len(task_ids) != 20 or len(set(task_ids)) != 20:
        raise ValueError("runs.json task IDs must be unique")
    if task_ids != sorted(task_ids):
        raise ValueError("runs.json tasks must be sorted")
    return raw


def _run_rows(source: dict[str, Any], model: str) -> list[dict[str, Any]]:
    rows = []
    for task in source["tasks"]:
        run = task["runs"][model]
        if run["model"] != model:
            raise ValueError(f"Task {task['task_id']} has a mismatched model")
        if run["scores_resolved"] != int(run["resolved"]):
            raise ValueError(f"Task {task['task_id']} has inconsistent outcomes")
        if run["api_calls"] <= 0 or run["instance_cost_usd"] <= 0:
            raise ValueError(f"Task {task['task_id']} has invalid economics")
        rows.append({"task_id": task["task_id"], **run})
    return rows


def _paired_policy(
    reference_rows: list[dict[str, Any]],
) -> tuple[Baseline, EconomicPolicy]:
    attempts = len(reference_rows)
    accepted = sum(row["resolved"] for row in reference_rows)
    costs = [float(row["instance_cost_usd"]) for row in reference_rows]
    total = math.fsum(costs)
    mean = total / attempts
    acceptable_rate = accepted / attempts
    baseline = Baseline(
        name="mini-swe-agent + claude-4.5-haiku-high on the same 20 tasks",
        cost_per_attempt_usd=mean,
        acceptable_rate=acceptable_rate,
        value_per_acceptable_outcome_usd=0.0,
    )
    policy = EconomicPolicy(
        human_hourly_cost_usd=0.0,
        min_acceptable_rate=acceptable_rate,
        max_cost_per_acceptable_outcome_usd=total / accepted,
        max_p95_task_cost_usd=percentile(costs, 0.95),
        max_trace_cost_per_task_usd=max(costs),
        max_calls_per_task=max(int(row["api_calls"]) for row in reference_rows),
        min_expected_net_value_per_attempt_usd=0.0,
        min_incremental_net_value_vs_baseline_usd=0.0,
        repetition_warning_threshold=3,
    )
    return baseline, policy


def _task_manifest(
    source: dict[str, Any],
) -> dict[str, TaskIdentity]:
    rubric = source["rubric"]["version"]
    return {
        task["task_id"]: TaskIdentity(
            task_id=task["task_id"],
            input_digest=hashlib.sha256(
                task["task_id"].encode("utf-8")
            ).hexdigest(),
            rubric_version=rubric,
        )
        for task in source["tasks"]
    }


def _events(rows: list[dict[str, Any]]) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for row in rows:
        calls = int(row["api_calls"])
        for index in range(1, calls + 1):
            final_call = index == calls
            arguments = {
                "api_call_index": index,
                "cost_role": (
                    "observed-run-total" if final_call else "call-marker"
                ),
            }
            if final_call:
                arguments.update(
                    {
                        "observed_api_calls": calls,
                        "source_path": row["source_path"],
                        "source_sha256": row["source_sha256"],
                    }
                )
            events.append(
                TraceEvent(
                    task_id=row["task_id"],
                    event_id=(
                        f"{row['model']}:{row['task_id']}:api-call-{index:03d}"
                    ),
                    timestamp="",
                    event_type="model",
                    name="mini-swe-agent.api-call",
                    model=row["model"],
                    direct_cost_usd=(
                        float(row["instance_cost_usd"])
                        if final_call
                        else 0.0
                    ),
                    status="ok",
                    arguments=arguments,
                )
            )
    return events


def _bundle(
    source: dict[str, Any],
    *,
    model: str,
    baseline: Baseline,
    policy: EconomicPolicy,
):
    rows = _run_rows(source, model)
    outcomes = {
        row["task_id"]: Outcome(
            task_id=row["task_id"],
            acceptable=bool(row["resolved"]),
            business_value_usd=0.0,
            human_minutes=0.0,
            remediation_cost_usd=0.0,
            incident_loss_usd=0.0,
        )
        for row in rows
    }
    return make_evidence_bundle(
        events=_events(rows),
        outcomes=outcomes,
        rates={},
        baseline=baseline,
        policy=policy,
        source_id=SOURCE_ID,
        source_version=SOURCE_VERSION,
        task_manifest=_task_manifest(source),
        # What adjudicated these outcomes. The case shipped without this, so
        # every audit of it withheld on "no evidence instrument recorded" --
        # correctly, because nothing said whether the labels came from hidden
        # tests, a model, or a default. For this dataset it is the SWE-bench
        # hidden tests, and the rubric block already named them.
        label_source=source["rubric"]["version"],
    )


def _receipt(
    source: dict[str, Any],
    *,
    model: str,
    evidence_digest: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "source_version": SOURCE_VERSION,
        "evidence_digest": evidence_digest,
        "public_source_manifest_sha256": _sha256_json(source),
        "upstream_dataset": source["upstream"]["dataset"],
        "upstream_revision": source["upstream"]["revision"],
        "model": model,
        "outcome_field": source["rubric"]["acceptable_field"],
        "cost_field": source["cost"]["field"],
        "task_count": len(source["tasks"]),
        "claim_scope": "public benchmark, trace spend only, zero monetized value",
    }


def _render_frontier_bundle(bundle, receipt: dict[str, Any]) -> str:
    document = normalized_json_document(bundle, conversion=receipt)
    document["schema_version"] = 1
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _task_manifest_document(source: dict[str, Any]) -> dict[str, Any]:
    manifest = _task_manifest(source)
    return {
        "schema_version": 1,
        "tasks": [
            {
                "task_id": task_id,
                "input_digest": manifest[task_id].input_digest,
                "rubric_version": manifest[task_id].rubric_version,
            }
            for task_id in sorted(manifest)
        ],
    }


def _task_manifest_digest(document: dict[str, Any]) -> str:
    return _sha256_json({"tasks": document["tasks"]})


def build(source_path: Path, output_dir: Path) -> None:
    source = _load_source(source_path)
    target_model = source["target_model"]
    reference_model = source["reference_model"]
    reference_rows = _run_rows(source, reference_model)
    baseline, policy = _paired_policy(reference_rows)
    target_bundle = _bundle(
        source,
        model=target_model,
        baseline=baseline,
        policy=policy,
    )
    reference_bundle = _bundle(
        source,
        model=reference_model,
        baseline=baseline,
        policy=policy,
    )

    arms_dir = output_dir / "arms"
    frontier_dir = output_dir / "frontier"
    arms_dir.mkdir(parents=True, exist_ok=True)
    frontier_dir.mkdir(parents=True, exist_ok=True)
    target_path = arms_dir / "candidate-opus.json"
    reference_path = arms_dir / "reference-haiku.json"
    target_path.write_text(
        _render_frontier_bundle(
            target_bundle,
            _receipt(
                source,
                model=target_model,
                evidence_digest=target_bundle.digest,
            ),
        ),
        encoding="utf-8",
    )
    reference_path.write_text(
        _render_frontier_bundle(
            reference_bundle,
            _receipt(
                source,
                model=reference_model,
                evidence_digest=reference_bundle.digest,
            ),
        ),
        encoding="utf-8",
    )
    (output_dir / "assurance-case.md").write_text(
        render_markdown(evaluate_bundle(target_bundle)),
        encoding="utf-8",
    )

    task_manifest = _task_manifest_document(source)
    (output_dir / "task-manifest.json").write_text(
        json.dumps(task_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    plan = {
        "schema_version": 1,
        "experiment_id": "public-swebench-opus-vs-haiku-20-paired-v1",
        "reference_arm": "reference-haiku",
        "arms": {
            "candidate-opus": "arms/candidate-opus.json",
            "reference-haiku": "arms/reference-haiku.json",
        },
        "max_breakage_rate": 0.05,
        "min_cost_reduction_rate": 0.0,
        "confidence_level": 0.95,
        "bootstrap_samples": 10000,
        "seed": 20260728,
        "min_paired_tasks": 20,
        "task_manifest": "task-manifest.json",
        "task_manifest_digest": _task_manifest_digest(task_manifest),
    }
    plan_path = output_dir / "manifest.json"
    plan_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    frontier = run_frontier(plan_path)
    (frontier_dir / "frontier.md").write_text(
        render_frontier_markdown(frontier),
        encoding="utf-8",
    )
    (frontier_dir / "frontier.json").write_text(
        render_frontier_json(frontier),
        encoding="utf-8",
    )
    (frontier_dir / "frontier.svg").write_text(
        render_frontier_svg(frontier),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(ROOT / "runs.json"))
    parser.add_argument(
        "--output-dir",
        default="/tmp/agent-economics-public-swebench",
    )
    args = parser.parse_args()
    build(Path(args.source), Path(args.output_dir))
    print(f"Wrote public case to {args.output_dir}")


if __name__ == "__main__":
    main()
