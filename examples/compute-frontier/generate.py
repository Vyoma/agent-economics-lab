"""Generate the frozen synthetic paired-budget frontier fixture.

The data are intentionally transparent and deterministic. They validate the
frontier implementation and its selection rule; they are not field evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TASK_COUNT = 180
REFERENCE_FAILURES = {0, 20, 40, 60, 80, 100, 120, 140, 160}

ARM_CONFIGS = {
    "premium-8-step": {
        "trace_cost": 1.40,
        "failures": REFERENCE_FAILURES,
        "route": "premium-all",
        "max_steps": 8,
    },
    "balanced-4-step": {
        "trace_cost": 0.75,
        "failures": (REFERENCE_FAILURES - {0, 20}) | {1},
        "route": "cheap-first-escalate",
        "max_steps": 4,
    },
    "cheap-2-step": {
        "trace_cost": 0.40,
        "failures": (REFERENCE_FAILURES - {0, 20})
        | {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
        "route": "cheap-only",
        "max_steps": 2,
    },
    "premium-12-step": {
        "trace_cost": 2.00,
        "failures": REFERENCE_FAILURES - {0, 20, 40},
        "route": "premium-all",
        "max_steps": 12,
    },
}

POLICY = {
    "human_hourly_cost_usd": 60.0,
    "min_acceptable_rate": 0.85,
    "max_cost_per_acceptable_outcome_usd": 3.0,
    "max_p95_task_cost_usd": 10.0,
    "max_trace_cost_per_task_usd": 3.0,
    "max_calls_per_task": 20,
    "min_expected_net_value_per_attempt_usd": 0.0,
    "min_incremental_net_value_vs_baseline_usd": 0.0,
    "repetition_warning_threshold": 3,
}

BASELINE = {
    "name": "human-first triage",
    "cost_per_attempt_usd": 2.0,
    "acceptable_rate": 0.80,
    "value_per_acceptable_outcome_usd": 8.0,
}


TASK_MANIFEST = [
    {
        "task_id": f"case-{index:03d}",
        "input_digest": hashlib.sha256(
            f"synthetic-support-input-{index:03d}".encode("utf-8")
        ).hexdigest(),
        "rubric_version": "support-rubric-v1",
    }
    for index in range(TASK_COUNT)
]


def task_manifest_digest() -> str:
    encoded = json.dumps(
        {"tasks": TASK_MANIFEST},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_bundle(arm_id: str, config: dict[str, object]) -> dict[str, object]:
    failures = config["failures"]
    assert isinstance(failures, set)
    events = []
    outcomes = []
    for index in range(TASK_COUNT):
        task_id = f"case-{index:03d}"
        acceptable = index not in failures
        events.append(
            {
                "task_id": task_id,
                "event_id": f"{arm_id}-event-{index:03d}",
                "timestamp": f"2026-07-01T00:{index // 60:02d}:{index % 60:02d}Z",
                "event_type": "model",
                "name": "resolve_case",
                "model": str(config["route"]),
                "input_tokens": 0,
                "output_tokens": 0,
                "direct_cost_usd": round(
                    float(config["trace_cost"]) + 0.02 * (index % 5), 2
                ),
                "status": "ok",
                "arguments": {
                    "arm_id": arm_id,
                    "route": config["route"],
                    "max_steps": config["max_steps"],
                    "prompt_version": "support-rubric-v1",
                },
            }
        )
        outcomes.append(
            {
                "task_id": task_id,
                "acceptable": acceptable,
                "business_value_usd": 8.0,
                "human_minutes": 0.0 if acceptable else 4.0,
                "remediation_cost_usd": 0.0 if acceptable else 0.5,
                "incident_loss_usd": 2.0 if index == 1 and not acceptable else 0.0,
            }
        )
    return {
        "schema_version": 1,
        "arm": {
            "id": arm_id,
            "route": config["route"],
            "max_steps": config["max_steps"],
            "prompt_version": "support-rubric-v1",
        },
        "events": events,
        "outcomes": outcomes,
        "rates": {},
        "baseline": BASELINE,
        "policy": POLICY,
    }


def main() -> None:
    arms_dir = ROOT / "arms"
    arms_dir.mkdir(parents=True, exist_ok=True)
    arm_paths = {}
    for arm_id, config in ARM_CONFIGS.items():
        relative = f"arms/{arm_id}.json"
        arm_paths[arm_id] = relative
        (ROOT / relative).write_text(
            json.dumps(build_bundle(arm_id, config), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    plan = {
        "schema_version": 1,
        "experiment_id": "synthetic-support-budget-frontier-v1",
        "reference_arm": "premium-8-step",
        "arms": arm_paths,
        "max_breakage_rate": 0.05,
        "min_cost_reduction_rate": 0.25,
        "confidence_level": 0.95,
        "bootstrap_samples": 5000,
        "seed": 20260722,
        "min_paired_tasks": 150,
        "task_manifest": "task-manifest.json",
        "task_manifest_digest": task_manifest_digest(),
    }
    (ROOT / "task-manifest.json").write_text(
        json.dumps(
            {"schema_version": 1, "tasks": TASK_MANIFEST},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (ROOT / "manifest.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
