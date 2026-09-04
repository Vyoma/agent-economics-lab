"""Freeze PostTrainBench agent traces: the most-downloaded, and a new shape.

Every other entry in this corpus is a table of trajectories with an outcome
column. This one is a directory tree of autonomous runs: an agent is given a
base model, an evaluation script, and ten hours on an H100, and told to make
the model better. That is the "give it a machine and a goal" shape the field
keeps saying should replace benchmarks, published by the most-downloaded
agent-trajectory dataset on the hub, and nobody has audited it.

What makes it auditable is that each run records three independent things:

* `metrics.json` - the **measured** benchmark accuracy after post-training.
  Not a judge's opinion; the evaluation script's number.
* `judgement_*.json` - an **LLM judge's integrity verdict**: did the agent
  contaminate its training data with the benchmark, and did it train the
  base model it was told to train. This is an instrument, and like every
  instrument in this corpus the question is what validates it.
* `time_taken.txt` - the wall clock, against a ten-hour budget on hardware
  with a published hourly price. Runs here cost real money, which makes the
  economic questions this package exists to ask answerable directly.

The freeze is content-free in the same way as every other: identifiers,
numbers, booleans and hashes, never the traces themselves. `solve_out.txt`
is often over a megabyte and is never fetched; only its presence and size
are recorded from the listing.

    python3 research/corpus/freeze_posttrainbench.py

Writes research/corpus/frozen/posttrainbench.json, bracketing the dataset
revision before and after so a mid-run upstream change is caught rather than
silently mixed.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
OUT = FROZEN / "posttrainbench.json"

DATASET = "aisa-group/PostTrainBench-Trajectories"
_API = "https://huggingface.co/api/datasets"
_FILES = "https://huggingface.co/datasets"

#: Fetched per run. Everything else in a run directory is a transcript or a
#: checkpoint, and neither belongs in a content-free freeze.
SMALL_FILES = ("metrics.json", "time_taken.txt")

#: Runs live at group/run; anything deeper is the agent's own workspace.
SKIP_GROUPS = {"viewer_data"}


def _get(url: str, *, raw: bool = False):
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                payload = response.read()
                return payload if raw else json.loads(payload)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last = error
            time.sleep(5 * (attempt + 1))
        except Exception as error:
            last = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def _revision() -> str:
    return _get(f"{_API}/{urllib.parse.quote(DATASET, safe='/')}")["sha"]


def _tree(path: str = "") -> list[dict]:
    suffix = f"/{urllib.parse.quote(path)}" if path else ""
    return _get(f"{_API}/{urllib.parse.quote(DATASET, safe='/')}/tree/main{suffix}") or []


def _file(path: str) -> bytes | None:
    return _get(
        f"{_FILES}/{urllib.parse.quote(DATASET, safe='/')}/resolve/main/"
        f"{urllib.parse.quote(path)}",
        raw=True,
    )


def _duration_seconds(text: str) -> int | None:
    """`08:54:34` -> seconds. Anything else is unparsed, never guessed."""
    parts = text.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (int(p) for p in parts)
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _run_row(group: str, run: str) -> dict | None:
    listing = _tree(f"{group}/{run}")
    names = {
        entry["path"].split("/")[-1]: entry
        for entry in listing
        if entry.get("type") == "file"
    }

    # A malformed file is recorded as malformed. Not as missing, which would
    # understate how many runs lack a usable outcome, and not as zero, which
    # would invent one. The first freeze crashed on a metrics.json that is
    # not valid JSON, which is itself a fact about this dataset.
    metrics_raw = _file(f"{group}/{run}/metrics.json") if "metrics.json" in names else None
    metrics: dict = {}
    metrics_malformed = False
    if metrics_raw:
        try:
            parsed = json.loads(metrics_raw)
            metrics = parsed if isinstance(parsed, dict) else {}
            metrics_malformed = not isinstance(parsed, dict)
        except ValueError:
            metrics_malformed = True

    judge_name = next(
        (n for n in sorted(names) if n.startswith("judgement_") and n.endswith(".json")),
        None,
    )
    judge: dict = {}
    judge_malformed = False
    if judge_name:
        judge_raw = _file(f"{group}/{run}/{judge_name}")
        if judge_raw:
            try:
                parsed = json.loads(judge_raw)
                judge = parsed if isinstance(parsed, dict) else {}
                judge_malformed = not isinstance(parsed, dict)
            except ValueError:
                judge_malformed = True

    duration = None
    if "time_taken.txt" in names:
        taken = _file(f"{group}/{run}/time_taken.txt")
        if taken:
            duration = _duration_seconds(taken.decode("utf-8", "replace"))

    # `aime2025_Qwen_Qwen3-1.7B-Base_17415289` -> benchmark, base model, id
    benchmark, _, remainder = run.partition("_")
    base_model, _, run_id = remainder.rpartition("_")
    return {
        "id": f"{group}/{run}",
        "group": group,
        "benchmark": benchmark,
        "base_model": base_model,
        "run_id": run_id,
        # the measured outcome, from the evaluation script
        "accuracy": metrics.get("accuracy"),
        "stderr": metrics.get("stderr"),
        "has_metrics": bool(metrics_raw),
        "metrics_malformed": metrics_malformed,
        "judge_malformed": judge_malformed,
        # the judge's integrity verdict, and whether one exists at all
        "judge_file": judge_name or "",
        "contamination": judge.get("contamination"),
        "disallowed_model": judge.get("disallowed_model"),
        "judge_sha256": hashlib.sha256(
            json.dumps(judge, sort_keys=True).encode("utf-8")
        ).hexdigest() if judge else "",
        "duration_seconds": duration,
        # presence and size only; the transcript itself is never fetched
        "solve_out_bytes": names.get("solve_out.txt", {}).get("size"),
        "error_log_bytes": names.get("error.log", {}).get("size"),
        "file_names": sorted(names),
    }


def freeze() -> dict:
    before = _revision()
    groups = [
        entry["path"]
        for entry in _tree()
        if entry.get("type") == "directory" and entry["path"] not in SKIP_GROUPS
    ]
    rows: list[dict] = []
    for index, group in enumerate(sorted(groups), start=1):
        runs = [
            entry["path"].split("/")[-1]
            for entry in _tree(group)
            if entry.get("type") == "directory"
        ]
        for run in sorted(runs):
            rows.append(_run_row(group, run))
        print(
            f"[{index}/{len(groups)}] {group}: {len(runs)} runs "
            f"({len(rows)} total)",
            flush=True,
        )
    after = _revision()
    if before != after:
        raise RuntimeError(
            f"dataset moved during the freeze ({before[:8]} -> {after[:8]}); "
            "rows from two revisions must never be mixed"
        )
    return {
        "dataset": DATASET,
        "revision": before,
        "license": "apache-2.0",
        "question": "do the measured outcomes, the integrity judge, and the "
                    "ten-hour budget agree with each other",
        "schema": "corpus.posttrainbench@1",
        "groups": len(groups),
        "rows": rows,
    }


def main() -> int:
    document = freeze()
    FROZEN.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"froze {len(document['rows'])} runs across {document['groups']} groups "
        f"-> {OUT.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
