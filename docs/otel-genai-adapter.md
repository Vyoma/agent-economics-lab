# OpenTelemetry GenAI adapter

`source.otel-genai@1` converts a pinned offline OTLP JSON export into the canonical
economic evidence bundle. One adapter is exercised against content-safe fixtures
derived from Langfuse and Arize OpenInference.

The mapper is pinned to:

- OpenTelemetry Semantic Conventions `1.43.0`;
- GenAI semantic-conventions commit
  `799e014b68f0e786dc44d9117c30758c5f864510`; and
- OTLP JSON `resourceSpans -> scopeSpans -> spans` envelopes.

The separate OpenTelemetry GenAI repository had no tagged release when this
contract was frozen. The commit pin is therefore part of the conversion receipt,
not just documentation.

## Two-phase conversion

Inspect a local export and create a contract template:

```bash
agent-economics convert \
  --from otel-genai \
  --in traces.otlp.json \
  --template conversion-contract.json
```

Complete the task mapping approval, input digests, outcome labels, prices,
baseline, and policy. Then convert and evaluate:

```bash
agent-economics convert \
  --from otel-genai \
  --in traces.otlp.json \
  --contract conversion-contract.json \
  --out bundle.json

agent-economics evaluate --bundle bundle.json --ci
```

The converter refuses to write a bundle when the contract or export is
incomplete.

## Mapping contract

The v1 task unit is one explicitly approved OTLP trace. The adapter does not
reinterpret `traceId` as an OpenTelemetry conversation ID. It creates an opaque
task ID, hashes the source trace ID for contract matching, and requires a human
owner in `task_mapping.approved_by` to assert that each trace is one evaluation
task.

Supported model operations are `chat`, `embeddings`, `generate_content`,
`image_generation`, and `text_completion`. `execute_tool` is supported when
`gen_ai.tool.name` is present. Other `gen_ai.operation.name` values fail closed
until their economic semantics are specified.

The billing model is `gen_ai.response.model` when present, otherwise
`gen_ai.request.model`. Every observed model and tool name must appear exactly in
the supplied price card. Model events require non-negative input and output token
counts with positive total usage.

`gen_ai.usage.input_tokens` is priced once. Cache-read and cache-creation counts
are retained as audit metadata but are not added to input tokens. The pinned
semantic convention defines them as input-token subsets. Differentiated cache
pricing is outside the v1 OTLP contract.

## Parentage

`parentSpanId` is resolved within the frozen export. Each economic span links to
its nearest economic ancestor through any structural spans. The resulting event
edges are stored in the typed `dependency_edges` field and covered by the evidence
digest.

An unresolved non-root parent, a parent cycle, duplicate span identity, or a
cross-task edge is rejected. The default directed-cycle check emits only a
diagnostic warning. A cycle is not treated as proof of deadlock.

## Content firewall

The adapter decodes only the following economic keys:

```text
error.type
gen_ai.operation.name
gen_ai.provider.name
gen_ai.request.model
gen_ai.response.model
gen_ai.tool.name
gen_ai.usage.input_tokens
gen_ai.usage.output_tokens
gen_ai.usage.cache_read.input_tokens
gen_ai.usage.cache_creation.input_tokens
```

All other attribute values are left unread. Prompt text, responses, messages,
system instructions, tool definitions, tool arguments, and tool results never
enter the canonical bundle.

The raw-file digest still covers the complete input file. Review the input,
contract, and generated bundle before publishing any of them.

## Proof of genericity

The checked fixtures record repository, commit, path, upstream digest, and local
content-removal transformation:

- Langfuse OTLP ingestion fixture at commit
  `429ec4fff6512fff49aef50fccb92846f674a98a`;
- Arize OpenInference GenAI fixture at commit
  `a1392c50d2d5b20fb805c195fb6006c80d5a6106`.

They prove conformance across two independently maintained platform shapes. They
do not prove compatibility with every exporter version or production economic
validity.

```bash
make otel-genai
```
