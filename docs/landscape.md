# Landscape and product decision

Research date: 2026-07-13.

## Decision

Open source the **executable economic assurance method**, not a wiki-only knowledge
base and not a thin “semantic circuit breaker for MCP.” The runtime safety idea is
useful as one transparent lesson, but it is not a defensible category claim.

| Direction | User value | Existing coverage | Decision |
|---|---|---|---|
| LLM/agent wiki | Discoverability and shared vocabulary | Many excellent lists, syllabi, and idea files | Publish later as supporting notes, not the product |
| MCP circuit-breaker wrapper | Fast demo and immediate developer pain | Direct OSS and commercial overlap; observability boundary is incomplete | Keep only honest diagnostics and deterministic caps |
| Agent-cost dashboard | Familiar enterprise UI | Observability and FinOps products already track spend and budgets | Do not build another dashboard in v0.1 |
| Economic assurance lab | Cross-functional decision from reproducible evidence | Components exist; the portable decision artifact is less owned | **Build this** |

## What the market already provides

- [Galileo custom metrics](https://docs.galileo.ai/concepts/metrics/custom-metrics/custom-metrics-ui-code)
  already let teams add code-based evaluation criteria over sessions, traces, and
  agent/tool/model spans. “You can add a scorer” is therefore not differentiation;
  the distinct artifact must be the cross-functional economic assurance manifest.
- [Circuit Breaker](https://circuitbreaker.dev/) already positions a local,
  zero-dependency TypeScript guardrail around AI agent runs, with cost caps,
  cycle/depth detection, and framework adapters. A new project cannot credibly lead
  with “the first zero-compute agent circuit breaker.”
- The [MCP tools specification](https://modelcontextprotocol.io/specification/2025-03-26/server/tools)
  already recommends validation, access controls, rate limiting, timeouts, result
  validation, logging, and human confirmation. MCP defines a tool-call protocol;
  a client wrapper alone does not automatically observe all nested or distributed
  work.
- [LangSmith cost tracking](https://docs.langchain.com/langsmith/cost-tracking)
  already attaches model, tool, and retrieval costs to traces.
- LangSmith also supports [trace export](https://docs.langchain.com/langsmith/export-traces)
  and [OpenTelemetry routing](https://docs.langchain.com/langsmith/trace-with-opentelemetry),
  while OpenTelemetry publishes shared
  [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).
  That makes offline evidence normalization a credible integration seam without
  replacing the observability platform.
- [Braintrust’s cost-efficiency guidance](https://www.braintrust.dev/blog/test-agent-cost-efficiency)
  already evaluates agent control logic with quality gates and cost per resolved
  request. Cost-versus-quality experiments are necessary, but not a unique product
  claim.
- The [FinOps Foundation’s unit-economics capability](https://www.finops.org/framework/capabilities/unit-economics/)
  explicitly connects technology cost to business outcomes and notes that outcome
  data is difficult to gather and correlate.
- [AWS Prescriptive Guidance on agentic AI economics](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-economics/assessing-costs.html)
  includes human baseline, failure, opportunity, technology, and risk costs. A
  token-only calculator would be incomplete.
- Products such as [Tarmac](https://www.gettarmac.ai/),
  [LensAI](https://getlens.ai/), and [Runrate](https://www.runrate.tech/) already
  market budget controls, outcome/ROI attribution, or cost per outcome.

## The narrower gap

The under-owned artifact is a vendor-neutral, inspectable package that can move
between engineering, finance, product, risk, and an architecture review:

```text
What was attempted?
  -> What full execution path occurred?
  -> Was the outcome acceptable?
  -> What downstream labor and loss followed?
  -> What would the alternative have cost and achieved?
  -> Which pre-agreed boundary passed or failed?
  -> What is the bounded decision and its expiry date?
```

Observability products can export the trace. Eval products can supply the outcome.
Finance systems can provide rates and losses. Runtime guardrails can enforce the
caps. The assurance case makes their combined claim reviewable and portable.

## Why a small executable system beats a wiki at launch

High-traction educational repositories tend to give users an immediate act:
run it, inspect it, change one assumption, and falsify the result. A wiki can grow
around that system, but a wiki launched first has no proof that its categories
survive contact with data.

For this project, the executable artifact provides:

1. a two-minute result with no cloud account;
2. transparent math and synthetic evidence;
3. a sharp, shareable failure case;
4. a contribution unit—bring one assurance case; and
5. a narrow adapter seam that lets existing platforms remain in place.

## Product boundary for v0.1

Build:

- CSV/JSON evidence contract;
- explicit source-adapter and typed-check composition;
- a canonical evidence digest and module manifest;
- deterministic cost reconstruction;
- cost per acceptable outcome;
- counterfactual net value;
- fail-safe incomplete/scale/assist/stop routing;
- diagnostic repetition/cycle checks with explicit caveats;
- a portable Markdown report;
- runnable lessons, tests, and one synthetic case.

Do not build yet:

- a hosted dashboard;
- live authenticated vendor clients;
- an MCP proxy;
- online authorization;
- a generalized policy language;
- a claim of semantic loop or deadlock proof; or
- a broad agent-economics encyclopedia.

Offline source mappers are a contribution lane; live SDK clients and runtime
instrumentation are not. Extensions beyond this boundary should be pulled by real
case-study contributions, not guessed in advance.
