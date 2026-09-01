"""Check the frozen evidence against the upstream dataset, row by row.

The hostile reading of research/OUTCOME_AUDIT.md is that nothing in this
repository can confirm the frozen rows match Hugging Face revision `b55979d6`
without a 740MB download, so offline the whole finding verifies only against
this repository's own file. That reading was correct. This closes it: every
frozen row names the SHA-256 of its complete upstream file, the upstream
layout is `swebench_verified_raw/<arm>/<task_id>/<task_id>.traj.json`, and
files are individually addressable at a pinned revision. Verifying a row costs
one fetch, not the corpus.

    python3 research/verify_upstream.py --sample 3          # per arm
    python3 research/verify_upstream.py --arm gemini-3-pro --all

The sample is deterministic: rows are ranked by their frozen trajectory hash,
so two people running the same command check the same rows without a seed, and
widening --sample only appends. The rows that carry the published findings are
always included: every gemini-3-pro run recording at most one API call and no
spend, and one row of the duplicated arm pair, where both files are fetched
and the transcripts are additionally required to be byte-identical under the
frozen canonical encoding while the whole files differ.

Both hashes are re-derived here, from the fetched bytes, by the same recipe
the freeze used. A mismatch is an exit 1 and names the row; so is a row that
cannot be fetched, because "could not check" must never read as "checked".
This is the one target in the research suite that requires the network, which
is why it is not part of `make reproduce`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "examples" / "public-swebench" / "outcome_audit.json"

DATASET = "tarsur385/swebench-verified-trajectories"
REVISION = "b55979d6b24850b72ae4d80f912526280cd6058a"
TWINS = ("gpt-5.2-codex", "gpt-5.2-high")


def upstream_path(arm: str, task_id: str) -> str:
    return f"swebench_verified_raw/{arm}/{task_id}/{task_id}.traj.json"


def upstream_url(arm: str, task_id: str) -> str:
    return (
        f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
        f"{upstream_path(arm, task_id)}"
    )


def rehash(raw: bytes) -> tuple[str, str]:
    """(whole-file hash, canonical transcript hash), the freeze's own recipe."""
    document = json.loads(raw)
    transcript = hashlib.sha256(
        json.dumps(document.get("messages"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return hashlib.sha256(raw).hexdigest(), transcript


def select(
    arms: dict, sample: int, only_arm: str | None, everything: bool
) -> list[tuple[tuple[str, str], dict]]:
    """Deterministic worklist: hash-ranked sample per arm plus the load-bearing rows."""
    chosen: dict[tuple[str, str], dict] = {}

    def add(arm: str, row: dict) -> None:
        chosen[(arm, row["task_id"])] = row

    for arm, rows in sorted(arms.items()):
        if only_arm and arm != only_arm:
            continue
        ranked = sorted(rows, key=lambda r: r["trajectory_sha256"])
        for row in ranked if everything else ranked[:sample]:
            add(arm, row)
    if only_arm is None:
        # The rows the published findings stand on are never left to chance.
        for row in arms["gemini-3-pro"]:
            if (row["api_calls"] or 0) <= 1 and not (row["instance_cost_usd"] or 0.0):
                add("gemini-3-pro", row)
        twin_task = min(r["task_id"] for r in arms[TWINS[0]])
        for arm in TWINS:
            add(arm, next(r for r in arms[arm] if r["task_id"] == twin_task))
    return sorted(chosen.items())


def fetch(url: str) -> bytes:
    last: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise RuntimeError(f"404 at {url}") from error
            last = error
            time.sleep(5 * (attempt + 1))
        except Exception as error:  # retried, then surfaced as a failure
            last = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=int, default=3,
                        help="rows per arm, by frozen-hash rank (default 3)")
    parser.add_argument("--arm", help="restrict to one arm")
    parser.add_argument("--all", action="store_true",
                        help="every row of the selected arms (5,000 fetches unrestricted)")
    args = parser.parse_args(argv)

    arms = json.loads(AUDIT.read_text(encoding="utf-8"))["arms"]
    worklist = select(arms, args.sample, args.arm, args.all)
    failures = []
    fetched: dict[tuple[str, str], bytes] = {}
    for (arm, task_id), row in worklist:
        try:
            raw = fetch(upstream_url(arm, task_id))
        except RuntimeError as error:
            failures.append(f"{arm}/{task_id}: UNFETCHED ({error})")
            continue
        fetched[(arm, task_id)] = raw
        whole, transcript = rehash(raw)
        if whole != row["trajectory_sha256"]:
            failures.append(
                f"{arm}/{task_id}: trajectory hash {whole[:12]} != frozen "
                f"{row['trajectory_sha256'][:12]}"
            )
        elif transcript != row["messages_sha256"]:
            failures.append(
                f"{arm}/{task_id}: transcript hash {transcript[:12]} != frozen "
                f"{row['messages_sha256'][:12]}"
            )
        else:
            print(f"ok  {arm}/{task_id}  {whole[:12]}", flush=True)

    twin_task = min(r["task_id"] for r in arms[TWINS[0]])
    twin_raw = [fetched.get((arm, twin_task)) for arm in TWINS]
    if all(twin_raw):
        a, b = twin_raw
        if a == b:
            failures.append(
                f"{twin_task}: the twin files are byte-identical upstream; the "
                "frozen evidence says they differ outside the transcript"
            )
        elif rehash(a)[1] != rehash(b)[1]:
            failures.append(
                f"{twin_task}: twin transcripts differ upstream; the duplication "
                "finding does not reproduce on this row"
            )
        else:
            print(
                f"ok  twin pair shares a transcript and differs as files "
                f"({twin_task})",
                flush=True,
            )

    checked = len(fetched)
    print(f"\nchecked {checked} of {len(worklist)} selected rows against {DATASET}@{REVISION[:8]}")
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
