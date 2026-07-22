# Paired Budget Breakage Frontier Protocol

## Research question

Can a fail-closed paired experiment identify a lower-cost tested agent configuration
without treating an underpowered zero-regression sample as evidence of zero risk?

## Motivation and prior work boundary

Joint quality and cost evaluation is established. `AI Agents That Matter` argues
that agent evaluations should account for both accuracy and inference cost:
<https://arxiv.org/abs/2407.01502>. Experiment platforms also compare scores,
latency, and token usage. This artifact does not claim experiment comparison itself
is novel.

The narrower contribution under test is an offline decision artifact that combines:

- exact pairing of task IDs, SHA-256 input digests, and rubric versions across a
  frozen candidate family;
- an exact upper confidence bound on harmful paired regressions;
- simultaneous adjustment across planned quality and cost tests;
- model, tool, labor, remediation, and incident cost; and
- fail-closed handling of missing arms, tasks, costs, and assurance coverage.

OpenTelemetry GenAI conventions can provide invocation, tool, evaluation, and usage
telemetry, but important GenAI conventions remain under active development. The
frontier consumes normalized offline evidence and does not claim the telemetry
standard guarantees economic completeness:
<https://github.com/open-telemetry/semantic-conventions-genai>.

## Frozen synthetic study

The checked-in conformance study contains 180 fingerprinted task identities and four
tested arms:

| Arm | Intended role |
|---|---|
| `premium-8-step` | reference route |
| `balanced-4-step` | cheap-first route with escalation |
| `cheap-2-step` | aggressive low-budget route |
| `premium-12-step` | higher-compute route |

The generator is readable and deterministic. Arm identity, route, step budget, and
prompt version are included in every event's arguments and therefore in its evidence
digest.

## Hypotheses

- **H1:** `balanced-4-step` reduces mean full effective cost by at least 25% versus
  `premium-8-step`, while its simultaneous one-sided harmful-regression upper bound
  remains at or below 5% and its standard assurance decision remains `SCALE`.
- **H2:** `cheap-2-step` fails the 5% harmful-regression bound despite a lower point
  cost.
- **H3:** `premium-12-step` fails the 25% cost-reduction rule despite a higher point
  acceptable rate.

H1 is falsified if any completeness, assurance, breakage, or cost condition fails.
H2 is falsified if the cheap arm clears every rule. H3 is falsified if the extended
arm clears every rule.

This release ships the protocol and synthetic results together. It is a frozen
executable protocol, not a timestamped preregistration or independent replication.

## Primary endpoints

For reference outcome `R_i` and candidate outcome `C_i` on paired task `i`:

```text
harmful_i = 1 when R_i = acceptable and C_i = unacceptable
quality delta_i = C_i - R_i
cost reduction = (mean reference effective cost - mean candidate effective cost)
                 / mean reference effective cost
```

Effective task cost includes execution, human review, remediation, and incident loss.
The primary breakage estimand is `mean(harmful_i)` over all paired tasks. It is the
absolute joint harmful-transition rate, not a failure rate conditioned on reference
success.

## Statistical method

For `m` planned candidates and target nominal familywise confidence `1 - alpha`,
each one-sided quality or cost endpoint uses `alpha / (2m)`.

The harmful-regression gate uses an exact one-sided Clopper-Pearson binomial upper
bound. When zero regressions are observed in `n` tasks, the bound is:

```text
1 - adjusted_alpha^(1 / n)
```

The cost gate uses a deterministic paired percentile bootstrap with the seed and
resample count stored in the plan. It is approximate and has Monte Carlo error, so
the plan must provide at least 20 expected resamples in the adjusted lower tail.
Economic totals use accurate floating-point summation. Derived endpoints are
canonicalized to 12 significant digits before threshold comparison and portable
serialization, preventing runtime-level noise from changing a decision or artifact.
Net paired quality delta and the empirical Pareto frontier are descriptive; the
selection decision is made only by the declared gates.

## Selection rule

A candidate is eligible only if:

1. all planned arm and task evidence is complete, with task-manifest digest,
   baseline, policy, and shared-model rates consistent across arms;
2. reference and candidate standard assurance decisions are `SCALE`;
3. the exact harmful-regression upper bound is no more than 5%; and
4. the paired cost-reduction lower bound is at least 25%.

The result is `ADOPT <arm>` for the lowest observed full-cost eligible candidate,
`HOLD` when no candidate is eligible, and `INCOMPLETE` when the experiment family or
required evidence is incomplete.

## Threats to validity

- Synthetic outcomes validate software semantics, not production prevalence.
- The percentile-bootstrap endpoint and target nominal confidence are approximate
  and include Monte Carlo error.
- Nonrandom arm allocation, route order, and provider drift can confound comparison.
- Prompt tuning on the frozen task set contaminates the benchmark.
- Duplicate or correlated tasks can overstate effective sample size.
- Missing failed runs create survivorship bias.
- Binary outcome labels can hide judge or human disagreement.
- Sparse incident loss and delayed remediation make full-cost estimates unstable.
- Aggregate non-inferiority can hide subgroup regressions.
- The paired bootstrap does not repair biased labels or incomplete cost attribution.

## External validation exit criterion

Keep the public result labeled synthetic until there is at least one permissioned,
redacted matched-task study from a real agent workflow with a frozen rubric,
three or more tested configurations, at least 100 paired task input digests, and an
independent reproduction.
