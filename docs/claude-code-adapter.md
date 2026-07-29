# Claude Code JSONL Adapter

`source.claude-code-jsonl@1` converts one pinned offline Claude Code session into
the canonical normalized JSON evidence boundary.

The adapter is contract-first. It parses only observable execution facts from the
session. It refuses to infer outcome quality, current prices, business value, a
counterfactual, or deployment policy.

## Why this is not a one-step parser

A Claude Code transcript can tell us that a model call or tool call occurred. It
cannot tell us whether the business task was acceptable or whether the workflow
should scale.

Four source-owned claims must be supplied separately:

| Claim | Required contract evidence |
|---|---|
| Task outcome | Explicit boolean label plus named rubric and label source |
| Full cost | Explicit model price tiers, cache rates, client tool cost, and server tool cost |
| Business value | Value, review time, remediation cost, and incident loss per task |
| Counterfactual and policy | Named baseline plus thresholds fixed before evaluation |

The converter never replaces an absent value with a convenient proxy.

## Two-phase workflow

First, inspect the local session and write a privacy-preserving contract template:

```bash
agent-economics convert \
  --from claude-code \
  --in session.jsonl \
  --template conversion-contract.json
```

The template contains opaque task IDs, input digests, timestamps, observed model
and tool names, source counts, and two source digests. It contains no prompt,
response, thinking, tool-result, tool-argument key, or tool-argument value.

Complete every null field in the template. Then convert:

```bash
agent-economics convert \
  --from claude-code \
  --in session.jsonl \
  --contract conversion-contract.json \
  --out bundle.json

agent-economics evaluate --bundle bundle.json
```

An incomplete or stale contract returns exit code 2 and does not write the output.

## Exact task and call semantics

The v1 mapping is deliberately narrow:

- one non-sidechain external user prompt is one economic task;
- the task ID is an opaque SHA-256 identity derived from session and prompt UUID;
- the task input digest hashes the prompt content without exporting that content;
- multiple JSONL fragments with the same assistant `message.id` are one model call;
- one `tool_use` block plus exactly one matching result is one client tool call;
- a failed tool result becomes a canonical tool event with `status="error"`; and
- metadata, attachments, titles, raw responses, and thinking blocks are not
  economic calls.

The parent-UUID graph assigns every model and tool call to its nearest external
prompt. It also emits typed dependency edges between model calls, tool calls, and
subsequent model calls. Record order does not define either join.

This distinction matters because one streamed model response can appear as several
assistant rows. Counting rows would overstate both calls and cost.

## Cost contract

No provider prices are hardcoded.

Each observed model must have one or more explicit pricing tiers. A tier records:

- maximum total input tokens, or `null` for the final unbounded tier;
- base input price per million tokens;
- output price per million tokens;
- cache-read price per million tokens; and
- a price for every cache-write bucket observed in the source.

The contract also freezes the observed service tier, speed mode, and inference
geography for each model. Those fields remain part of the content-redacted
inventory even when the selected price card assigns them the same rates.

Total input for tier selection is:

```text
base input + cache reads + cache writes
```

The adapter computes an explicit direct model-call cost from the selected tier.
Client tool costs are declared per call, including explicit `0.0` when they are
known to be free or already allocated. Non-zero server-tool usage requires a
per-request price.

The canonical event retains the non-content usage breakdown and price-card ID so a
reviewer can reconstruct the cost.

## Source-completeness contract

The generated contract freezes:

- raw file SHA-256;
- a content-redacted inventory SHA-256;
- relevant record count;
- task count;
- unique model-call count;
- tool-call count;
- dependency-edge count;
- observed Claude Code versions; and
- known unexpanded delegation tools.

The inventory digest covers opaque task identities, input digests, unique model
calls, token usage, tool calls, statuses, timestamps, and redacted argument shapes.
It also covers the resolved dependency edges.
Deleting a failed tool result, model call, task, or source row invalidates the
contract.

The converter rejects:

- multiple session IDs;
- sidechain records;
- mixed or unsupported external-prompt content blocks;
- unresolved parent graphs;
- duplicate source UUIDs or tool-use IDs;
- missing or duplicate tool results;
- tool results assigned across task boundaries;
- outcome rows that do not exactly match discovered tasks;
- stale raw or inventory digests;
- missing model, cache, client-tool, or server-tool prices;
- non-finite or negative economics; and
- known `Agent` or `Task` delegation whose nested model calls are not in the file.

Unexpanded delegation is rejected because pricing the parent tool call as `0.0`
would silently omit the nested agent's model spend.

## Privacy boundary

The normalized bundle excludes:

- prompt text;
- assistant text;
- thinking content;
- tool-result content;
- tool-argument keys and values, including file paths, commands, and search terms;
  and
- raw Claude Code record identifiers.

Tool arguments keep only container counts and primitive type shapes. Source IDs
are converted into opaque hashes.

The adapter does not make a sensitive transcript safe for publication by itself.
Review every generated bundle and contract before sharing.

## Conversion receipt

The output bundle embeds a receipt with:

```text
source adapter ID and version
raw source digest
content-redacted inventory digest
conversion-contract digest
canonical evidence digest
price-card ID
rubric version and label source
task/model/tool counts
dependency-edge count
observed Claude Code versions
```

When the normalized bundle is loaded, its evidence digest is recomputed and must
match the receipt.

The receipt is not a signature, attestation, or third kernel digest. The existing
evidence digest and decision-contract digest remain unchanged.

## Reproduce the checked-in case

```bash
make claude-code
```

The checked-in fixture is synthetic and contains deliberately fake secret values
to verify that conversion removes content. It produces:

```text
2 tasks
4 unique model calls
2 client tool calls
4 dependency edges
1 acceptable outcome
ASSIST
```

The example is a schema and conformance fixture, not a real-world economic result.

## Real-data status

The inspector has been exercised locally against uncommitted Claude Code sessions
from observed versions `2.1.165` and `2.1.198`. No prompt, response, contract price,
or manually assigned outcome from those sessions is checked into this repository.

A public non-synthetic benchmark case now exists under
[`examples/public-swebench`](../examples/public-swebench/). A permissioned
enterprise case still requires manual labels under a frozen business rubric, an
approved price card, and a defensible human or production baseline.

Claude's supported CLI documents structured `json` and `stream-json` output, while
the local interactive transcript used here is treated as a pinned compatibility
fixture:

- [Claude Code CLI output formats](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
- [Anthropic pricing and prompt-cache accounting](https://docs.anthropic.com/en/docs/about-claude/pricing)
