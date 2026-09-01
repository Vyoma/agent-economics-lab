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

## Cost-per-outcome is academic mainstream, and five sweeps missed it

A sixth adversarial sweep (September 2026) found the economics lane preempted
by work none of the earlier five surfaced, which for a document claiming
adversarial sweeps is itself the finding worth recording:

- *Cost-of-Pass: An Economic Framework for Evaluating Language Models*
  ([arXiv:2504.13359](https://arxiv.org/abs/2504.13359), April 2025) defines
  the expected monetary cost of obtaining a correct solution as the evaluation
  primitive, with a frontier against human-expert cost. That is cost per
  confirmed outcome, published first.
- Kapoor et al., *AI Agents That Matter*
  ([arXiv:2407.01502](https://arxiv.org/abs/2407.01502), 2024) made
  cost-controlled evaluation and cost-accuracy Pareto frontiers the canonical
  position a year earlier still.
- The *Holistic Agent Leaderboard*
  ([arXiv:2510.11977](https://arxiv.org/abs/2510.11977)) operationalizes
  cost-aware agent evaluation as shared infrastructure, and FrugalGPT
  ([arXiv:2305.05176](https://arxiv.org/abs/2305.05176)) and the
  router/cascade literature optimize the same quantity in deployment.
- Commercially, per-resolution pricing has existed since 2023.

Nothing in this project's economics framing is a contribution. What it ships
is the composition: those quantities computed offline from normalized
evidence, gated fail-closed, under a decision contract. The framing itself is
theirs.

## Fail-closed required coverage is not a new idea

An earlier version of this document surveyed the economics and observability lane
thoroughly and omitted the lane where this project's central invariant actually
originates. That omission made a decades-old idea look like a contribution. The
invariant is:

> A required check that did not run must not read as a check that passed.

That is prior art, and well-established prior art:

- [GitHub required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
  pin a required list in branch-protection configuration. A check that never
  reports stays pending and blocks the merge; it does not become green because
  the checks that did run passed. This is the same fixed-contract behavior,
  shipped since 2015.
- [Kubernetes admission webhooks](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#failure-policy)
  with `failurePolicy: Fail` reject a request when a required admission
  controller is unreachable, rather than admitting it unchecked.
- [in-toto](https://in-toto.io/) layouts sign an expected list of supply-chain
  steps. Missing link metadata for a required step fails verification. The
  layout is the fixed contract; the links are the evidence.
- [SLSA](https://slsa.dev/) provenance and
  [OPA](https://www.openpolicyagent.org/) / Conftest deny-by-default policy
  bundles express the same default: absence of an attestation is not a
  satisfied requirement.
- [InvarLock](https://www.invarlock.ai/docs/assurance/reproducibility)
  publishes signed evidence packs that SHA-256-bind artifacts, policy files,
  runtime config, and verdict calculations for ML evaluation, with
  recipient-controlled acceptance; Red Hat's
  [EvalHub](https://developers.redhat.com/articles/2026/06/16/store-immutable-ai-evaluation-records-evalhub-oci)
  stores immutable eval records by OCI digest with a provenance chain. Digest
  binding of evaluation evidence is shipped industrial practice, not an idea
  from here; the residual here is the granularity (each check's own run
  source), and [docs/limitations.md](limitations.md) records that this
  fingerprint is non-transitive through shared helpers.
- The *LLM Readiness Harness*
  ([arXiv:2603.27355](https://arxiv.org/abs/2603.27355)) ships CI gates for
  LLM applications, and Maiorano's release-gate work
  ([arXiv:2603.15676](https://arxiv.org/abs/2603.15676), cited in
  [docs/novelty.md](novelty.md)) ships PROMOTE/HOLD/ROLLBACK decisions where
  evidence coverage is the primary determinant of rejection. Fail-closed
  eval-coverage gating for LLM releases specifically is published prior art.
- Safety-case practice in
  [DO-178C](https://www.rtca.org/) and
  [ISO 26262](https://www.iso.org/standard/68383.html), and Goal Structuring
  Notation more generally, treat argument completeness as an explicit
  obligation. An unsupported goal invalidates the case; it is not silently
  dropped.

So the delta claimed here is narrower than "fail-closed coverage." It is:

```text
fail-closed required coverage applied to ECONOMIC decision dimensions
  + an adjudicated acceptable-outcome label
  + full cost including labor, remediation, and incident loss
  + a named counterfactual baseline
  + one portable artifact that engineering, finance, product, and risk read
```

The gate-completeness mechanism is borrowed. The economic dimensions it is
applied to, and the refusal to issue a verdict without a counterfactual, are the
parts worth reviewing.

One further correction belongs here, because it bounds the mechanism itself.
Fixed required coverage detects a *removed* gate by construction. It does not
detect a *substituted* gate that keeps its declared ID, version, and coverage
while ceasing to enforce anything, and against that operator a fixed contract
scores no better than a dynamic one. The per-check implementation fingerprint in
the decision-contract digest exists for that case, and covers only a check's own
body: it is not transitive through shared helpers, as
[limitations.md](limitations.md) records. `make mutation-score` reports
both operators side by side, and
[docs/limitations.md](limitations.md) states the residual gap.

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

## Coverage closure over dynamic delegation

`agent_economics/delegation.py` measures the share of delegated spend a contract
accounts for. An adversarial prior-art sweep was asked to refute the claim and
returned *partially novel*, with several sources closer than the first draft of
that module admitted. They are listed first.

| Prior art | What it establishes |
|---|---|
| Mishra and Sharad, *Observability for Delegated Execution in Agentic AI Systems*, [arXiv:2606.09692](https://arxiv.org/abs/2606.09692), June 2026 | States the premise almost verbatim, names **"delegation closure / lineage"** as a requirement, and states the coverage-accounting principle: uncovered channels must be treated as unknown, and global accountability requires explicit detection of missing coverage. The closest work by some distance. |
| Nian et al., *Auditable Agents*, [arXiv:2604.05485](https://arxiv.org/abs/2604.05485), April 2026 | Defines an accounted-fraction over policy-relevant actions **including delegation events**, plus a magnitude-weighted Gap Burden, and argues for magnitude weighting in nearly the terms used here. Also reaches an "incomplete" verdict. |
| Armesto and Kolb, *Closure Gaps and Delegation Envelopes for Open-World AI Agents*, [arXiv:2604.25000](https://arxiv.org/abs/2604.25000), April 2026 | Terminology collision rather than subsumption: their closure gaps concern specification adequacy before acting. Noted because "closure", "delegation" and "open-world" are now taken twice in this space. |
| ISA 600 (Revised), group audits; ISA 705 (Revised) | Delegated work is either covered by the group team's procedures or by reviewed component work, and an inability to obtain sufficient evidence produces a qualified opinion or a disclaimer, with materiality as the magnitude test. This subsumes the concept completely and predates it by decades. |
| SOC 2 carve-out versus inclusive method | The same disjunction: a delegated subservice organisation is inside the report or explicitly outside its opinion. |
| FinOps Foundation untagged-cost KPI | Cost-weighted accounted-fraction, published as a KPI, already carried into AI spend attribution. The weighting argument is not new. |
| in-toto sublayouts | Already implement "the delegated work carries a contract of its own", verified recursively. An earlier draft of `delegation.py` promised that disjunct without implementing it; the promise has been removed. |
| AgentSpec ([arXiv:2503.18666](https://arxiv.org/abs/2503.18666)); allowlists of permitted sub-agents in agent gateways | "Declare permitted delegations" is shipped practice. These prevent at spawn time; they do not measure a residual or return an incomplete verdict. |

### What survives

**The denominator is the contract, not the ground truth.** The agent work above
measures whether the *record* captured what happened: whether the gateway
observed the tool, whether the trace covered the lifecycle. This measures whether
anyone *undertook to assess* what the record already shows. A run can be
perfectly instrumented, every subagent traced, full observability coverage, and
still score zero closure because no delegation was declared. That failure mode is
invisible to all three agent papers, and it is the one that bears on a scale
decision.

Narrowly: a cost-weighted ratio of delegated spend accounted for by a declared
manifest carried in a pinned conversion contract, computed offline from a trace,
where a shortfall routes to `INCOMPLETE` rather than `FAIL`, shipped as a check.
The refusal is real and verifiable: `assurance.py` computes `unmet_coverage` from
gates that could not run and routes it above the STOP branch.

Lanes the sweep found empty, which is where the ground is firmest: distributed
tracing treats orphan and missing spans purely as data-quality troubleshooting,
with no accounted-fraction and no gate; contract-based design remains
closed-composition; and no observability or eval product detects that a spawned
subagent was never declared.

## Auditing benchmark labels and trajectories is a crowded lane

The findings in [research/CORPUS.md](../research/CORPUS.md) and
[research/OUTCOME_AUDIT.md](../research/OUTCOME_AUDIT.md) sit in a lane with
substantial neighbors, closer than earlier drafts of this document
acknowledged:

| Prior art | What it establishes |
|---|---|
| SWE-Bench+ ([arXiv:2410.06992](https://arxiv.org/abs/2410.06992)) | 32.67% solution leakage and 31.08% weak tests in SWE-bench. Benchmark-label auditing at scale, before this project existed. |
| UTBoost ([arXiv:2506.09289](https://arxiv.org/abs/2506.09289)) | 345 mislabeled passes and 36 insufficient-test instances in SWE-bench and Verified, found by augmenting the graded tests. |
| *The SWE-Bench Illusion* ([arXiv:2506.12286](https://arxiv.org/abs/2506.12286)); [OpenAI on retiring SWE-bench Verified](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/); [METR on unmergeable passing PRs](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/) | The benchmark's headline number measures less than it reads as measuring, said by three independent parties including its own steward. |
| SWE-Bench++ ([arXiv:2512.17419](https://arxiv.org/abs/2512.17419)) | Runs 3x determinism checks because label flakiness is a known, quantified hazard. |
| AgentLens ([arXiv:2605.12925](https://arxiv.org/abs/2605.12925), May 2026) | Process-audits 1,815 SWE-bench Verified trajectories and names the lucky-pass problem. Trajectory-level auditing, published first. |
| ATBench ([arXiv:2604.02022](https://arxiv.org/abs/2604.02022)) | Publishes 165 fine-grained label corrections across 129 agent trajectories. |
| *Automated Transcript Analysis for Detecting Flaws in Agentic Benchmarks* ([arXiv:2607.27518](https://arxiv.org/abs/2607.27518), July 2026) | Automated scanners for transcript-level validity defects. |

### What survives

Not the activity, which is a crowded lane, and not the method. What no
neighbor does: freeze content-free evidence rows keyed to a pinned upstream
revision so every claim re-verifies offline without redistributing anyone's
data; record clean bills with the same care as defects, in a registry built to
accumulate; and refuse fail-open in the auditor itself, where a row the parser
cannot fully read is excluded and counted rather than guessed at. And, as
priority rather than method: nobody had audited these specific uploads. The
findings are first about their objects, not their kind.

## Attestation for the instruments that produced the evidence

`agent_economics/provenance.py` refuses a verdict when an evidence-producing
instrument is unattested, weakly agreeing, or out of calibration. A second sweep
returned *partially novel*, and the mechanism is not new anywhere except this
domain.

| Prior art | What it establishes |
|---|---|
| DO-330 and ISO 26262-8 clause 11, tool qualification | **The strongest citation against this.** Certification credit cannot be taken from an unqualified tool, and the independent-verification exemption is the same sole-provider carve-out implemented here. Cited here because `docs/landscape.md` already referenced these standards for a different point while missing the clause containing this mechanism. |
| PPAP element 10 with Measurement Systems Analysis | A production-release decision is refused when Gauge R&R fails: an agreement analogue, a stated sample design, a named reference, a date. |
| CLIA: 42 CFR 493 subpart H; 42 CFR 493.1255; Westgard QC | Two failed proficiency events and a laboratory must cease reporting that analyte. Calibration verification at least every six months is a literal maximum age. QC failure holds patient results. Analysers refuse to run a test once a calibration curve lapses. The closest complete analogue, expiry included. |
| ISO/IEC 17025:2017 clauses 6.4.9 and 7.10 | Goes further than this module: equipment found out of calibration triggers review and recall of results already issued. This refuses only forward. |
| Usami et al., *LLM Judges Have Dark Current*, [arXiv:2606.15610](https://arxiv.org/abs/2606.15610), June 2026 | Argues a judge should be reported as a measurement instrument and gives a metrological protocol for measuring the measuring device. **The metrology framing is theirs and predates this.** It defines no threshold, no expiry and no consequence. |
| Psychometrics imported into LLM evaluation: [arXiv:2310.16379](https://arxiv.org/abs/2310.16379), the systematic review [arXiv:2505.08245](https://arxiv.org/abs/2505.08245), and *Measuring what Matters* ([arXiv:2511.04703](https://arxiv.org/abs/2511.04703), reviewing 445 benchmarks for construct validity) | Reliability-necessary-but-not-sufficient is a century of measurement theory, repeatedly and explicitly applied to LLM evals before this package existed. The distinction is not a contribution; only its mechanized enforcement as a method-typed floor was not found. |
| The ABC checklist, *Establishing Best Practices for Building Rigorous Agentic Benchmarks* ([arXiv:2507.02825](https://arxiv.org/abs/2507.02825), NeurIPS 2025 D&B) | Task validity versus outcome validity for agent benchmarks, formalized as 30 criteria. The conceptual separation this package enforces, published as a checklist first. |
| EvalGen, *Who Validates the Validators?* ([arXiv:2404.12272](https://arxiv.org/abs/2404.12272)) | Requires human alignment before trusting a judge, as a workflow. The requirement is prior art; the fail-closed gate form was not found. |
| *Eval Factsheets*, [arXiv:2512.04062](https://arxiv.org/abs/2512.04062) | Specifies the attestation record fields, including who made the evaluation and when, and how it is reliable. Reporting only. |
| *Evaluation Cards*, [arXiv:2606.09809](https://arxiv.org/abs/2606.09809) | Explicitly declines to assign pass/fail thresholds. Evidence that the field's reporting layer deliberately does not gate. |
| *Trust or Escalate*, [arXiv:2407.18370](https://arxiv.org/abs/2407.18370) | The only thing in the judge literature that refuses, but per instance on runtime confidence, not a deployment decision on a stored calibration record. |
| Crowdsourcing gold-question QC; sample ratio mismatch; in-toto, SLSA and Conforma attestation expiry | Agreement against a reference deciding whether labels count; apparatus-integrity gates; and the expiry pattern. All attest identity, process integrity, or per-item quality rather than instrument calibration. |

### What survives

Three things together, and only the third is genuinely unclaimed: a stored
per-instrument record; an age limit evaluated against a caller-supplied `as_of`
rather than the wall clock, so a verdict is reproducible; and an `INCOMPLETE`
outcome **distinct from FAIL**, so that unknown quality does not route to STOP.

The honest concession on tool qualification is that the mechanism is entirely
theirs. Tool qualification qualifies a deterministic tool against a development
process, once, bound to a version, with no time-based expiry and no agreement
statistic. The object here is a stochastic instrument whose behaviour changes
without a version bump, so the certificate has to carry an agreement number
against a named reference on a stated sample and a date, and it has to lapse on a
clock rather than on a version.

Two corrections the sweep forced. The module now implements the sole-provider
carve-out its docstring described and its code did not. And thresholds are
per-method: raw agreement, Cohen's kappa and held-out accuracy do not share a
bar, and comparing all three against one number was a category error that
ILAC-G8 exists to prevent. An attestation whose method has no stated floor is
refused rather than graded on another method's scale. The floors are conventional
landmarks, not derived from this package's data, and are labelled as such.

## What other frameworks do when a check cannot run

This section exists because the stance this package takes — that evidence which
could not be produced is not a result — is only worth taking if the field does
something else. A survey was run against primary sources to find out. **It
refuted the premise it started from**, and the real answer is more interesting.

### The premise that was wrong

The survey set out to confirm that eval frameworks silently convert a failed
check into a pass. **They do not.** No mainstream framework treats a broken
check as a pass. The one clear historical case, Guardrails AI defaulting
`on_fail` to `NOOP`, was fixed by its maintainers: the default became
`OnFailAction.EXCEPTION` in v0.6.0. DeepEval's `ignore_errors`, which looked
like the same thing, records the error and marks the item a **failure**, and
both it and `skip_on_missing_params` default to `False`, so the default aborts.

That framing is retired. It was wrong.

### What the field actually divides on

Not whether a broken check passes, but whether it is **counted somewhere the
reader will see**.

| Behaviour | Frameworks |
|---|---|
| Aborts by default | UK AISI Inspect, DeepEval, lm-evaluation-harness, HELM, Arize Phoenix, Guardrails 0.6+, openai/evals |
| Reports an un-scored state | **Inspect** (counts `scored_samples` and `unscored_samples` beside the metric, and defaults `aggregate(on_missing="error")`), Langfuse, MLflow, Braintrust Python/TS, Phoenix, LangSmith (best effort) |
| Drops from the denominator | Ragas, MLflow, Braintrust Python/TS, DeepEval under `skip_on_missing_params`, Weave numeric means |
| Folds into a zero or a fail | OpenAI graders (documented: a grader exception or non-numeric output "will be marked as invalid and return a 0 grade"), promptfoo judge transport failures, DeepEval under `ignore_errors`, Braintrust C#/Java |

**UK AISI Inspect is the closest prior art to the position this package takes,
and it is better at the reporting half.** `Score.unscored()` is a first-class
state, the exclusion is counted rather than merely performed, and the aggregate
default is to error on missing values. Anything this package says about refusing
should credit it.

The sharpest remaining gap is silent denominator shrinkage. Ragas is the clearest
case: with `raise_exceptions=False` and `np.nanmean`, a run where forty of a
hundred judge calls fail reports the mean of the surviving sixty, in the same
shape as a complete run, with no count of the missing forty. MLflow does the same
with a log warning as the only signal. Both offer a stricter setting; neither
makes it the default.

### Every design here has a stated reason

The maintainers are not careless, and the write-up should not imply it. DeepEval's
flag exists because a custom model "generating invalid JSONs ... will stop the
execution of the entire test run". MLflow isolates sub-scorer failures "so one bad
scorer doesn't abort the whole ensemble". HELM drops NaN statistics because
"Python's stdlib json.dumps() will produce invalid JSON when serializing a NaN".
Weave's own pull request is candid that its fix is partial.

Two projects have argued the principle explicitly, from opposite directions.
promptfoo's source declines to invert a grader error into a pass because "a
grader error is not evidence that the criterion was or was not met". Inspect's
changelog reaches the same conclusion by the other route, keeping judge-parse
failures visible "rather than inflating the INCORRECT count".

### The honest conclusion

The field has converged on *not a pass*. It has not converged on *how to report
not a score*. An explicitly counted un-scored state is a minority position, held
clearly by one framework and partially by several others.

That is a narrower justification for this package's stance than the one it
started with, and it is the true one.

### This repository was doing the worst version of it

Until the commit that added this section, `kimi_judge` wrote a task the judge
never evaluated into the outcomes CSV as `acceptable: false`. That file is the
evidence a verdict is built from, so a judge outage lowered the acceptable rate
and was indistinguishable from a genuinely bad result. The audit sidecar recorded
the truth and nothing downstream read it.

That is the fold-into-a-fail behaviour catalogued above, in the package that
argues against it, while `kimi_eval` twenty files away already excluded errors
from its denominator under a test reading "an outage must not be reported as
strictness". It is fixed, and it is recorded here rather than quietly corrected,
because a survey of other people's defaults has no standing from a project that
had not checked its own.
