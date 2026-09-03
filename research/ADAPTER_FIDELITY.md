# What each ingestion path loses

Byte-compared fixtures prove an adapter's output has not changed.
A frozen count inventory proves the contract's declared totals equal
the adapter's own decoded totals. Both are perfectly consistent with
an adapter that reads half its input and always has.

This measures the property those two miss: **conservation with a
named remainder**. Every unit in the source is either cited by a
decoded economic entity, or falls in a bucket the adapter names as
carrying no economics. Anything else is a unit that vanished, and a
bundle missing a model call is a valid bundle with a smaller cost -
no downstream check can see it.

Source counts are taken from the raw bytes here, never from what the
adapter reports about itself.

| ingestion path | unit | source | cited | accounted | orphaned |
|---|---|---:|---:|---:|---:|
| `source.claude-code-jsonl@1` | JSONL record | 9 | 9 | 0 | **0** |
| `source.claude-code-session-tree@1` | JSONL record across the session tree | 10 | 8 | 2 (repeated delegation bootstrap envelopes, excluded from cost so delegation is not counted twice) | **0** |
| `source.csv@1` | CSV row | 36 | 36 | 0 | **0** |
| `source.otel-genai@1` | OTLP span | 2 | 2 | 0 (structural spans, carrying no GenAI economics) | **0** |

**0 of 57 source units orphaned across every shipped ingestion path.**

What this does and does not establish. It establishes that on these
fixtures nothing is silently dropped, and it is a real property: the
guard fails the build the moment a whole class of decoded entity
stops citing its source.

Three limits, each pinned by a test so this page cannot quietly
overclaim. **Citation is redundant**: a model turn's record is often
also named by the task boundary or a tool pair, so dropping one call
of several leaves every record still cited and orphans nothing -
whole-class loss is caught, a single co-cited call is not. **It is
conservation, not fidelity**: a path could cite every record and
still misread a token count. **The fixtures are ours**, small and
written here, so an export whose shape they do not contain is
unmeasured by this page.

Decoded entities per path, for scale:

- `source.claude-code-jsonl@1`: 2 tasks, 4 model calls, 2 tool calls
- `source.claude-code-session-tree@1`: 1 tasks, 4 model calls, 2 tool calls
- `source.csv@1`: 36 events
- `source.otel-genai@1`: 1 tasks, 2 economic spans


## Does the spend survive conversion?

Counting records is not counting money. The session-tree path is the
one that transforms usage rather than copying it, so it is the one
worth reconciling: it drops the repeated delegation bootstrap
envelope, merges streamed fragments of a single message, and folds
cache reads into input. Raw source totals are therefore *not*
expected to equal bundle totals, and publishing the difference as
loss would be wrong. Subtracting exactly the documented transforms
is the honest check, because a decode that lost a real call would
leave a residual no transform explains.

| term | input tokens | output tokens |
|---|---:|---:|
| source records | 610 | 185 |
| less repeated bootstrap envelope | -100 | -20 |
| less merged stream fragments | -120 | -30 |
| plus cache reads folded into input | +50 | 0 |
| **expected** | **440** | **135** |
| bundle | 440 | 135 |
| **residual** | **0** | **0** |

**Residual 0 input and 0 output tokens: the accounting closes to the token.**

