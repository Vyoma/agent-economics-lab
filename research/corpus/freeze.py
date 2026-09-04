"""Freeze content-free audit evidence from a public trajectory dataset.

One command per dataset, network required once, everything downstream offline:

    python3 research/corpus/freeze.py coderforge
    python3 research/corpus/freeze.py jetbrains

Per row it keeps identifiers, outcome fields, step counts, SHA-256 hashes of
the content it refuses to copy, and — where the dataset ships raw test logs
beside graded-test lists — the re-adjudication verdict those logs support.
No prompts, no responses, no patches, no logs are stored.

Rows come from the Hugging Face datasets-server, which serves the dataset's
current revision and takes no revision parameter. That would be an unpinned
measurement, so the freeze brackets the fetch: it records the repository's
commit SHA before the first page and refuses to write anything if the SHA
after the last page differs. The frozen file then names the exact commit all
of its rows came from.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from parse_tests import readjudicate  # type: ignore[import-not-found]

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"

_ROWS_API = "https://datasets-server.huggingface.co/rows"
_INFO_API = "https://huggingface.co/api/datasets"


def _get(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(7):
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                return json.load(response)
        except Exception as error:  # retried, then re-raised
            last = error
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def _sha_now(dataset: str) -> str:
    return _get(f"{_INFO_API}/{urllib.parse.quote(dataset, safe='/')}")["sha"]


#: A checkpoint rewrites every row fetched so far, so writing one per page
#: costs O(n^2) bytes over a freeze. Measured on the corpus: 27GB of writes
#: for the 66k-row dataset and 632GB for the 318k-row one, to protect work
#: that is cheap to refetch. Every 25 pages bounds that to a fortieth while
#: risking at most 25 pages - a couple of minutes - on an interruption.
CHECKPOINT_EVERY_PAGES = 25


def _write_checkpoint(
    path: pathlib.Path, revision: str, offset: int, rows: list[dict]
) -> None:
    """Atomic: a freeze killed mid-write must not leave a truncated resume.

    The point of the checkpoint is to survive being killed, and the moment
    it is most likely to be killed is while it is writing.
    """
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"revision": revision, "offset": offset, "rows": rows}),
        encoding="utf-8",
    )
    temporary.replace(path)


def _extracted_rows(
    slug: str,
    spec: Mapping[str, Any],
    revision: str,
    page_length: int = 100,
) -> list[dict]:
    """Fetch page by page, extract immediately, and checkpoint as we go.

    The largest dataset in this corpus took twenty hours of paging, and this
    function had no memory: an interruption at hour nineteen was worth
    exactly as much as one at minute one. The sibling freezer for
    PostTrainBench was made resumable and this one, which does the same job
    for every other dataset, was left as it was - the defect this repository
    keeps naming, committed here by the person naming it.

    Extraction happens per page rather than at the end, and that turns out
    to matter more for memory than for the checkpoint. The previous version
    accumulated every raw row and extracted once at the end, so a freeze
    held the entire dataset resident: the 318k-row, 12GB nvidia-swezero
    freeze reached 2GB of RSS after twenty hours, put the machine into
    heavy swap, and was still nowhere near the 12GB it would have needed to
    finish. Measured against this version doing the same class of work on a
    comparable dataset: 23MB. The restructure was written for resumability
    and silently fixed an unbounded accumulation that could never have
    completed on the largest entry in the corpus.

    It also keeps the checkpoint content-free, since checkpointing raw pages
    would write gigabytes of trajectories to disk - the thing the whole
    freeze exists to avoid.
    """
    checkpoint = FROZEN / f"{slug}.partial.json"
    extracted: list[dict] = []
    offset = 0
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved.get("revision") != revision:
            raise RuntimeError(
                f"{checkpoint.name} is for revision "
                f"{saved.get('revision', '?')[:8]}, upstream is now "
                f"{revision[:8]}; delete it to refreeze from scratch"
            )
        extracted = saved["rows"]
        offset = saved["offset"]
        print(f"resuming {slug} at row {offset:,}", flush=True)

    total = spec["expected_rows"]
    pages_since_checkpoint = 0
    # `page_length` and the fetched page must not share a name: a first draft
    # assigned the response dict over the length parameter, and every request
    # after the first urlencoded a nine-megabyte page as `length=`.
    while True:
        query = urllib.parse.urlencode(
            {"dataset": spec["dataset"], "config": spec["config"],
             "split": spec["split"], "offset": offset, "length": page_length}
        )
        document = _get(f"{_ROWS_API}?{query}")
        for wrapper in document["rows"]:
            if wrapper.get("truncated_cells"):
                raise RuntimeError(
                    f"row {offset} truncated cells {wrapper['truncated_cells']}: "
                    "a hash of a truncated cell would be a hash of nothing"
                )
            extracted.append(spec["extract"](wrapper["row"]))
        offset += len(document["rows"])
        done = offset >= document.get("num_rows_total", 0) or not document["rows"]
        pages_since_checkpoint += 1
        if pages_since_checkpoint >= CHECKPOINT_EVERY_PAGES or done:
            _write_checkpoint(checkpoint, revision, offset, extracted)
            pages_since_checkpoint = 0
        if offset % (page_length * 20) == 0 or done:
            print(f"  {slug}: {offset:,}/{total:,} rows", flush=True)
        if done:
            return extracted


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _coderforge(row: dict) -> dict:
    ds = json.loads(row["ds"]) if isinstance(row.get("ds"), str) else (row.get("ds") or {})
    f2p, p2p = ds.get("FAIL_TO_PASS"), ds.get("PASS_TO_PASS")
    if isinstance(f2p, str):
        f2p = json.loads(f2p)
    if isinstance(p2p, str):
        p2p = json.loads(p2p)
    log = row.get("test_output") or ""
    frozen = {
        "id": row.get("trajectory_id"),
        "instance_id": ds.get("instance_id"),
        "outcome": row.get("reward"),
        "steps": row.get("num_steps"),
        "transcript_sha256": _sha256(_canonical(row.get("messages"))),
        "patch_sha256": _sha256(row.get("output_patch") or ""),
        "log_sha256": _sha256(log),
        "log_bytes": len(log.encode()),
    }
    if f2p is not None and p2p is not None and log:
        frozen["graded"] = {
            "f2p_n": len(f2p),
            "p2p_n": len(p2p),
            **readjudicate(log, f2p, p2p),
        }
    return frozen


def _jetbrains(row: dict) -> dict:
    return {
        "id": row.get("instance_id"),
        "instance_id": row.get("instance_id"),
        "outcome": row.get("resolved"),
        "cross": row.get("exit_status"),
        "steps": row.get("n_turns"),
        "transcript_sha256": _sha256(_canonical(row.get("messages"))),
    }


def _swesmith(row: dict) -> dict:
    patch = row.get("patch") or ""
    return {
        "id": row.get("traj_id"),
        "instance_id": row.get("instance_id"),
        "outcome": row.get("resolved"),
        "model": row.get("model"),
        "patch_sha256": _sha256(patch),
        "patch_empty": patch == "",
        # Added after the first freeze: hash equality across repositories is
        # only interesting when the patch is non-trivial, and settling that
        # took a re-fetch (patch_check.py). Committed swesmith files predate
        # this field; a re-freeze carries it.
        "patch_bytes": len(patch.encode()),
        "transcript_sha256": _sha256(_canonical(row.get("messages"))),
    }


def _kwai_klear(row: dict) -> dict:
    """A SWE-smith derivative that kept the transcripts and dropped the rest.

    Two columns survive: instance_id and messages. No outcome label, so a
    consumer cannot filter this training set by whether the trajectory
    succeeded, and no patch, so the misalignment recorded against the parent
    dataset cannot be checked here at all. Both absences are the audit.
    """
    messages = row.get("messages") or []
    return {
        "id": row.get("instance_id"),
        "instance_id": row.get("instance_id"),
        # Present so the census can say "absent", rather than the schema
        # quietly not mentioning outcomes at all.
        "outcome": row.get("resolved"),
        "message_count": len(messages),
        "transcript_sha256": _sha256(_canonical(messages)),
        "roles_sha256": _sha256(
            _canonical([m.get("role") for m in messages])
        ),
    }


def _nebius_sweagent(row: dict) -> dict:
    patch = row.get("generated_patch") or ""
    logs = row.get("eval_logs") or ""
    return {
        "id": f"{row.get('instance_id')}::{row.get('model_name')}",
        "instance_id": row.get("instance_id"),
        "model": row.get("model_name"),
        "outcome": row.get("target"),
        "exit_status": row.get("exit_status"),
        "patch_sha256": _sha256(patch),
        "patch_empty": patch.strip() == "",
        "patch_bytes": len(patch.encode()),
        "eval_logs_sha256": _sha256(logs),
        "eval_logs_bytes": len(logs.encode()),
        "transcript_sha256": _sha256(_canonical(row.get("trajectory"))),
    }


def _nebius_openhands(row: dict) -> dict:
    patch = row.get("model_patch") or ""
    return {
        "id": row.get("trajectory_id"),
        "instance_id": row.get("instance_id"),
        "repo": row.get("repo"),
        "outcome": row.get("resolved"),
        "cross": row.get("pred_passes_gen_tests"),
        "gen_tests_correct": row.get("gen_tests_correct"),
        "exit_status": row.get("exit_status"),
        "patch_sha256": _sha256(patch),
        "patch_empty": patch.strip() == "",
        "patch_bytes": len(patch.encode()),
        "transcript_sha256": _sha256(_canonical(row.get("trajectory"))),
    }


def _nvidia_swezero(row: dict) -> dict:
    patch = row.get("model_patch") or ""
    return {
        "id": row.get("trajectory_id"),
        "instance_id": row.get("instance_id"),
        "repo": row.get("repo"),
        "source_dataset": row.get("dataset"),
        # No outcome field exists upstream; recorded as None so the census
        # says "unlabelled" rather than silently omitting the dimension.
        "outcome": row.get("resolved"),
        "patch_sha256": _sha256(patch),
        "patch_empty": patch.strip() == "",
        "patch_bytes": len(patch.encode()),
        "transcript_sha256": _sha256(_canonical(row.get("trajectory"))),
    }


SPECS = {
    "coderforge": {
        "dataset": (
            "togethercomputer/"
            "CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories"
        ),
        "config": "trajectory",
        "split": "train",
        "expected_rows": 500,
        "outcome_field": "reward",
        "cross_field": None,
        "extract": _coderforge,
        "license": "apache-2.0",
    },
    # The official SWE-bench organisation's training-trajectory release.
    # Three splits, one per action format; each is frozen as its own file
    # because the split is part of the row's identity upstream. Pages of 50:
    # these transcripts are heavy enough that 100-row pages time out.
    "swesmith-tool": {
        "dataset": "SWE-bench/SWE-smith-trajectories",
        "config": "default",
        "split": "tool",
        "page_length": 50,
        "expected_rows": 24100,
        "outcome_field": "resolved",
        "cross_field": None,
        "extract": _swesmith,
        "license": "mit",
    },
    "swesmith-xml": {
        "dataset": "SWE-bench/SWE-smith-trajectories",
        "config": "default",
        "split": "xml",
        "page_length": 50,
        "expected_rows": 26076,
        "outcome_field": "resolved",
        "cross_field": None,
        "extract": _swesmith,
        "license": "mit",
    },
    "swesmith-ticks": {
        "dataset": "SWE-bench/SWE-smith-trajectories",
        "config": "default",
        "split": "ticks",
        "page_length": 50,
        "expected_rows": 25826,
        "outcome_field": "resolved",
        "cross_field": None,
        "extract": _swesmith,
        "license": "mit",
    },
    # Nebius's SWE-agent training trajectories: labels plus the raw
    # evaluation logs, which permit CoderForge-style re-adjudication.
    "nebius-sweagent": {
        "dataset": "nebius/SWE-agent-trajectories",
        "config": "default",
        "split": "train",
        "page_length": 50,
        "expected_rows": 80036,
        "outcome_field": "target",
        "cross_field": None,
        "extract": _nebius_sweagent,
        "license": "cc-by-4.0",
    },
    # Nebius's OpenHands trajectories over SWE-rebench: a resolved label
    # beside a generated-test cross-signal, the tarsur385 shape.
    "nebius-openhands": {
        "dataset": "nebius/SWE-rebench-openhands-trajectories",
        "config": "default",
        "split": "train",
        "page_length": 50,
        "expected_rows": 67074,
        "outcome_field": "resolved",
        "cross_field": "pred_passes_gen_tests",
        "extract": _nebius_openhands,
        "license": "cc-by-4.0",
    },
    # NVIDIA's SWE-Zero OpenHands trajectories: 318k rows, no outcome
    # column, and a per-row `dataset` provenance pointer into other public
    # training sets. Both facts are the audit.
    "nvidia-swezero": {
        "dataset": "nvidia/SWE-Zero-openhands-trajectories",
        "config": "default",
        "split": "train",
        "page_length": 50,
        "expected_rows": 318115,
        "outcome_field": "resolved",
        "cross_field": None,
        "extract": _nvidia_swezero,
        "license": "cc-by-4.0",
    },
    # A widely-used training set derived from SWE-smith trajectories. The
    # question this corpus can ask that the dataset cannot answer for
    # itself: what survives derivation, and what silently does not.
    "kwai-klear": {
        "dataset": "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
        "config": "default",
        "split": "train",
        "page_length": 20,
        "expected_rows": 65994,
        "outcome_field": "resolved",
        "cross_field": None,
        "extract": _kwai_klear,
        "license": "mit",
    },
    "jetbrains": {
        "dataset": "JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified",
        "config": "default",
        "split": "train",
        "expected_rows": 1785,
        "outcome_field": "resolved",
        "cross_field": "exit_status",
        "extract": _jetbrains,
        "license": "apache-2.0",
    },
}


def freeze(slug: str) -> pathlib.Path:
    spec = SPECS[slug]
    sha_before = _sha_now(spec["dataset"])
    rows = _extracted_rows(
        slug, spec, sha_before, page_length=spec.get("page_length", 100)
    )
    sha_after = _sha_now(spec["dataset"])
    if sha_before != sha_after:
        raise RuntimeError(
            f"{spec['dataset']} moved {sha_before[:8]} -> {sha_after[:8]} "
            "during the fetch; the pages are not one snapshot. Re-run."
        )
    if len(rows) != spec["expected_rows"]:
        raise RuntimeError(
            f"{spec['dataset']}: fetched {len(rows)} rows, expected "
            f"{spec['expected_rows']}. A partial arm is a sample presented "
            "as a census; refusing to freeze it."
        )
    document = {
        "dataset": spec["dataset"],
        "revision": sha_before,
        "config": spec["config"],
        "split": spec["split"],
        "outcome_field": spec["outcome_field"],
        "cross_field": spec["cross_field"],
        "license": spec["license"],
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fetched_via": "datasets-server /rows, revision bracketed by repo SHA",
        "rows": rows,
    }
    FROZEN.mkdir(exist_ok=True)
    path = FROZEN / f"{slug}.json"
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (FROZEN / f"{slug}.partial.json").unlink(missing_ok=True)
    return path


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in SPECS:
        print(f"usage: freeze.py {{{'|'.join(SPECS)}}}", file=sys.stderr)
        return 2
    path = freeze(argv[1])
    print(f"froze {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    sys.exit(main(sys.argv))
