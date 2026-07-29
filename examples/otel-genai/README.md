# OpenTelemetry GenAI conformance fixtures

This directory contains two content-safe inputs for
`source.otel-genai@1`. They test one converter against independent Langfuse and
Arize OpenInference source shapes.

Each input records:

- upstream repository, exact commit, and file path;
- SHA-256 digest of the upstream file;
- the local content-removal or envelope transformation; and
- only the GenAI fields needed for the economic contract.

The Langfuse fixture also contains one content-free `execute_tool` child. It
exercises model-to-tool parentage and exact tool-price coverage. The Arize fixture
retains the upstream request and response model distinction while excluding all
messages and tool arguments.

The completed conversion contracts use illustrative fixture outcomes, prices,
baseline, and policy. They are conformance evidence, not production economics.

```bash
make otel-genai
```
