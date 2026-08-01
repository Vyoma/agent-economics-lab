# Economic Assurance Frontier

**Decision: HOLD**

No tested candidate is cleared, and the reference configuration is not cleared for scaling. This report makes no deployment recommendation.

## Frozen experiment plan

- Experiment: `public-swebench-opus-vs-haiku-20-paired-v1`
- Reference arm: `reference-haiku`
- Plan digest: `14a18582de5f520c43a611e820d3d2596a26cdac060ceaf85375978122cba421`
- Task manifest: `task-manifest.json`
- Frozen task-manifest digest: `a7cd01c2784a6faa780d6f8ca68c84343b31910d85a4ea5feee99d938d9e383a`
- Paired-task minimum: 20
- Maximum harmful-regression risk: 5.0%
- Minimum full-cost reduction: 0.0%
- Target nominal familywise confidence: 95.0%
- Paired bootstrap resamples: 10000
- Bootstrap seed: 20260728
- Expected adjusted-tail draws: 250.0
- Portable numeric precision: 12 significant digits

## Tested configurations

| Arm | Assurance | N | Acceptable | Mean full cost | Cost / acceptable | Net value / attempt | Pareto |
|---|---|---:|---:|---:|---:|---:|---|
| `candidate-opus` | STOP | 20 | 70.0% | $0.42 | $0.60 | $-0.42 | frontier |
| `reference-haiku` | STOP | 20 | 55.0% | $0.27 | $0.49 | $-0.27 | frontier |

## Paired evidence against the reference

| Candidate | Harmful transitions | Absolute rate (H/N) | Absolute UCB (governing) | Conditional rate (H/R+) | Quality delta | Cost reduction | Cost reduction LCB | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `candidate-opus` | 1 | 1/20 (5.0%) | 24.9% | 1/11 (9.1%) | +15.0% | -56.9% | -93.6% | no |

### Rejection reasons

- `candidate-opus`:
  - reference assurance decision is STOP, not SCALE
  - candidate assurance decision is STOP, not SCALE
  - breakage upper bound 24.873% exceeds 5.000%
  - cost-reduction lower bound -93.647% is below 0.000%

## Selection interpretation

The selection rule chooses the minimum observed mean full cost among eligible candidates. The candidate family is used both to establish eligibility and to rank eligible arms. The multiplicity-adjusted endpoints are designed to control simultaneous threshold clearance under the stated method, but they do not debias the selected arm's observed cost or prove that its rank will persist in a new population.

Treat the selected arm's cost magnitude and rank as post-selection exploratory evidence for generalization. A production claim requires a held-out confirmation set, nested selection and evaluation, or an independent frozen replication.

## Statistical method

Exact one-sided Clopper-Pearson breakage bound plus deterministic paired percentile bootstrap for cost reduction; a Bonferroni-adjusted nominal familywise confidence target across planned quality and cost tests. Derived decision endpoints are canonicalized to twelve significant digits.

The governing breakage estimand is the absolute paired-population rate of tasks accepted by the reference and rejected by the candidate, with all matched tasks in the denominator. The conditional rate uses only reference-acceptable tasks in the denominator and is descriptive; it does not govern v1 eligibility. Reporting both prevents a low reference acceptance rate from making the absolute rate look sufficient by itself. The exact upper bound prevents a small sample with zero observed regressions from appearing certain. Paired resampling preserves the task-level relationship between reference and candidate costs. The bootstrap endpoint and its nominal confidence target are approximate and include Monte Carlo error.

## Evidence and decision manifests

- `candidate-opus` evidence: `2d063279479ebeff05654482a77ad53eb6076441315e462b1881e0c56e5a4394`
  - decision contract: `e7faae0cb2b0fb62c5341412c16c8e7930142eaf86cd8e8568b0dfad72c3baab`
- `reference-haiku` evidence: `c88375512518ad44a03ff98b4eb44b8184825aaaeacdcd02eb0e9ce0f8497a4d`
  - decision contract: `e7faae0cb2b0fb62c5341412c16c8e7930142eaf86cd8e8568b0dfad72c3baab`

## Claim boundary

This report identifies the lowest-cost tested configuration that satisfies the declared rule on this frozen matched dataset. It does not establish a causal effect unless route assignment was randomized or counterbalanced. It does not validate the outcome rubric, prove production generalization, or infer an exact breakpoint between untested configurations. Missing arms, task fingerprints, rubric versions, cost evidence, or assurance coverage fail closed. The selected arm's observed cost and rank are not unbiased confirmatory estimates for a new population.
