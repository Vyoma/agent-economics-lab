"""Freeze Collaborative Gym trajectories: human ratings, and a new domain.

Every other entry in this corpus audits a coding agent, and every outcome
instrument in it is automated - a cross-check column, a re-adjudication from
logs, model-generated tests, an LLM judge. This dataset is neither. It holds
228 real human-agent collaboration sessions on travel planning, related-work
writing and tabular analysis, and the outcome labels are ratings typed by
the human who was in the session.

That makes it the one entry where the instrument is the thing every other
instrument is validated against. Each session carries up to three Likert
ratings from the same person: the artifact (`outcomeRating`), overall
satisfaction (`agentRating`), and the agent's communication
(`communicationRating`). They are separate questions, so they need not
agree - but a reader treating "human rating" as a single number should know
how far apart they run, and every automated instrument in this corpus is
scored against exactly this kind of judgement.

Content-free, and more carefully than usual because these are real people:
ratings, counts, task and model names, and hashes. Never the query, never
the feedback text, never the event log. Whether feedback exists is recorded;
what it says is not.

    python3 research/corpus/freeze_cogym.py

Writes research/corpus/frozen/cogym.json, bracketing the dataset revision so
a mid-run upstream change is caught rather than silently mixed.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
OUT = FROZEN / "cogym.json"

DATASET = "SALT-NLP/cogym-real-trajectories"
_API = f"https://huggingface.co/api/datasets/{DATASET}"
_FILES = f"https://huggingface.co/datasets/{DATASET}/resolve/main"

RATINGS = ("outcomeRating", "agentRating", "communicationRating")


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
            time.sleep(4 * (attempt + 1))
        except Exception as error:
            last = error
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}") from last


def _rating(value: object) -> int | None:
    """A Likert value, or None. Never coerced: 'not provided' is a fact."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _row(name: str, payload: bytes) -> dict:
    session = json.loads(payload)
    events = session.get("event_log") or []
    roles = [e.get("role") for e in events if isinstance(e, dict)]
    return {
        "id": name.removeprefix("session_").removesuffix(".json"),
        "task": session.get("task"),
        "model": session.get("modelName"),
        **{key: _rating(session.get(key)) for key in RATINGS},
        "has_feedback": bool((session.get("agentFeedback") or "").strip()),
        "event_count": len(events),
        "human_events": sum(1 for r in roles if r == "user"),
        "agent_events": sum(1 for r in roles if r == "agent"),
        "session_bytes": len(payload),
        # The transcript is hashed and discarded: enough to prove the freeze
        # read this session and nothing about what anyone said in it.
        "event_log_sha256": hashlib.sha256(
            json.dumps(events, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }


def freeze() -> dict:
    before = _get(_API)["sha"]
    listing = _get(f"{_API}/tree/main")
    names = sorted(
        entry["path"] for entry in listing
        if entry.get("type") == "file" and entry["path"].startswith("session_")
    )
    rows = []
    for index, name in enumerate(names, start=1):
        payload = _get(f"{_FILES}/{name}", raw=True)
        if payload is None:
            raise RuntimeError(f"{name} vanished mid-freeze")
        rows.append(_row(name, payload))
        if index % 25 == 0 or index == len(names):
            print(f"  cogym: {index}/{len(names)} sessions", flush=True)
    after = _get(_API)["sha"]
    if before != after:
        raise RuntimeError(
            f"dataset moved during the freeze ({before[:8]} -> {after[:8]}); "
            "rows from two revisions must never be mixed"
        )
    return {
        "dataset": DATASET,
        "revision": before,
        "license": "cc-by-sa-4.0",
        "question": "how far apart do one person's ratings of one session run",
        "schema": "corpus.cogym@1",
        "rows": rows,
    }


def main() -> int:
    document = freeze()
    FROZEN.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"froze {len(document['rows'])} sessions -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
