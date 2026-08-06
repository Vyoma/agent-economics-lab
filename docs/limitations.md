# Limitations and non-claims

The project is designed to make weak claims visible. It does not make them strong
by itself.

## The demo is pedagogical

Eight synthetic tasks are enough to inspect every calculation, not enough to infer
production behavior. A real decision needs representative volume, seasonality,
segment analysis, uncertainty bounds, and monitoring for distribution shift.

The paired frontier fixture has 180 synthetic tasks. Its intervals exercise the
selection method, but synthetic volume does not create external validity. A public
enterprise-impact claim needs a permissioned matched-task study and independent
reproduction.

## Paired uncertainty does not create causality

Exact pairing of task IDs, input digests, and rubric versions controls task-mix
differences. It does not control route order,
provider drift, learning effects, benchmark contamination, or unobserved changes
between arms. Use randomized or counterbalanced assignment before interpreting a
paired difference as causal.

The Clopper-Pearson bound covers the observed harmful-transition process under a
binomial model. The paired percentile bootstrap reflects sampling variation in
recorded full cost, but its interval and nominal confidence target are approximate
and include Monte Carlo error. The plan rejects a resample count that cannot resolve
the adjusted lower tail. Derived endpoints are canonicalized to 12 significant
digits for cross-runtime reproducibility. This numeric precision is not additional
statistical certainty. Neither method repairs biased labels, correlated duplicates,
missing failed runs, or an unrepresentative population.

## Most verdicts in the synthetic matrix are assumption artifacts

`make sensitivity` sweeps a 48-cell grid of incident-loss and remediation-cost
assumptions across the 98-scenario matrix and counts how many cells change the
verdict:

```text
ROBUST  (0 flips)   43/98   43.9%
BRITTLE (3+ flips)  55/98   56.1%
```

Fifty-five of ninety-eight scenarios produce a verdict that moves under
plausible economic assumptions. A 50% error in the baseline acceptable rate
flips the counterfactual gate in 25 of 98 scenarios. These are properties of a
synthetic fixture rather than a prevalence estimate, but the direction
generalizes: a decision built on an estimated incident loss, an estimated
remediation cost, and an estimated baseline inherits the error bars of all
three.

Report the fragility index beside the verdict. A `SCALE` from a scenario with
three or more flips is a statement about the assumptions, not about the agent.

## p95 is the maximum on small samples

`percentile` uses `rank = ceil(0.95 n)`, which equals `n` for any workload of
fewer than 20 tasks. On the eight-task demo fixture the reported p95 effective task
cost and the maximum effective task cost are therefore the same number by
construction, not two measures that happen to agree. Tail risk is one of the six
required coverage dimensions, so read it as "the worst task" until the workload
exceeds 20 tasks.

## Outcome labels can dominate the result

“Acceptable” must be operationalized before analysis. Human labels require a rubric
and agreement checks. Automated graders require validation against the decision the
enterprise actually cares about. A convenient proxy can make the economics precise
and wrong.

This is not a theoretical worry. Changing only the label source, on identical
traces, rates, baseline, policy, and decision contract, moved the verdict a full
decision class and flipped the sign of net value:

| | hand-authored labels | `kimi-k3` labels |
|---|---|---|
| decision | `ASSIST` | `STOP` |
| acceptable rate | 75.0% | 37.5% |
| cost per acceptable outcome | $3.50 | $14.76 |
| expected net value per attempt | $3.37 | $-2.53 |
| incremental vs baseline | $2.77 | $-3.13 |
| failing gates | 4 of 6 | 6 of 6 |

The decision-contract digest is identical in both runs. Every input except the
outcome column is byte-identical. The judge was stricter about unverifiable
specifics: its rationales flagged fabricated rate limits, an incorrect claim about
feature availability, and a mishandled error code that the hand labels accepted.

**Neither label set is validated ground truth**, and that is the point. This does
not show the judge is right and the hand labels wrong; it shows that the most
subjective input in the pipeline is also the one with the most leverage over the
output. Cost per acceptable outcome moved 4.2x on the same spend, because the
denominator is a judgment call.

Before trusting economics built on any label source, measure inter-rater agreement
against human labels on a sample, and report which source produced the labels
alongside the verdict. The judge writes that provenance into an audit sidecar for
this reason.

This comparison came from one live run. Judge output is not deterministic, so it is
not byte-pinned in `make reproduce`, unlike every other published number here.

## Cost attribution is a model

Shared infrastructure, cached work, prepaid commitments, labor, opportunity cost,
and low-frequency incidents need explicit allocation rules. This lab accepts the
provided figures; it does not reconcile invoices or replace finance systems.

## The counterfactual can be stale or unfair

A human-only baseline may contain queueing, escalation, training, QA, and error
costs that are easy to omit. An agent baseline can change with model versions or
prompt/configuration updates. Compare the same task population and publish the
assumptions.

## Averages hide subgroups

The lab reports an aggregate acceptable rate and tail cost. Production use should
slice by customer, language, task type, risk tier, model route, tool path, and other
relevant groups. A profitable aggregate can conceal a harmful or unprofitable
segment.

## A repeated signature is not semantic equivalence

The structural signature retains tool name, argument keys, containers, and
primitive types, while dropping values. It is cheap and deterministic. That makes
it useful for diagnostics and makes false positives inevitable. Repeated pagination,
polling, search refinement, or batch processing can be healthy.

## A directed cycle is not proof of deadlock

Cycle detection over a dependency graph says nothing about resource ownership,
wait conditions, timeouts, messages in flight, or the ability to make progress.
Call it a dependency-cycle warning unless those semantics are observed.

## “Zero compute” is not literal

Local structural checks avoid model-inference spend, but they still consume CPU,
memory, latency, and operational effort. The project uses the precise phrase
“no additional model inference” when that is the claim.

