# Data Card: Synthetic False-Green Scenario Matrix v1

## Purpose

Stress-test whether incomplete agent economic assurance can silently produce a
green deployment decision. The data is generated, not collected from users or
production systems.

## Composition

- 98 deterministic scenarios: 96 factorial cases and 2 gate-isolation cases.
- 10 synthetic tasks per scenario.
- 6 single-dimension ablations per scenario.
- 588 result rows.
- No prompts, model responses, personal data, customer identifiers, or secrets.

## Generation

`research/false_green_benchmark.py` creates the factorial matrix plus two isolation
cases documented in `research/README.md`. Every task contains one directly priced
model event and one business outcome. Values were selected to create separable
quality, unit-cost, tail-risk, business-value, counterfactual, and runtime-cap
boundary conditions.

## Labels

`false_green=true` means:

```text
complete decision != SCALE
and
unsafe available-only decision == SCALE
```

`prevented_by_coverage=true` additionally means the production engine returned
`INCOMPLETE` for the same ablation.

## Known limitations

- Factor values are hand-selected and are not sampled from an empirical
  distribution.
- Each task has one event, so multi-call topology is not represented.
- Cost allocation is exact by construction; missing or noisy billing is not modeled.
- Outcome labels are deterministic and have no annotator disagreement.
- Ablations are one-at-a-time and do not study interacting missing dimensions.
- Results must not be presented as production prevalence estimates.

## Intended uses

- Regression testing fail-safe coverage semantics.
- Teaching why removal of an assurance check is not equivalent to passing it.
- Generating hypotheses for evaluation on real, permissioned evidence cases.

## Out-of-scope uses

- Ranking vendors or models.
- Estimating financial savings.
- Setting enterprise policy thresholds.
- Making safety or compliance certifications.
