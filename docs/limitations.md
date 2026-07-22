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

## Outcome labels can dominate the result

“Acceptable” must be operationalized before analysis. Human labels require a rubric
and agreement checks. Automated graders require validation against the decision the
enterprise actually cares about. A convenient proxy can make the economics precise
and wrong.

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
declared required coverage is missing. It cannot prove that a third-party gate
correctly implements the coverage it claims. Review module code, pin its ID/version,
test counterexamples, and treat the evidence digest as reproducibility metadata, not
as a signature or security attestation.

## Generic interchange is not a finished vendor adapter

`source.normalized-json@1` is the stable offline boundary for mappers. It does not
mean arbitrary Galileo, LangSmith, or OpenTelemetry exports can be consumed without
normalization. Vendor formats evolve; every adapter needs pinned fixtures and an
equivalence test.

## Event and cost semantics must be mapped explicitly

The default runtime-call cap counts canonical trace events. A source adapter must
decide which source spans represent calls versus internal bookkeeping. The
single-arm engine preserves legacy behavior in which non-model events without a
direct cost contribute zero trace spend. The paired frontier is stricter: an absent
non-model cost returns `INCOMPLETE`; explicitly free or included events must record
`direct_cost_usd: 0.0`. Rate-card-priced model events must include explicit token
counts and positive usage. Source adapters must preserve these distinctions.
