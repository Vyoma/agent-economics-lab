"""Freeze content-free outcome evidence across model arms of the public dataset.

The paired economic case in this directory uses two arms. This looks at every
arm that could be downloaded and asks one question of each trajectory: does the
outcome field agree with the cross-check field beside it.

It copies no prompts, responses, patches, tool output, or reasoning. Per
trajectory it retains the two outcome fields, the two published cost figures,
and the SHA-256 of the complete upstream file so anyone can confirm the row
against the source.

The reason this exists: `info.resolved` reads as an adjudicated outcome, and for
one arm it is `true` on all 500 tasks while `info.scores.resolved` is the string
`"unknown"` on all 500. A 100% resolution rate on SWE-bench Verified is not a
result anyone has achieved, so that field is a default that scoring never
overwrote. The dataset is not at fault: it ships the cross-check that reveals
this. A consumer reading one field is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UPSTREAM_DATASET = "tarsur385/swebench-verified-trajectories"
UPSTREAM_REVISION = "b55979d6b24850b72ae4d80f912526280cd6058a"


def _row(path: Path) -> dict[str, Any] | None:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except ValueError:
        return None
    if document.get("trajectory_format") != "mini-swe-agent-1.1":
        return None
    info = document.get("info") or {}
    stats = info.get("model_stats") or {}
    scores = info.get("scores") or {}
    return {
        "task_id": document.get("instance_id"),
        "resolved": info.get("resolved"),
        "scores_resolved": scores.get("resolved"),
        "api_calls": stats.get("api_calls"),
        "instance_cost_usd": stats.get("instance_cost"),
        "trajectory_sha256": hashlib.sha256(raw).hexdigest(),
    }


def freeze(arms: dict[str, Path]) -> dict[str, Any]:
    frozen: dict[str, Any] = {}
    for arm, root in sorted(arms.items()):
        rows = [row for path in sorted(root.rglob("*.json")) if (row := _row(path))]
        if not rows:
            # An arm that produced nothing is omitted rather than recorded as
            # empty. A rate-limited download is not evidence of anything, and a
            # zero-row arm in the table would read as one.
            continue
        frozen[arm] = sorted(rows, key=lambda item: item["task_id"] or "")
    return {
        "schema": "public.swebench-outcome-audit@1",
        "license": "MIT",
        "upstream": {
            "dataset": UPSTREAM_DATASET,
            "revision": UPSTREAM_REVISION,
            "dataset_url": (
                f"https://huggingface.co/datasets/{UPSTREAM_DATASET}"
                f"/tree/{UPSTREAM_REVISION}"
            ),
        },
        "question": (
            "For each trajectory, does info.resolved agree with "
            "info.scores.resolved beside it?"
        ),
        "arms": frozen,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arm", action="append", required=True, metavar="NAME=PATH",
        help="Model arm and the directory holding its trajectories. Repeatable.",
    )
    parser.add_argument("--output", default=str(ROOT / "outcome_audit.json"))
    args = parser.parse_args()
    arms = {}
    for entry in args.arm:
        name, _, path = entry.partition("=")
        arms[name] = Path(path)
    document = freeze(arms)
    Path(args.output).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output}: {len(document['arms'])} arms")


if __name__ == "__main__":
    main()
