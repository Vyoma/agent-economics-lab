# Claude Code Session-Tree Adapter

`source.claude-code-session-tree@1` converts one parent Claude Code transcript and
its persisted subagent transcripts into the canonical evidence boundary.

It is a separate adapter. `source.claude-code-jsonl@1` remains the narrow
single-file contract and still refuses delegation that may hide nested model
spend.

## Input layout

Pass the parent transcript:

```text
<session>.jsonl
<session>/subagents/agent-<id>.jsonl
<session>/subagents/agent-<id>.meta.json
```

Anthropic documents that subagent transcripts persist as
`agent-{agentId}.jsonl` files under the parent session. The adapter treats that
layout as a pinned local source format, not a stable public interchange schema.

- [Claude Code subagent transcripts](https://code.claude.com/docs/en/sub-agents)
- [Claude session storage subpaths](https://code.claude.com/docs/en/agent-sdk/session-storage)
- [Claude Code local transcript storage](https://code.claude.com/docs/en/claude-directory)

Symlinks are refused. Every child JSONL must have one metadata peer with the same
agent ID. Extra or missing peers return `INCOMPLETE`.

## Conversion

Generate the content-safe contract template:

```bash
agent-economics convert \
  --from claude-code-tree \
  --in session.jsonl \
  --template conversion-contract.json
```

Complete the outcome, price, baseline, and policy fields, then convert:

```bash
agent-economics convert \
  --from claude-code-tree \
  --in session.jsonl \
  --contract conversion-contract.json \
  --out bundle.json

agent-economics evaluate --bundle bundle.json
```

The same normalized evidence kernel, gates, renderers, and decision exit codes are
used after conversion.

## Economic attribution

Root external prompts remain the economic task unit. A subagent prompt is not
counted as a second business attempt.

Mixed root prompt structures, including image blocks, are canonicalized only to
derive the opaque task input digest. Their values are not decoded or emitted. The
original parent bytes remain bound to the aggregate source manifest.

For every subagent:

1. `metadata.toolUseId` must identify exactly one `Agent` or `Task` call in the
   parent or an ancestor subagent.
2. The child transcript session and agent identity must match its parent tree.
3. Child model and tool events inherit the root task that owns the delegation.
4. The delegation event points to the first child event.
5. Child leaf events point to the parent's post-delegation successors.

Nested children are resolved recursively. Cycles and incorrect declared spawn
depth fail closed.

Recent forked transcripts repeat the parent delegation call as a child bootstrap
envelope. The adapter verifies the repeated tool identity, converts the envelope
into a local prompt boundary, and excludes the repeated parent model and tool call
from cost. Direct-prompt child transcripts are handled without that removal.

Streamed fragments can carry an early partial usage total and a later cumulative
total for the same message. The adapter requires identical input and cache
accounting, then conservatively selects the maximum observed output and server-tool
usage. Conflicting input or billing context still fails closed.

An explicit API-error placeholder is excluded only when every token and server
tool counter is zero. A child transcript with no billable event remains bound to
the source tree without receiving a fabricated event. Cyclic child graphs use
deterministic source and sink components for cross-file edges; the cycle itself
remains visible to the diagnostic check.

## Frozen source inventory

The conversion contract binds:

- the parent transcript digest;
- every child transcript digest;
- every child metadata digest;
- opaque agent identities;
- source-file, subagent, expanded-delegation, and depth counts;
- all root and child model usage;
- all root and child tool calls and results; and
- all within-file and cross-file dependency edges.

Deleting or changing any paired file invalidates the contract. A delegation tool
without one matching child transcript remains listed as unexpanded, and conversion
is refused.

## Privacy boundary

The tree adapter applies the single-file content firewall to every transcript. The
contract and normalized bundle exclude:

- parent and child prompts;
- responses and thinking;
- tool-result content;
- tool-argument keys and values;
- metadata descriptions;
- session IDs, agent IDs, source UUIDs, message IDs, and tool-use IDs; and
- local paths.

Only hashes, counts, timestamps, model and tool names, usage, billing context,
status, and content-free argument type shapes cross the adapter boundary.

Raw Claude Code transcripts are plaintext and may contain secrets. Generated
artifacts must still be reviewed before publication.

## Conformance proof

```bash
make claude-code-tree
```

The checked-in synthetic tree contains one root task and one child. It proves:

```text
3 bound source files
1 expanded delegation
4 unique model calls
2 tool calls
6 dependency edges
SCALE
```

The fixture includes fake secret markers in the parent, child, tool arguments, and
metadata. Tests prove none appear in the template or normalized bundle. Separate
tests cover legacy direct-prompt children, nested attribution, source drift,
missing pairs, unknown delegation links, CLI conversion, and the GitHub Action.

This fixture proves schema handling and fail-closed accounting. It does not prove
that its illustrative outcome, prices, baseline, or policy generalize to a real
enterprise workload.

## Observed compatibility boundary

Privacy-safe local inspection has exercised transcript shapes from Claude Code
versions `2.1.156`, `2.1.162`, and `2.1.212`. Complete tree inspection passes the
observed `2.1.156` and `2.1.212` sessions. The observed `2.1.162` tree remains
intentionally refused because it contains root external-prompt boundaries with no
execution events. The adapter does not silently turn those ambiguous boundaries
into zero-cost attempts.
