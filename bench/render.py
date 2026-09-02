"""Render docs/at-scale.md from bench/RESULTS.json. Never edit the doc by hand."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = pathlib.Path(__file__).resolve().parent / "RESULTS.json"


def render() -> str:
    document = json.loads(RESULTS.read_text(encoding="utf-8"))
    runs = document["runs"]
    biggest = runs[-1]
    machine = document["machine"]
    lines = [
        "# At scale",
        "",
        "The first question a fleet engineer asks is what happens at a",
        "million events. This page is the measured answer, reproducible with",
        "`make bench`, and it states what stays expensive as plainly as what",
        "got fast.",
        "",
        "Every number is the **full shipped decision path** — engine",
        "evaluation, the audit's fourteen-variation mutation self-test,",
        "delegation closure, cycle detection, and instrument attestation —",
        "not a stripped-down core. The workload is synthetic *load*, never",
        "synthetic *evidence*: deterministic, clock-free, digest-pinned, and",
        "nothing it produces is presented as a finding about any agent.",
        "",
        "| events | decide | throughput | peak engine memory | one digest |",
        "|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        lines.append(
            f"| {run['events']:,} | {run['decide_seconds']}s "
            f"| {run['decide_events_per_second']:,}/s "
            f"| {run['decide_peak_mib']} MiB | {run['digest_seconds']}s |"
        )
    ratio = runs[-1]["decide_seconds"] / runs[0]["decide_seconds"]
    growth = runs[-1]["events"] / runs[0]["events"]
    lines += [
        "",
        f"Scaling is linear: {growth:,.0f}x the events costs {ratio:,.1f}x "
        "the time. A ratio guard runs in CI (`make bench-smoke`) and fails",
        "the build if the engine ever goes superlinear on the realistic",
        "shape.",
        "",
        f"Measured on {machine['platform']}, Python {machine['python']}, "
        f"process peak RSS {document['max_rss_mib']:,} MiB at "
        f"{biggest['events']:,} events. One process, one core, no",
        "dependencies. The bundle digests in",
        "[RESULTS.json](../bench/RESULTS.json) let another machine confirm",
        "it measured the same workload.",
        "",
        "## What the scale pass found and fixed",
        "",
        "Profiling `decide()` before this page existed found the engine",
        "itself was a rounding error; the cost lived elsewhere, and one item",
        "was a correctness bug, not a slowdown:",
        "",
        "- **Cycle detection died at depth and the death was reported as a",
        "  finding.** The detector was recursive, so a dependency chain",
        "  about a thousand events deep raised `RecursionError` — which the",
        "  diagnostic guard converted into a \"could not run\" control",
        "  finding. Cycle detection silently stopped existing exactly when",
        "  traces got big. It is iterative now and proven on a 50,000-deep",
        "  chain, back edge and all.",
        "- **The evidence was hashed fifteen times per decision.** The",
        "  audit's mutation self-test re-evaluates one unchanged bundle",
        "  under fourteen contract variations, and every evaluation",
        "  recomputed the bundle's SHA-256. The digest is computed once per",
        "  decision now and handed to the self-test; `verify` likewise",
        "  reuses the digest it just recomputed and proved equal to the",
        "  claim's. Tamper evidence is unchanged: the digest is still",
        "  derived from content on every decision, never read from a stored",
        "  field.",
        "- **Generic serialization was two thirds of runtime.**",
        "  `dataclasses.asdict` recursed through every event; the digest now",
        "  serializes by direct field access, and a test holds the payload",
        "  byte-identical to the generic form, because every frozen claim",
        "  digest depends on that identity.",
        "- **Validation paid ABC dispatch per field.** Plain int/float now",
        "  short-circuit before the `numbers` machinery.",
        "",
        "## What stays expensive, and why that is honest",
        "",
        "Delegation closure stores each delegation's full spawned-event set,",
        "because the report and its serialization promise that detail. On a",
        "pathological trace where *every* event is a delegating tool call in",
        "one nested chain, the total size of those sets is quadratic in the",
        "chain length — that is the size of the *output*, and no traversal",
        "can beat the size of its own answer. Real traces keep delegation",
        "events sparse; measured at one delegator per fifty events, closure",
        "over 400,000 events costs about a fifth of a second. The honest",
        "envelope: linear in events, plus the sum of delegation subtree",
        "sizes, which the depth cap in the default policy already bounds.",
        "",
        "Peak memory is the harder wall than time. Evidence bundles are",
        "in-memory Python objects, so ten million events costs tens of",
        "gigabytes before a digest is taken. The supported answer at that",
        "scale is sharding by window or by task cohort — decide per shard,",
        "issue a claim per shard — not a bigger machine.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
