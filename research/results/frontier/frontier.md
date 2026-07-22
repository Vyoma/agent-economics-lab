# Economic Assurance Frontier

**Decision: ADOPT `balanced-4-step`**

This is the lowest-cost tested candidate that satisfied the predeclared breakage-risk, cost-reduction, evidence-completeness, and assurance rules.

## Frozen experiment plan

- Experiment: `synthetic-support-budget-frontier-v1`
- Reference arm: `premium-8-step`
- Plan digest: `fdef79a28661ec29d92439f64cbc37dadd32f2362b5d13af55f7da96b5608660`
- Task manifest: `task-manifest.json`
- Frozen task-manifest digest: `8ab1d32aff8ff1d42fa3d7fecff28bc36548dd1c9905b972a0ed701c874298d4`
- Paired-task minimum: 150
- Maximum harmful-regression risk: 5.0%
- Minimum full-cost reduction: 25.0%
- Target nominal familywise confidence: 95.0%
- Paired bootstrap resamples: 5000
- Bootstrap seed: 20260722
- Expected adjusted-tail draws: 41.7

## Tested configurations

| Arm | Assurance | N | Acceptable | Mean full cost | Cost / acceptable | Net value / attempt | Pareto |
|---|---|---:|---:|---:|---:|---:|---|
| `balanced-4-step` | SCALE | 180 | 95.6% | $1.00 | $1.05 | $6.64 | frontier |
| `cheap-2-step` | SCALE | 180 | 89.4% | $0.93 | $1.04 | $6.23 | frontier |
| `premium-12-step` | SCALE | 180 | 96.7% | $2.19 | $2.27 | $5.54 | frontier |
| `premium-8-step` | SCALE | 180 | 95.0% | $1.66 | $1.75 | $5.94 | dominated |

## Paired evidence against the reference

| Candidate | Harmful regressions | Breakage UCB | Quality delta | Cost reduction | Cost reduction LCB | Eligible |
|---|---:|---:|---:|---:|---:|---|
| `balanced-4-step` | 1/180 | 3.7% | +0.6% | 39.9% | 32.0% | yes |
| `cheap-2-step` | 12/180 | 12.5% | -5.6% | 44.4% | 29.9% | no |
| `premium-12-step` | 0/180 | 2.6% | +1.7% | -31.5% | -38.9% | no |

### Rejection reasons

- `cheap-2-step`:
  - breakage upper bound 12.477% exceeds 5.000%
- `premium-12-step`:
  - cost-reduction lower bound -38.944% is below 25.000%

## Statistical method

Exact one-sided Clopper-Pearson breakage bound plus deterministic paired percentile bootstrap for cost reduction; a Bonferroni-adjusted nominal familywise confidence target across planned quality and cost tests.

The breakage estimand is the absolute paired-population rate of tasks accepted by the reference and rejected by the candidate, with all matched tasks in the denominator. The exact upper bound prevents a small sample with zero observed regressions from appearing certain. Paired resampling preserves the task-level relationship between reference and candidate costs. The bootstrap endpoint and its nominal confidence target are approximate and include Monte Carlo error.

## Evidence manifests

- `balanced-4-step`: `32fa0e4a4953b298352d58e0849cc2ffc18636d67093a77ce0fae0673896638f`
- `cheap-2-step`: `25259104ba610bae17322c6b40d1b301362c52c806c796466ce3e46adfb7ff7a`
- `premium-12-step`: `8316e57badbc4fcc1cbab1233ba66873237a549f6f1df583bee1901a0204cb05`
- `premium-8-step`: `91526aecd73578ba43d2bc1cf4bfdb9cedcb26841967b2899dddfe1348fb9756`

## Claim boundary

This report identifies the lowest-cost tested configuration that satisfies the declared rule on this frozen matched dataset. It does not establish a causal effect unless route assignment was randomized or counterbalanced. It does not validate the outcome rubric, prove production generalization, or infer an exact breakpoint between untested configurations. Missing arms, task fingerprints, rubric versions, cost evidence, or assurance coverage fail closed.
