# Landscape and product decision

Research date: 2026-07-30.

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
- Claude Code transcript parsing is already a populated open-source category.
  [claude-session-analyzer](https://pypi.org/project/claude-session-analyzer/)
  reports token, cost, time, and per-skill behavior;
  [AgentSight](https://www.agentsight.org/) reports usage, cache efficiency, and
  cost; and
  [claude-code-usage-analyzer](https://github.com/aarora79/claude-code-usage-analyzer)
  breaks cost down by token type. Parsing JSONL or showing cache spend is not the
  novel claim.
- Multi-agent trace trees and child-cost rollups are also existing product
  capabilities. [Braintrust trace views](https://www.braintrust.dev/docs/observe/examine-traces)
  propagate child-span cost to parent spans, while
  [LangSmith cost tracking](https://docs.langchain.com/langsmith/cost-tracking)
  shows cost on parent and child runs and aggregates child runs when thread
  metadata is present. Anthropic documents that
  [Claude Code subagent transcripts](https://code.claude.com/docs/en/sub-agents)
  persist separately from the main conversation. This repository therefore does
  not claim that hierarchical tracing, subagent discovery, or cost rollup is
  novel. The shipped distinction is an offline, file-bound join that attributes
  each expanded child to one root business attempt, guards against duplicate
  execution evidence, and then applies the same outcome, labor, loss,
  counterfactual, and fixed-coverage decision contract as every other adapter.
- Anthropic's own [cost guidance](https://code.claude.com/docs/en/costs) exposes
  session usage and estimated spend. It also notes that local dollar figures may
  differ from authoritative billing, which is another reason to keep the supplied
  price card explicit and versioned.
- OpenTelemetry export is already a populated integration seam, not a greenfield
  category. [Langfuse](https://langfuse.com/integrations/native/opentelemetry)
  receives OTLP traces, and its OpenTelemetry-native SDK emits LLM-relevant spans.
  [Arize OpenInference](https://github.com/Arize-ai/openinference) publishes
  complementary semantic conventions and OpenTelemetry instrumentation for LLM
  and agent traces.
  [Traceloop OpenLLMetry](https://github.com/traceloop/openllmetry) provides LLM
  instrumentation on top of OpenTelemetry and emits standard OpenTelemetry data.
  Those cited tracing contracts do not define this repository's full economic
  decision contract: adjudicated acceptability, labor and incident cost, a named
  counterfactual, and fixed required coverage. Capturing the span is therefore not
  the differentiation. The shipped contribution is a pinned offline mapper that
  refuses incomplete economic evidence and is exercised against two independently
  maintained, content-safe platform fixture shapes.

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

For the Claude Code adapter, the differentiator is the semantic boundary after
parsing:

```text
observed transcript facts
  + frozen task/outcome contract
  + explicit cache/client/server price contract
  + named baseline and policy
  -> auditable INCOMPLETE / SCALE / ASSIST / STOP decision
```

Existing analyzers answer, "What did this session consume?" This project asks a
different question: "What evidence must be present before this workload earns the
right to scale?" The source inventory and refusal behavior make that distinction
executable.

## Why a small executable system beats a wiki at launch

High-traction educational repositories tend to give users an immediate act:
run it, inspect it, change one assumption, and falsify the result. A wiki can grow
around that system, but a wiki launched first has no proof that its categories
survive contact with data.

For this project, the executable artifact provides:

1. a two-minute result with no cloud account;
2. transparent math, synthetic conformance evidence, and one public paired case;
3. a sharp, shareable failure case;
4. a contribution unit: bring one assurance case; and
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
- runnable lessons, synthetic conformance cases, and a non-synthetic public paired
  case.

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

## Mutating the checker rather than the code

An earlier draft of the README claimed this package reports "a question no
evaluation framework currently reports". An adversarial prior-art sweep
falsified that. The idea of mutating the checking artifact instead of the thing
under test is an established sub-genre, and leave-one-out gate ablation has
already been published for LLM release decisions. The citations belong here
because every other claim in this repository has a landscape entry and this one
did not, which was itself a tell.

| Prior art | What it establishes |
|---|---|
| Di Guglielmo, Fummi, Pravadelli, *Vacuity analysis for property qualification by mutation of checkers*, DATE 2010 | Mutating the **checkers** rather than the design, to find properties that pass vacuously. The mechanism, sixteen years earlier. |
| Schuler and Zeller, *Checked coverage*, ICST 2011 / STVR 2013 | "Which executed code actually influences what the oracle checks." The load-bearing question, for test suites. |
| Chockler, Kupferman, Vardi, *Coverage metrics for formal verification* | A coverage metric over a specification, built by mutation. The claimed analogy already exists. |
| Jahangirova, Clark, Harman, Tonella, *Test oracle assessment and improvement*, ISSTA 2016; OASIs, ISSTA 2018 | Grading the oracle by mutation. |
| Vera-Pérez, Monperrus, Baudry, extreme mutation / pseudo-tested methods (Descartes) | Delete a whole unit; if nothing notices, it was pseudo-tested. |
| Black, Okun, Yesha, *Specification mutation*, ASE 2000 | Mutating specifications rather than code. |
| Synopsys Certitude, functional qualification | Commercial tooling that measures a verification environment's ability to detect faults. |
| Adebayo et al., *Sanity Checks for Saliency Maps*, NeurIPS 2018 | Destroy what a method claims to depend on and confirm its output changes. The cleanest ML ancestor. |
| Maiorano, *Automated Self-Testing as a Quality Gate*, arXiv:2603.15676, March 2026 | **The strongest citation against novelty.** Five quality gates over an LLM system, promote/hold/rollback verdicts, and gate ablation reported in the abstract: removing evidence coverage from the decision logic would have promoted both severe failures. Same domain, same mechanism, predating this package. |
| Bloomfield and Rushby, *Confidence in Assurance 2.0 Cases*, arXiv:2409.10665 | "Excising any subtree will increase probabilistic confidence at the top node." The ablation phenomenon, published as a known pathology. |
| SPADE, VLDB 2024 (deployed in LangSmith) | Selects a minimal assertion set meeting coverage constraints. Deciding which assertions can be dropped is a load-bearingness computation, shipped commercially. |

### Refusing to answer when evidence is absent

Also not novel, and established in three literatures:

| Prior art | What it establishes |
|---|---|
| Assurance 2.0 / Clarissa (SRI, Adelard), arXiv:2409.10665 | Evaluates over true / false / **unsupported**, propagating: an unsupported antecedent makes the parent unsupported. The required semantics, exactly. |
| OMG SACM 2.1; GSN Community Standard | `needsSupport` as a machine-readable state for a claim with no evidence; the undeveloped-goal diamond. `unprovided_coverage` is `needsSupport`, restated. |
| Three-valued model checking; runtime verification | `inconclusive` verdicts by design. |
| Fail-closed design | The ordinary security-engineering name for the property. |
| *Evidence-Driven Release Gates for LLM Sales Agents* (June 2026) | Ships promote/hold/rollback with a coverage metric and states "incomplete evidence is not a pass" and "a judge outage that leaves a level unscored is a coverage hole rather than a silent pass" — this repository's thesis sentence, in its domain, before its first commit. |

### What is left

Narrow, and worth stating without inflation: an offline, contract-bound
primitive over a portable evidence bundle that enumerates required coverage
dimensions with no enabled provider, and reports whether removing a sole
provider would flip *this* bundle's verdict green under a
requirements-derived-from-enabled-checks engine. Shipped as a CLI and a library
function.

The one defensible distinction from arXiv:2603.15676 is directional. That paper
ablates gates analytically, after the fact, to explain which dimension
discriminated regressions in a case study, and has no abstain verdict: a gate
that fails to run is simply absent from its decision logic. Here the ablation is
not the finding, it is the test of a shipped architectural invariant — fixed,
versioned required coverage — that makes a missing gate return `INCOMPLETE`
instead of disappearing. That is one paragraph's worth of difference, not a
headline.

What no eval product ships, as of this sweep: an automated, per-check,
verdict-level ablation as a feature. Inspect, LangSmith, Phoenix, Weave,
Promptfoo, Ragas, DeepEval, HELM and lm-evaluation-harness have nothing here,
and several actively manufacture silent passes. That is a gap in tooling, not a
gap in the literature, and it is the honest form of the claim.

## Coverage closure over dynamic delegation

The fixed-contract argument assumes required evidence can be enumerated before
the run. That holds for an agent calling a model in a loop. It stops holding when
the agent spawns subagents at runtime, because the shape of what it did is not
known until it has done it. A subagent can call tools nobody wrote a gate for, and
its cost rolls into the parent's totals as ordinary compute.

Read literally, this package's own logic makes such a run unassessable: evidence
exists that no gate covers, so INCOMPLETE is the only honest verdict. Read
naively, that makes every dynamic agent permanently incomplete. `delegation.py`
takes the third option: require closure rather than enumeration. A contract need
not anticipate each delegation; it must require that each one is accounted for.

| Prior art | What it establishes |
|---|---|
| Modular and compositional assurance cases; contract-based design (Sangiovanni-Vincentelli et al.) | One argument discharging obligations onto another, with interface contracts between components. The composition idea is not new. |
| Dynamic and through-life safety cases (Denney, Pai and others) | Assurance arguments that are updated as a system operates rather than fixed at certification. The temporal idea is not new either. |
| GSN "away goals" and module interfaces | An argument explicitly deferring a claim to another argument, which is what a declared delegation does. |
| Distributed tracing (OpenTelemetry span parentage) | The graph walked here. Tracing records the structure; it does not gate on whether the structure was anticipated. |

**What appears to be absent**: any of this applied to structure discovered at
runtime, in an agent delegation tree, as a shipped check that refuses. Tracing
tools show the tree. Assurance frameworks compose arguments over an architecture
known in advance. Nothing observed measures the share of delegated compute that
falls under a contract, or fails a build when it does not.

The number is `closure`: accounted delegated spend over total delegated spend. It
is weighted by cost rather than count, because one undeclared subagent that burns
the run matters more than five that return immediately. Unlike the conformance
line elsewhere in this package, it is not an invariant. It varies with the run and
it degrades as an agent becomes more dynamic, which is the direction the field is
moving. On the shipped session-tree fixture it is 0% undeclared and 100% declared.

Two honest limits. It measures declaration, not quality: a declared subagent is
accounted for even if nobody looked at what it did. And detection is authoritative
on tool name rather than graph shape, because inferring delegation from structure
conflated sequencing with delegation and reported a file read as a subagent. Tool
calls that spawned model work under some other name are surfaced as suspected, and
never counted as closed.

## Attestation for the instruments that produced the evidence

Every gate here rests on evidence, and every piece of evidence was produced by
something: a rubric applied by a human, an LLM judge, a subagent, a metric
pipeline. The contract records which instrument. Nothing recorded whether it
works, so `provenance.py` applies the package's own rule one level down: an
unattested instrument supplying a sole-provider gate forces INCOMPLETE.

The idea is old and the prior art is deep. This is not presented as new.

| Prior art | What it establishes |
|---|---|
| Metrology: calibration certificates and their validity periods | An instrument carries a record of what it was checked against, how closely, and when; measurements taken on a lapsed certificate are not accepted. This module is that, restated for eval instruments, including the expiry. |
| Measurement systems analysis, Gauge R&R | Validating the measurement system before trusting measurements taken with it. A century of manufacturing practice. |
| Inter-rater reliability; Cohen's and Fleiss' kappa | The agreement statistic itself, and the long-standing insistence that a rater be characterised before their labels are used. |
| W3C PROV | A vocabulary for recording what produced a piece of data. Provenance as a first-class record is not new. |
| The current LLM-judge calibration literature | Measuring judge agreement against human labels is established and widely practised. |
| Assurance 2.0's "confidence in evidence" | Assurance cases already distinguish a claim's structure from confidence in the evidence leaves. |

**What appears absent** is gating a deployment decision on the calibration state
of the instrument that produced its evidence. Judges are calibrated and the
number is reported; nothing observed refuses to issue a verdict when that number
is missing, too low, measured on too small a sample, or too old. The practice
exists. The enforcement does not.

Two design choices worth stating. `as_of` is a required argument rather than
defaulting to today, because a verdict that silently changes with the wall clock
is not a reproducible artifact and everything else here is. And `agreement` is
deliberately not named as to method: agreement against human adjudication,
Cohen's kappa and held-out accuracy are different quantities, `method` says
which, and this does not pretend they are interchangeable. What is enforced is
that a number exists, measured against something named, on a stated sample, on a
stated date.

The honest limit: this attests the instrument, not the individual label. A judge
in calibration can still be wrong about a particular task, and nothing here
detects that.
