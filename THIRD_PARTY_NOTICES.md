# Third-party notices

This project is licensed under Apache-2.0 (see [LICENSE](LICENSE)). It has **no
third-party runtime dependencies**: `pyproject.toml` declares
`dependencies = []` and the package uses only the Python standard library.

The material below is credited because the repository either derives fixture data
from it, implements against its specification, or calls it at runtime. Nothing
here is vendored into the source tree.

---

## Derived data

### mini-SWE-agent trajectories on SWE-bench Verified

- **Source:** `tarsur385/swebench-verified-trajectories` on Hugging Face
- **Revision:** `b55979d6b24850b72ae4d80f912526280cd6058a` (pinned)
- **License:** MIT
- **Used in:** [`examples/public-swebench/runs.json`](examples/public-swebench/runs.json)

**Extent of use.** `runs.json` records, per task and per model, only: the public
SWE-bench instance ID, the published resolution flag, the published API-call count,
the published client-side cost estimate, the upstream file path, and a SHA-256
digest of the upstream file. It contains **no prompts, no reasoning, no patches,
and no tool output**. The digests let a reviewer retrieve and verify the original
files rather than trusting this repository's copy.

That dataset in turn credits its own provenance:

- Trajectories obtained from [Docent](https://docent.transluce.org) (Transluce)
- Preprocessing from [`jackyk02/contrastive_learning`](https://github.com/jackyk02/contrastive_learning)

### Upstream of that dataset

| Project | License | Relationship |
|---|---|---|
| [SWE-bench](https://github.com/SWE-bench/SWE-bench) and SWE-bench Verified | MIT | Task instances and the hidden-test resolution outcome used as ground truth |
| [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) | MIT | The agent harness that produced the trajectories |

### MIT License text

Reproduced once here to satisfy the notice condition of the MIT-licensed material
credited above. Copyright is held by the respective authors of each project.

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Specifications implemented

| Specification | License | Relationship |
|---|---|---|
| [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) `1.43.0`, GenAI commit `799e014` | Apache-2.0 | `source.otel-genai@1` decodes a pinned allowlist of GenAI attributes. No OpenTelemetry code is included. |
| [Moonshot Flavored JSON Schema](https://github.com/MoonshotAI/walle/blob/main/docs/mfjs-spec.md) | see upstream | The judge's structured-output schema conforms to it. |

## Fixture shapes derived from observed exports

The OpenTelemetry fixtures were written to match the export *shape* of two
platforms. No code, and no captured customer data, is included. Values are
synthetic and content-free.

| Project | License | Relationship |
|---|---|---|
| [Langfuse](https://github.com/langfuse/langfuse) | MIT (core tracing, API, data model, exports) | `examples/otel-genai/langfuse-*.json` matches its OTLP export shape |
| [Arize OpenInference](https://github.com/Arize-ai/openinference) | Apache-2.0 | `examples/otel-genai/arize-openinference-*.json` matches its convention shape |

## Services called at runtime, not redistributed

| Service | Relationship |
|---|---|
| [Moonshot Kimi API](https://platform.kimi.ai/docs/api/chat) | Optional. `kimi-judge@1` and `kimi-analyst@1` call it when the user supplies their own `MOONSHOT_API_KEY`. Use is subject to Moonshot's own terms. No credentials, responses, or model weights are distributed with this repository. |
| Anthropic Claude Code | The `claude-code` and `claude-code-tree` adapters read locally exported transcripts supplied by the user. The checked-in fixtures are synthetic and content-redacted. |

## Trademarks

Product and company names used here, including SWE-bench, Claude, Claude Code,
Kimi, Moonshot, Langfuse, Arize, OpenInference, OpenTelemetry, and GitHub, are the
property of their respective owners. They are used descriptively to identify the
formats, specifications, and services this project interoperates with. **No
affiliation, sponsorship, or endorsement is claimed or implied.**

## Reporting an omission

If you believe attribution here is incomplete or incorrect, please open an issue.
Corrections to this file are treated as priority fixes.
