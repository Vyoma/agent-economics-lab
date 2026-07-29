# Adapter and Extension Layer PRD

Status: P0 through P5 shipped on `main`. This document preserves the original
scoping rationale. See the [roadmap](roadmap.md) for current shipped and planned
work.

## Fixed kernel

This work does not change:

- the trace/outcome join;
- full-cost reconstruction;
- reducer order;
- required assurance coverage;
- the evidence digest;
- the decision-contract digest; or
- the zero-runtime-dependency policy.

No plugin registry, entry-point discovery, live vendor authentication, policy DSL,
hosted dashboard, or MCP proxy is introduced.

## Problem

The repository previously accepted CSV and its own normalized JSON shape. It had no
tested path from a real vendor or agent-runtime export into the canonical evidence
boundary.

Claude Code JSONL is the first source target. It is cost- and trace-bearing, but it
does not contain the economic semantics needed for a scale decision.

## Product decision

The CLI uses a separate conversion step:

```text
offline JSONL
  -> privacy-preserving contract template
  -> completed conversion contract
  -> normalized JSON + conversion receipt
  -> unchanged evaluate command
```

The normalized JSON boundary remains the only input to downstream assurance.

## P0 goals

| Goal | Status | Evidence |
|---|---|---|
| G1: real source adapter clears the conformance bar | Complete | `tests/test_claude_code_adapter.py` |
| G2: non-synthetic case published | Complete at public benchmark scope | 20 paired SWE-bench Verified tasks with public outcomes, spend, calls, and source digests |
| G3: decided bring-your-own-data CLI path | Complete | `agent-economics convert` |
| G4: kernel and both digests unchanged | Complete | Existing reproduction suite plus adapter tests |

G2 is satisfied by the public SWE-bench case, not by relabeling the synthetic
Claude Code fixture. The case uses published hidden-test outcomes, run-cost
estimates, API-call counts, and a same-task Haiku reference. It intentionally
assigns zero business value and therefore makes no enterprise ROI claim.

## Contract-first design

The source file is allowed to supply only facts it actually observes:

- external prompt boundaries;
- parent graph;
- unique model message IDs;
- token and cache usage;
- model identity and billing context;
- client tool calls and results;
- server-tool request counts; and
- timestamps and source version.

The user-owned conversion contract supplies:

- outcome rubric and label source;
- one explicit outcome row per discovered task;
- value, review, remediation, and incident cost;
- model pricing tiers and all cache bucket rates;
- explicit client and server tool cost;
- named counterfactual baseline; and
- economic policy.

Missing values remain missing. The adapter never infers an acceptable outcome from
the absence of an error.

## Novel engineering contribution

The differentiator is not parsing another JSON shape. It is a semantic firebreak
between observed execution and adjudicated economics:

1. streamed assistant fragments are deduplicated by source message ID;
2. prompts, responses, thinking, result content, argument keys, and argument values
   are removed;
3. a frozen source inventory detects deleted tasks, calls, and results;
4. cache writes, cache reads, context tiers, client tools, and server tools remain
   separately priced;
5. billing-context drift invalidates the contract;
6. unexpanded delegation is refused because nested model spend may be absent;
7. every economic default must be explicit; and
8. the emitted receipt binds raw source, inventory, conversion contract, and
   canonical evidence.

The receipt is transport provenance. It does not replace or modify the kernel's
evidence and decision-contract digests.

## Acceptance criteria

The adapter must:

1. produce the same economic digest and decision as equivalent CSV-loaded evidence;
2. remain invariant to JSONL row order;
3. count one model call per unique assistant message ID, not per streamed row;
4. reject duplicate source IDs and outcome task IDs;
5. reject non-finite or negative economics;
6. require exactly one same-task result per client tool call;
7. require exact task/outcome equality;
8. require exact model, cache, client-tool, and server-tool price coverage;
9. reject stale raw and inventory digests;
10. reject unsupported sidechains and unexpanded delegation;
11. emit no raw content values;
12. detect normalized evidence changed after conversion; and
13. reproduce checked-in template, bundle, and report byte for byte.

## Source compatibility

P0 targets the observed local interactive Claude Code session JSONL shape. It does
not claim that this internal transcript is a stable public vendor API.

The inspectors have been exercised locally against uncommitted sessions from
observed versions `2.1.156`, `2.1.162`, `2.1.165`, `2.1.198`, and `2.1.212`.
Pinned fixtures and a source adapter version change are required for incompatible
upstream schema changes.

Complete session-tree inspection passes the observed `2.1.156` and `2.1.212`
trees. The observed `2.1.162` tree remains refused because it contains root prompt
boundaries with no execution events. That refusal is preserved instead of
assuming those ambiguous prompts were zero-cost attempts.

## P5 outcome: complete delegated-session accounting

`source.claude-code-session-tree@1` expands the parent transcript and paired
`agent-<id>.jsonl` child transcripts without changing
`source.claude-code-jsonl@1`.

The adapter:

- keeps root external prompts as the economic task unit;
- maps every child call to the task that owns its spawning delegation;
- supports nested delegation with verified spawn depth;
- verifies but does not double count the child bootstrap envelope;
- binds every parent, child, and metadata file into the source digest;
- adds cross-file dependency edges from delegation through child execution; and
- refuses missing pairs, unknown links, cycles, identity collisions, or any
  remaining unexpanded delegation.

## Deferred work

- permissioned enterprise case with manually labeled business outcomes;
- supported Claude Code `stream-json` adapter if its schema differs materially;
- broader OpenTelemetry operation and cache-pricing semantics beyond the pinned v1
  contract;
- stable GitHub Action release tags after repository dogfood;
- subgroup and segment assurance; and
- registry discussion only after two independent adapters expose real wiring
  friction.