## This is not a runtime security boundary

The code analyzes local evidence and emits findings. It does not authenticate MCP
participants, authorize tool calls, enforce data policy, provide durable distributed
state, or guarantee fail-closed behavior. Use a production policy/guardrail layer
for those responsibilities.

## Decision thresholds are governance choices

The sample thresholds are not industry standards. Policy owners must set and review
them based on value, risk appetite, regulatory duties, customer commitments, and
the cost of false acceptance versus false rejection.

## Modularity does not establish trust in a module

The engine rejects diagnostics that attempt to route and returns `INCOMPLETE` when
declared required coverage is missing.

Two mutation classes must be distinguished, because the architecture treats them
differently. *Removing* a required gate is detected by construction: the fixed
contract still demands the dimension, so `INCOMPLETE` is the only legal answer.
*Substituting* a permissive gate that keeps the same ID, version, coverage, and
failure route is not detected by the coverage contract at all, because coverage
still appears satisfied and the gate simply stops failing. The per-check
implementation fingerprint in the decision-contract digest exists for that second
class, and it changes when a check's own body is substituted.

**The fingerprint is not transitive, and that limit is load-bearing.** It hashes
the source of each check's `run` function and nothing `run` calls. All six gates
route through one shared helper, `checks._result`. Editing that helper so it never
reports a failure moves the demo fixture from `ASSIST` to `SCALE` while leaving the
contract digest byte-identical. The same holds for `assurance.percentile`, which
`gate.tail-cost` depends on, and for the diagnostic helpers in `controls.py`. Both
were verified by executing them, not reasoned about.

The practical consequence: the digest is a reproducibility record for *which check
functions* ran, not an integrity guarantee for the engine. A reviewer who receives
an `AssuranceCase` from a producer they do not trust learns from the digest that
the declared checks and their bodies match a known-good value, and learns nothing
about the code beneath them. Detecting that requires pinning the package itself,
by version and artifact hash, which this project does not do for you.

What the fingerprint does not do: it cannot prove that a third-party gate correctly
implements the coverage it claims, and it is not a signature. A reviewer who never
compares the digest against a known-good value learns nothing from it. Review module
code, pin its ID/version, record the expected contract digest, test counterexamples,
and treat both digests as reproducibility metadata rather than as a security
attestation.

## One OpenTelemetry contract is not every vendor export

`source.otel-genai@1` consumes the pinned OTLP JSON and GenAI semantic-attribute
contract documented in
[`otel-genai-adapter.md`](otel-genai-adapter.md). Langfuse and Arize
OpenInference fixtures exercise one shared mapper, but arbitrary Galileo,
LangSmith, proprietary, or future OpenTelemetry exports still require an explicit
compatibility test. Vendor and semantic-convention formats evolve.

## Event and cost semantics must be mapped explicitly

The default runtime-call cap counts canonical trace events. A source adapter must
decide which source spans represent calls versus internal bookkeeping. The
single-arm engine preserves legacy behavior in which non-model events without a
direct cost contribute zero trace spend. The paired frontier is stricter: an absent
non-model cost returns `INCOMPLETE`; explicitly free or included events must record
`direct_cost_usd: 0.0`. Rate-card-priced model events must include explicit token
counts and positive usage. Source adapters must preserve these distinctions.

The checked-in [raw evidence-ablation
benchmark](../research/EVIDENCE_ABLATION_PROTOCOL.md) makes this boundary
executable. Four of nine constructed omissions are refused at the schema or
semantic-evidence boundary. Five decision-material omissions change `ASSIST` to
`SCALE`: incident loss, remediation cost, human review time, a directly priced tool
cost, and a timed-out event. These cases do not estimate prevalence. They show that
fixed check coverage cannot prove source completeness when absence is interpreted
as zero or when no independent attempt inventory exists.

## Claude Code conversion still requires human-owned semantics

`source.claude-code-jsonl@1` observes prompt boundaries, model usage, tool calls,
tool results, and source inventory. It does not infer whether a task was acceptable,
what the task was worth, the correct counterfactual, or current provider prices.
Those values come from a required conversion contract and remain claims owned by
the data owner.

The v1 adapter treats one external user prompt as one task and one unique assistant
message ID as one model call. It rejects sidechains and known unexpanded `Agent` or
`Task` delegations because a single parent JSONL file may omit their nested model
calls. It also requires exactly one same-task result for every client tool use.

`source.claude-code-session-tree@1` is a separate, explicit adapter for the
adjacent parent plus subagent transcript layout. It does not make the single-file
adapter permissive. It requires paired child transcript and metadata files, binds
all files into the source digest, and still refuses any delegation that cannot be
expanded. Its conformance fixture proves the pinned layouts and recursive task
attribution, not compatibility with every past or future Claude Code release.

Claude Code's local interactive transcript is an observed source format, not a
stable public interchange standard. Pinned fixtures and versioned compatibility
tests are required when Claude Code changes its record shape. The conversion
receipt is reproducibility metadata, not a signature or proof that a manual outcome
label or price card is correct.

## The public case is a benchmark case, not enterprise ROI

The public SWE-bench case uses real published trajectories, hidden-test outcomes,
client-estimated run spend, and API-call counts. It assigns zero monetized value,
human cost, remediation cost, and incident loss because the public source does not
publish defensible business values for those fields. Zero is a conservative credit
for this routing demonstration, not an estimate that a resolved task has no value.

Its paired Haiku reference is a technical counterfactual, not a human workflow.
The 20 outcome-blind selected tasks are sufficient for an inspectable demonstration,
not a population estimate. The frontier's exact harmful-regression upper bound and
claim boundary make that sampling uncertainty visible.
