"""Freeze content-free evidence from pinned public mini-SWE-agent trajectories.

This script never copies prompts, responses, patches, tool output, or reasoning.
It retains only the fields needed to reproduce the public economic case and the
SHA-256 digest of each complete upstream trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UPSTREAM_DATASET = "tarsur385/swebench-verified-trajectories"
UPSTREAM_REVISION = "b55979d6b24850b72ae4d80f912526280cd6058a"
TARGET_MODEL = "claude-opus-4.6"
REFERENCE_MODEL = "claude-4.5-haiku-high"
ELIGIBLE_TASK_IDS_SHA256 = (
    "a6b0fd7c8c2969a0eef892e032250adcfa6d32362d395c246930e61b575ac9b9"
)
SELECTED_TASK_IDS_SHA256 = (
    "539a7c78003458fb692ebc2213c0c55177d41af13a2d6f254cf9c828161be872"
)
MODEL_ALIASES = {
    TARGET_MODEL: "opus",
    REFERENCE_MODEL: "haiku",
}
TASK_IDS = (
    "astropy__astropy-12907",
    "astropy__astropy-8707",
    "django__django-11211",
    "django__django-11790",
    "django__django-12308",
    "django__django-13128",
    "django__django-13568",
    "django__django-14034",
    "django__django-14559",
    "django__django-15128",
    "django__django-15572",
    "django__django-16145",
    "django__django-16667",
    "matplotlib__matplotlib-22719",
    "matplotlib__matplotlib-25775",
    "pydata__xarray-3151",
    "pylint-dev__pylint-4551",
    "pytest-dev__pytest-7205",
    "scikit-learn__scikit-learn-13328",
    "scikit-learn__scikit-learn-9288",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _required_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _compact_run(path: Path, *, task_id: str, model: str) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if raw.get("instance_id") != task_id:
        raise ValueError(f"{path} has the wrong instance_id")
    if raw.get("trajectory_format") != "mini-swe-agent-1.1":
        raise ValueError(f"{path} has an unsupported trajectory_format")

    info = _required_mapping(raw.get("info"), f"{path}.info")
    docent = _required_mapping(info.get("docent"), f"{path}.info.docent")
    model_stats = _required_mapping(
        info.get("model_stats"), f"{path}.info.model_stats"
    )
    scores = _required_mapping(info.get("scores"), f"{path}.info.scores")
    resolved = info.get("resolved")
    if not isinstance(resolved, bool):
        raise ValueError(f"{path}.info.resolved must be boolean")
    if scores.get("resolved") != int(resolved):
        raise ValueError(f"{path} resolved fields disagree")
    if docent.get("model_label") != model:
        raise ValueError(f"{path} has the wrong model label")

    api_calls = model_stats.get("api_calls")
    if isinstance(api_calls, bool) or not isinstance(api_calls, int) or api_calls <= 0:
        raise ValueError(f"{path}.info.model_stats.api_calls must be positive")
    instance_cost = model_stats.get("instance_cost")
    if (
        isinstance(instance_cost, bool)
        or not isinstance(instance_cost, (int, float))
        or not math.isfinite(float(instance_cost))
        or float(instance_cost) <= 0
    ):
        raise ValueError(f"{path}.info.model_stats.instance_cost must be positive")

    relative_source = (
        f"swebench_verified_raw/{model}/{task_id}/{task_id}.traj.json"
    )
    return {
        "api_calls": api_calls,
        "exit_status": str(info.get("exit_status", "")),
        "instance_cost_usd": float(instance_cost),
        "model": model,
        "resolved": resolved,
        "scores_resolved": int(resolved),
        "source_path": relative_source,
        "source_sha256": _sha256_bytes(raw_bytes),
        "trajectory_format": "mini-swe-agent-1.1",
    }


def _raw_path(raw_root: Path, *, task_id: str, model: str) -> Path:
    candidates = (
        raw_root / model / task_id / f"{task_id}.traj.json",
        raw_root / MODEL_ALIASES[model] / f"{task_id}.json",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"No public trajectory found for {model}/{task_id}"
    )


def _census_task_ids(raw_root: Path) -> tuple[str, ...]:
    """Every task present for both model labels, verified against the pin.

    A census removes selection entirely, which is strictly stronger than any
    sample however well drawn. The 20-task version of this case was drawn
    outcome-blind by a documented rule, which was the right thing to do when
    the whole population was not in hand; it now is.
    """
    per_model = []
    for model in (REFERENCE_MODEL, TARGET_MODEL):
        root = raw_root / "swebench_verified_raw" / model
        if not root.is_dir():
            root = raw_root / model
        per_model.append({path.name for path in root.iterdir() if path.is_dir()})
    task_ids = tuple(sorted(per_model[0] & per_model[1]))
    digest = _sha256_bytes(
        ("".join(f"{task_id}\n" for task_id in task_ids)).encode("utf-8")
    )
    if digest != ELIGIBLE_TASK_IDS_SHA256:
        raise ValueError(
            "The eligible population on disk does not match the pinned digest: "
            f"{digest} against {ELIGIBLE_TASK_IDS_SHA256}. Either the download "
            "is incomplete or the upstream revision moved."
        )
    return task_ids


def freeze(raw_root: Path, *, census: bool = False) -> dict[str, Any]:
    task_ids = _census_task_ids(raw_root) if census else TASK_IDS
    selected_digest = _sha256_bytes(
        ("".join(f"{task_id}\n" for task_id in task_ids)).encode("utf-8")
    )
    expected = (
        ELIGIBLE_TASK_IDS_SHA256 if census else SELECTED_TASK_IDS_SHA256
    )
    if selected_digest != expected:
        raise ValueError("Frozen task selection digest is inconsistent")
    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        runs = {}
        for model in (REFERENCE_MODEL, TARGET_MODEL):
            path = _raw_path(raw_root, task_id=task_id, model=model)
            runs[model] = _compact_run(path, task_id=task_id, model=model)
        tasks.append({"task_id": task_id, "runs": runs})
    return {
        "schema": "public.swebench-paired-runs@1",
        "license": "MIT",
        "upstream": {
            "dataset": UPSTREAM_DATASET,
            "revision": UPSTREAM_REVISION,
            "dataset_url": (
                "https://huggingface.co/datasets/"
                f"{UPSTREAM_DATASET}/tree/{UPSTREAM_REVISION}"
            ),
        },
        "selection": {
            "eligible_population": (
                "task IDs present for both fixed model labels at the pinned revision"
            ),
            "order": "lexicographic task_id",
            "stride": 1 if census else 20,
            "offset": 0,
            "take": len(task_ids),
            # A census has no selection to be blind about; the flag records
            # that the 20-task sample was drawn before outcomes were seen.
            "outcome_blind": True,
            "census": census,
            "eligible_task_count": 500,
            "eligible_task_ids_sha256": ELIGIBLE_TASK_IDS_SHA256,
            "selected_task_ids_sha256": selected_digest,
            "digest_encoding": "sorted task IDs, UTF-8, one newline per ID",
        },
        "rubric": {
            "acceptable_field": "info.resolved",
            "cross_check_field": "info.scores.resolved",
            "version": "swe-bench-verified.hidden-tests@pinned-upstream",
        },
        "cost": {
            "field": "info.model_stats.instance_cost",
            "authority": "upstream client-side estimate",
            "api_call_count_field": "info.model_stats.api_calls",
        },
        "target_model": TARGET_MODEL,
        "reference_model": REFERENCE_MODEL,
        "tasks": tasks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-root",
        required=True,
        help=(
            "Downloaded swebench_verified_raw directory, or a flat "
            "opus/ and haiku/ mirror."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "runs.json"),
    )
    parser.add_argument(
        "--census",
        action="store_true",
        help=(
            "Freeze every eligible task rather than the 20-task sample. "
            "Removes selection entirely, and refuses unless the population on "
            "disk hashes to the pinned eligible digest."
        ),
    )
    args = parser.parse_args()
    output = Path(args.output)
    document = freeze(Path(args.raw_root), census=args.census)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
