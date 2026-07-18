# Case Study: From Hidden Agent Cost to Economic Assurance

## Contents

1. Starting material
2. Ideas considered
3. Landscape correction
4. Gap selected
5. Artifact built
6. Modularity proof
7. Benchmark result
8. Positioning decisions
9. GitHub audit
10. Rejected claims
11. Revisit conditions

## 1. Starting material

The work began with a 45-minute lesson about the hidden economics of AI agents:
multi-turn spend, context growth, retrieval loops, retries, tool calls, quality
thresholds, and pre-production risk. A second concept proposed a zero-compute-cost
semantic circuit breaker delivered through MCP. The user also considered a broad
LLM wiki modeled after well-known educational repositories.

The target audience included enterprise AI architects, agent engineers, FinOps,
product, finance, risk leaders, and technical learners.

## 2. Ideas considered

### Generic agent-cost dashboard (rejected)

Observability platforms already report tokens, models, latency, traces, and cost.
Another dashboard would compete on implementation breadth without a clear new
decision.

### Semantic loop/deadlock circuit breaker (narrowed)

Repeated tool-call shapes and dependency cycles can be useful warnings. They do
not prove equal intent, lack of progress, or deadlock. Pagination, polling, search
refinement, and healthy coordination can look repetitive or cyclic. Deterministic
budgets, call caps, timeouts, authorization, and escalation are stronger enforcement
boundaries.

### MCP-first framing (rejected as the wedge)

MCP is a transport/integration choice, not the enterprise decision. Leading with it
would hide the actual value and prematurely constrain the architecture.

### Broad LLM wiki (deferred)

Resource collections can attract readers but do not prove a scarce engineering
capability. First-principles lessons became a supporting layer inside the flagship
artifact instead.

## 3. Landscape correction

The research showed that vendors such as agent-observability and evaluation
platforms already cover important parts of the problem. Runtime guardrails also
cover caps, timeouts, permissions, and some loop signals. The project therefore
should not claim to replace those systems.

The missing boundary was the portable deployment decision assembled from evidence
those systems can export.

## 4. Gap selected

Final gap statement:

> For enterprise AI architects, agent engineers, finance, product, and risk teams,
> existing traces and evaluation results do not provide one portable, inspectable
> answer to whether a workload should scale, run with assistance, stop, or be
> declared incomplete because outcome quality, full downstream cost, a named
> counterfactual, policy, and required coverage remain fragmented.

The category became **economic assurance for AI agents**.

## 5. Artifact built

Agent Economics Lab implements one complete evidence loop:

```text
CSV or normalized JSON evidence
        ↓
canonical bundle + digest
        ↓
typed, ordered, versioned checks
        ↓
Markdown/JSON assurance case
        ↓
INCOMPLETE / SCALE / ASSIST / STOP
```

Inputs include call-level traces, task outcomes, labor/remediation/incident costs, a
named counterfactual baseline, and versioned policy.

The project uses no third-party runtime packages. Packaging still uses setuptools,
so “dependency-free” was rejected as imprecise.

## 6. Modularity proof

The differentiator was not merely that modules could be registered. It was that
removal could not silently make the result greener.

The two-minute demonstration produced:

```text
DEFAULT              ASSIST
DELETE DIAGNOSTIC    ASSIST (finding removed)
DELETE REQUIRED      INCOMPLETE (outcome_quality missing)
ADD CUSTOM GATE      STOP
```

CSV and normalized JSON adapters also produce equivalent canonical evidence.

## 7. Benchmark result

The controlled benchmark contains:

- 98 deterministic synthetic scenarios;
- 588 single-module ablations;
- 510 comparisons whose complete result was not `SCALE`;
- 23 false `SCALE` results under an unsafe available-checks-only reducer (4.5%);
  and
- zero false `SCALE` results under fail-safe required coverage, which returned
  `INCOMPLETE` when coverage was missing.

Interpretation: the tested engine enforces the missing-coverage invariant under the
fixed synthetic perturbations. It does not estimate how often enterprises make
false-green decisions or prove production policy quality.

## 8. Positioning decisions

Accepted GitHub category:

> Applied AI research engineer building economic assurance for AI agents.

Accepted profile order:

1. category;
2. “Your agent passed its evals. Can you prove it should scale?”;
3. evidence inputs and bounded decision;
4. Question / Test / Result;
5. `make reproduce`;
6. synthetic limitation; and
7. adapters, assurance checks, and redacted evidence cases as contribution lanes.

Multi-agent handoff, provenance, and authority failures remain the next research
direction, not a shipped capability.

## 9. GitHub audit

The public account had no bio or profile README and foregrounded older toolchain
repositories. Newer visible repositories were not strong pins:

- one teaching repository withheld its engine;
- one project contained only a short README; and
- one looked like an upstream starter.

The resulting rule was **pin quality, not quantity**. Publish and pin the flagship
artifact first. Keep its protocol, benchmark, note, data card, and methodology
together rather than splitting them into superficial repositories.

## 10. Rejected claims

- enterprise-proven;
- production-ready authorization layer;
- prevents false-green decisions without benchmark scope;
- works with named vendors before adapters ship;
- semantic loop detection or deadlock proof;
- zero compute;
- first or only category claim;
- production prevalence inferred from 4.5%; and
- multi-agent system support before executable HandoffLab work exists.

## 11. Revisit conditions

Reconsider stronger claims only after:

- independent redacted evidence cases;
- fixture-backed vendor export adapters;
- prospective policies chosen before outcomes are observed;
- additional adversarial and distribution-shift benchmarks;
- a runnable multi-agent handoff benchmark; or
- external replication of the core safety property.
