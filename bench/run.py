"""Measure the engine's envelope: wall time and peak memory versus events.

The question a fleet engineer asks before reading anything else is what
happens at a million events, and until this file existed the honest answer
was "unmeasured". The workload here is synthetic *load*, never synthetic
*evidence*: it exists to exercise the code paths at controlled sizes, it is
deterministic (seeded, index-derived timestamps, no clock), and nothing it
produces is ever presented as a finding about any agent. Its bundle digest
is recorded so two machines can confirm they measured the same input.

Each scale runs the full shipped decision path, `agent_economics.audit
.decide` — engine evaluation, delegation closure, every default check, and
the audit — on an in-memory bundle. Build time is reported separately from
decision time because ingestion and decision scale differently and hiding
one inside the other would flatter both.

    python3 bench/run.py                     # 10k / 100k / 1M, writes RESULTS.json
    python3 bench/run.py --smoke             # ratio guard only, no file written

The smoke mode is the CI guard: it times two sizes 4x apart and fails if the
larger takes more than SMOKE_RATIO_LIMIT times longer. Linear scaling gives
about 4x; a quadratic regression gives about 16x; the limit sits between
them with room for CI noise on the healthy side.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import resource
import sys
import time
import tracemalloc

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_economics.audit import decide  # noqa: E402
from agent_economics.evidence import make_evidence_bundle  # noqa: E402
from agent_economics.models import (  # noqa: E402
    Baseline,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
)

RESULTS = pathlib.Path(__file__).resolve().parent / "RESULTS.json"

SCALES = (10_000, 100_000, 1_000_000)
EVENTS_PER_TASK = 20
SMOKE_SMALL, SMOKE_LARGE = 20_000, 80_000
SMOKE_RATIO_LIMIT = 10.0

MODELS = ("bench-model-a", "bench-model-b", "bench-model-c")


def build_workload(total_events: int):
    """A deterministic bundle of `total_events` events, no clock, no randomness.

    Every quantity derives from the index, so the same call on any machine
    yields a bundle with the same digest. Shapes exercised: multi-model LLM
    calls with token counts, tool calls, error statuses, and on every tenth
    task a declared delegation subtree with dependency edges, so the closure
    and the delegation gate do real work.
    """
    tasks = max(1, total_events // EVENTS_PER_TASK)
    events: list[TraceEvent] = []
    edges: list[tuple[str, str]] = []
    outcomes: dict[str, Outcome] = {}
    for t in range(tasks):
        task_id = f"task-{t:07d}"
        delegating = t % 10 == 0
        parent_for_subtree = None
        for i in range(EVENTS_PER_TASK):
            event_id = f"e-{t:07d}-{i:02d}"
            timestamp = f"2026-01-01T{(t // 3600) % 24:02d}:{(t // 60) % 60:02d}:{t % 60:02d}.{i:06d}Z"
            if i % 5 == 3:
                name = "delegate.subagent" if delegating and i == 3 else f"tool-{i % 7}"
                events.append(TraceEvent(
                    task_id=task_id,
                    event_id=event_id,
                    timestamp=timestamp,
                    event_type="tool_call",
                    name=name,
                    status="error" if (t + i) % 97 == 0 else "ok",
                ))
                if delegating and i == 3:
                    parent_for_subtree = event_id
            else:
                events.append(TraceEvent(
                    task_id=task_id,
                    event_id=event_id,
                    timestamp=timestamp,
                    event_type="llm_call",
                    name="completion",
                    model=MODELS[(t + i) % len(MODELS)],
                    input_tokens=400 + (t + i) % 300,
                    output_tokens=150 + (t * 7 + i) % 200,
                ))
                if parent_for_subtree is not None and 3 < i <= 8:
                    edges.append((parent_for_subtree, event_id))
        outcomes[task_id] = Outcome(
            task_id=task_id,
            acceptable=t % 10 < 7,
            business_value_usd=9.0,
            human_minutes=2.0,
            remediation_cost_usd=0.0 if t % 10 < 7 else 4.0,
        )
    rates = {m: ModelRate(3.0, 15.0) for m in MODELS}
    baseline = Baseline("human-only", 6.0, 0.9, 9.0)
    policy = EconomicPolicy(
        human_hourly_cost_usd=90.0,
        min_acceptable_rate=0.6,
        max_cost_per_acceptable_outcome_usd=10.0,
        max_p95_task_cost_usd=5.0,
        max_trace_cost_per_task_usd=5.0,
        max_calls_per_task=50,
        min_expected_net_value_per_attempt_usd=0.0,
    )
    return make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=baseline,
        policy=policy,
        source_id="bench.synthetic-load",
        source_version="1",
        dependency_edges=edges,
        declared_delegations=("delegate.subagent",),
        label_source="bench.no-instrument",
    )


def measure(total_events: int, repeats: int) -> dict:
    build_start = time.perf_counter()
    bundle = build_workload(total_events)
    build_seconds = time.perf_counter() - build_start

    times = []
    tracemalloc.start()
    for _ in range(repeats):
        tracemalloc.reset_peak()
        start = time.perf_counter()
        case, report = decide(bundle)
        times.append(time.perf_counter() - start)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    digest_start = time.perf_counter()
    digest = bundle.digest
    digest_seconds = time.perf_counter() - digest_start

    best = min(times)
    return {
        "events": len(bundle.events),
        "tasks": len(bundle.outcomes),
        "bundle_digest": digest,
        "build_seconds": round(build_seconds, 3),
        "decide_seconds": round(best, 3),
        "decide_events_per_second": round(len(bundle.events) / best),
        "digest_seconds": round(digest_seconds, 3),
        "decide_peak_mib": round(peak / 2**20, 1),
        "decision": case.decision.value,
        "audit_grounds": len(report.grounds),
    }


def smoke() -> int:
    small = measure(SMOKE_SMALL, repeats=2)
    large = measure(SMOKE_LARGE, repeats=2)
    ratio = large["decide_seconds"] / max(small["decide_seconds"], 1e-9)
    growth = SMOKE_LARGE / SMOKE_SMALL
    print(
        f"decide: {small['decide_seconds']}s @ {SMOKE_SMALL:,} -> "
        f"{large['decide_seconds']}s @ {SMOKE_LARGE:,} "
        f"(x{ratio:.1f} for x{growth:.0f} events; limit {SMOKE_RATIO_LIMIT})"
    )
    if ratio > SMOKE_RATIO_LIMIT:
        print(
            f"FAIL superlinear: {growth:.0f}x the events took {ratio:.1f}x "
            "the time; a linear engine takes about "
            f"{growth:.0f}x and the limit is {SMOKE_RATIO_LIMIT}",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--smoke", action="store_true",
                        help="ratio guard only; writes nothing")
    args = parser.parse_args(argv)
    if args.smoke:
        return smoke()

    runs = []
    for scale in SCALES:
        repeats = 3 if scale <= 100_000 else 1
        run = measure(scale, repeats=repeats)
        runs.append(run)
        print(
            f"{run['events']:>9,} events: decide {run['decide_seconds']}s "
            f"({run['decide_events_per_second']:,}/s), "
            f"peak {run['decide_peak_mib']} MiB, "
            f"digest {run['digest_seconds']}s, decision {run['decision']}",
            flush=True,
        )
    document = {
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.machine(),
        },
        "max_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (2**20 if sys.platform == "darwin" else 2**10),
            1,
        ),
        "workload": {
            "events_per_task": EVENTS_PER_TASK,
            "generator": "bench/run.py build_workload, deterministic, no clock",
        },
        "runs": runs,
    }
    RESULTS.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(f"\nwrote {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
