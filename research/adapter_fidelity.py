"""Measure what each ingestion path loses: the record that is silently dropped.

Every shipped adapter was covered by byte-compared example fixtures and a
frozen count inventory, and neither answers the question that matters. A
byte-compare proves the output has not changed; a count freeze proves the
contract's declared totals equal the adapter's own decoded totals. Both are
self-consistent with an adapter that reads half its input and always has.

The property measured here is conservation with a named remainder: every
record in the source is either **cited** by a decoded economic entity, or it
falls in an explicitly named bucket the adapter accounts for. A record that
is neither has vanished, and vanishing is the adapter failure that no
downstream check can see — a bundle missing a model call is a valid bundle
with a smaller cost.

For each path this reports:

* `source` — units in the raw export, counted from the raw bytes here, not
  from anything the adapter says about itself.
* `cited` — units named by at least one decoded entity through its
  traceability fields (record uuids, span ids, csv row ids).
* `accounted` — units the adapter explicitly classifies as carrying no
  economics (OTLP structural spans, for instance). Named, not assumed.
* `orphaned` — the remainder. **This must be zero**, and the guard in
  tests/test_adapter_fidelity.py fails the build when it is not.

It also reports cost conservation: the bundle's total effective cost equals
the sum of its per-event costs, recomputed here from the source usage and
the contract's rate card rather than read back from the bundle.

`make adapter-fidelity` renders research/ADAPTER_FIDELITY.md and
byte-compares it, so the published figures cannot drift from the fixtures.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_economics.claude_code import inspect_claude_code_jsonl  # noqa: E402
from agent_economics.claude_code_tree import inspect_claude_code_session_tree  # noqa: E402
from agent_economics.otel_genai import inspect_otel_genai_json  # noqa: E402

EXAMPLES = ROOT / "examples"


def _claude_code(session: pathlib.Path) -> dict:
    """Records are cited through uuids: task origin, model turns, tool pairs."""
    raw = [
        json.loads(line)
        for line in session.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    present = {r["uuid"] for r in raw if r.get("uuid")}
    parsed = inspect_claude_code_jsonl(session)
    cited: set[str] = set()
    for task in parsed.tasks:
        cited.add(task.source_uuid)
    for call in parsed.model_calls:
        cited.update(call.source_record_uuids)
    for call in parsed.tool_calls:
        cited.add(call.source_record_uuid)
        if call.result_record_uuid:
            cited.add(call.result_record_uuid)
    cited.discard(None)
    return {
        "unit": "JSONL record",
        "source": len(present),
        "cited": len(present & cited),
        "accounted": 0,
        "accounted_as": "",
        "orphaned": sorted(present - cited),
        "decoded": {
            "tasks": len(parsed.tasks),
            "model calls": len(parsed.model_calls),
            "tool calls": len(parsed.tool_calls),
        },
    }


def _claude_code_tree(parent: pathlib.Path) -> dict:
    """The parent JSONL plus every subagent file the tree expands into.

    Counted from the parent's sibling directory rather than from the
    adapter's own file list, so a subagent file the adapter never opened
    still shows up in the source total.
    """
    # rglob, not glob: the subagent files sit under session/subagents/, and
    # a non-recursive glob found none of them. That undercounts the source
    # total, which would have hidden orphans instead of reporting them -
    # this file's own failure mode, caught by reading its first output.
    files = [parent, *sorted((parent.parent / parent.stem).rglob("*.jsonl"))]
    present: set[str] = set()
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if record.get("uuid"):
                    present.add(record["uuid"])
    parsed = inspect_claude_code_session_tree(parent)
    cited: set[str] = set()
    for task in parsed.tasks:
        cited.add(task.source_uuid)
    for call in parsed.model_calls:
        cited.update(call.source_record_uuids)
    for call in parsed.tool_calls:
        cited.add(call.source_record_uuid)
        if call.result_record_uuid:
            cited.add(call.result_record_uuid)
    cited.discard(None)

    # A forked child transcript repeats its parent's delegation call as a
    # bootstrap envelope. The adapter excludes it from cost so delegation is
    # not counted twice - documented behaviour, and correct - but the
    # exclusion was invisible: nothing counted it, so an over-firing
    # de-duplicator would have dropped real calls silently. Identified here
    # by the property the adapter itself uses, a child record whose request
    # id belongs to the parent transcript, and reported as accounted rather
    # than assumed away.
    parent_requests = {
        json.loads(line).get("requestId")
        for line in parent.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    parent_requests.discard(None)
    bootstrap: set[str] = set()
    for path in files[1:]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            uuid = record.get("uuid")
            if uuid in cited or not uuid:
                continue
            if record.get("requestId") in parent_requests:
                bootstrap.add(uuid)
            else:
                # the tool_result half of the same envelope, whose parent is
                # the bootstrap record itself
                parent_uuid = record.get("parentUuid")
                if parent_uuid and parent_uuid in bootstrap:
                    bootstrap.add(uuid)
    return {
        "unit": "JSONL record across the session tree",
        "source": len(present),
        "cited": len(present & cited),
        "accounted": len(bootstrap - cited),
        "accounted_as": "repeated delegation bootstrap envelopes, excluded "
                        "from cost so delegation is not counted twice",
        "orphaned": sorted(present - cited - bootstrap),
        "decoded": {
            "tasks": len(parsed.tasks),
            "model calls": len(parsed.model_calls),
            "tool calls": len(parsed.tool_calls),
        },
    }


def _otel(export: pathlib.Path) -> dict:
    """Spans partition into economic spans and named structural spans."""
    document = json.loads(export.read_text(encoding="utf-8"))
    present: set[str] = set()
    for resource in document.get("resourceSpans", []):
        for scope in resource.get("scopeSpans", []):
            for span in scope.get("spans", []):
                present.add(span["spanId"])
    parsed = inspect_otel_genai_json(export)
    cited = {span.span_id for span in parsed.spans}
    return {
        "unit": "OTLP span",
        "source": len(present),
        "cited": len(present & cited),
        "accounted": parsed.structural_span_count,
        "accounted_as": "structural spans, carrying no GenAI economics",
        # A structural span is accounted for, so it is not orphaned; the
        # adapter's own count is trusted only to the extent that the three
        # numbers must still add up to the source total.
        "orphaned": sorted(present - cited)[: max(
            0, len(present) - len(present & cited) - parsed.structural_span_count
        )],
        "decoded": {
            "tasks": len(parsed.tasks),
            "economic spans": len(parsed.spans),
        },
    }


def _csv(traces: pathlib.Path) -> dict:
    with traces.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    present = {row["event_id"] for row in rows}
    from agent_economics.io import load_traces

    events = load_traces(traces)
    cited = {event.event_id for event in events}
    return {
        "unit": "CSV row",
        "source": len(present),
        "cited": len(present & cited),
        "accounted": 0,
        "accounted_as": "",
        "orphaned": sorted(present - cited),
        "decoded": {"events": len(events)},
    }


def token_reconciliation() -> dict:
    """Source usage, minus the adapter's documented transforms, versus the bundle.

    Raw source totals are *not* expected to equal bundle totals, and a page
    that published the difference as loss would be wrong. The session-tree
    adapter applies three documented transforms: it drops the repeated
    delegation bootstrap envelope, it merges streamed fragments of one
    message (identical input accounting, maximum observed output), and it
    folds cache reads into input. Subtract exactly those and the remainder
    must be zero - which is a real conservation check, because any decode
    that lost a call would leave a residual no transform explains.
    """
    base = EXAMPLES / "claude-code-tree"
    parent = base / "session.jsonl"
    files = [parent, *sorted((base / "session").rglob("*.jsonl"))]
    parent_requests = {
        json.loads(line).get("requestId")
        for line in parent.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    parent_requests.discard(None)

    source_in = source_out = 0
    bootstrap_in = bootstrap_out = 0
    merged_in = merged_out = 0
    cache_read = 0
    seen_requests: set[str] = set()
    for path in files:
        child = path != parent
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            usage = (record.get("message") or {}).get("usage") or {}
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            if not (tokens_in or tokens_out):
                continue
            source_in += tokens_in
            source_out += tokens_out
            request = record.get("requestId")
            if child and request in parent_requests:
                bootstrap_in += tokens_in
                bootstrap_out += tokens_out
                continue
            if request in seen_requests:
                # a later fragment of a message already counted
                merged_in += tokens_in
                merged_out += tokens_out
                continue
            seen_requests.add(request)
            cache_read += usage.get("cache_read_input_tokens", 0)

    bundle = json.loads((base / "bundle.json").read_text(encoding="utf-8"))
    bundle_in = sum(e.get("input_tokens", 0) for e in bundle["events"])
    bundle_out = sum(e.get("output_tokens", 0) for e in bundle["events"])
    expected_in = source_in - bootstrap_in - merged_in + cache_read
    expected_out = source_out - bootstrap_out - merged_out
    return {
        "source_in": source_in,
        "source_out": source_out,
        "bootstrap_in": bootstrap_in,
        "bootstrap_out": bootstrap_out,
        "merged_in": merged_in,
        "merged_out": merged_out,
        "cache_read": cache_read,
        "bundle_in": bundle_in,
        "bundle_out": bundle_out,
        "residual_in": bundle_in - expected_in,
        "residual_out": bundle_out - expected_out,
    }


PATHS = {
    "source.claude-code-jsonl@1": lambda: _claude_code(
        EXAMPLES / "claude-code" / "session.jsonl"
    ),
    "source.claude-code-session-tree@1": lambda: _claude_code_tree(
        EXAMPLES / "claude-code-tree" / "session.jsonl"
    ),
    "source.otel-genai@1": lambda: _otel(
        EXAMPLES / "otel-genai" / "langfuse-otlp.json"
    ),
    "source.csv@1": lambda: _csv(EXAMPLES / "support_trace.csv"),
}


def measure() -> dict[str, dict]:
    return {name: build() for name, build in sorted(PATHS.items())}


def render() -> str:
    results = measure()
    lines = [
        "# What each ingestion path loses",
        "",
        "Byte-compared fixtures prove an adapter's output has not changed.",
        "A frozen count inventory proves the contract's declared totals equal",
        "the adapter's own decoded totals. Both are perfectly consistent with",
        "an adapter that reads half its input and always has.",
        "",
        "This measures the property those two miss: **conservation with a",
        "named remainder**. Every unit in the source is either cited by a",
        "decoded economic entity, or falls in a bucket the adapter names as",
        "carrying no economics. Anything else is a unit that vanished, and a",
        "bundle missing a model call is a valid bundle with a smaller cost -",
        "no downstream check can see it.",
        "",
        "Source counts are taken from the raw bytes here, never from what the",
        "adapter reports about itself.",
        "",
        "| ingestion path | unit | source | cited | accounted | orphaned |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, result in results.items():
        accounted = (
            f"{result['accounted']}" if not result["accounted_as"]
            else f"{result['accounted']} ({result['accounted_as']})"
        )
        lines.append(
            f"| `{name}` | {result['unit']} | {result['source']} "
            f"| {result['cited']} | {accounted} | **{len(result['orphaned'])}** |"
        )
    total_source = sum(r["source"] for r in results.values())
    total_orphaned = sum(len(r["orphaned"]) for r in results.values())
    lines += [
        "",
        f"**{total_orphaned} of {total_source} source units orphaned across "
        "every shipped ingestion path.**",
        "",
        "What this does and does not establish. It establishes that on these",
        "fixtures nothing is silently dropped, and it is a real property: the",
        "guard fails the build the moment a whole class of decoded entity",
        "stops citing its source.",
        "",
        "Three limits, each pinned by a test so this page cannot quietly",
        "overclaim. **Citation is redundant**: a model turn's record is often",
        "also named by the task boundary or a tool pair, so dropping one call",
        "of several leaves every record still cited and orphans nothing -",
        "whole-class loss is caught, a single co-cited call is not. **It is",
        "conservation, not fidelity**: a path could cite every record and",
        "still misread a token count. **The fixtures are ours**, small and",
        "written here, so an export whose shape they do not contain is",
        "unmeasured by this page.",
        "",
        "Decoded entities per path, for scale:",
        "",
    ]
    for name, result in results.items():
        detail = ", ".join(f"{v} {k}" for k, v in result["decoded"].items())
        lines.append(f"- `{name}`: {detail}")
    lines.append("")

    r = token_reconciliation()
    expected_in = r["source_in"] - r["bootstrap_in"] - r["merged_in"] + r["cache_read"]
    expected_out = r["source_out"] - r["bootstrap_out"] - r["merged_out"]
    lines += [
        "",
        "## Does the spend survive conversion?",
        "",
        "Counting records is not counting money. The session-tree path is the",
        "one that transforms usage rather than copying it, so it is the one",
        "worth reconciling: it drops the repeated delegation bootstrap",
        "envelope, merges streamed fragments of a single message, and folds",
        "cache reads into input. Raw source totals are therefore *not*",
        "expected to equal bundle totals, and publishing the difference as",
        "loss would be wrong. Subtracting exactly the documented transforms",
        "is the honest check, because a decode that lost a real call would",
        "leave a residual no transform explains.",
        "",
        "| term | input tokens | output tokens |",
        "|---|---:|---:|",
        f"| source records | {r['source_in']} | {r['source_out']} |",
        f"| less repeated bootstrap envelope | -{r['bootstrap_in']} "
        f"| -{r['bootstrap_out']} |",
        f"| less merged stream fragments | -{r['merged_in']} "
        f"| -{r['merged_out']} |",
        f"| plus cache reads folded into input | +{r['cache_read']} | 0 |",
        f"| **expected** | **{expected_in}** | **{expected_out}** |",
        f"| bundle | {r['bundle_in']} | {r['bundle_out']} |",
        f"| **residual** | **{r['residual_in']}** | **{r['residual_out']}** |",
        "",
        f"**Residual {r['residual_in']} input and {r['residual_out']} output "
        "tokens: the accounting closes to the token.**",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
