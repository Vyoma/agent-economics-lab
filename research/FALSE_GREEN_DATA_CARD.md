# Data Card: Synthetic Decision-Coverage Drift Matrix v1

## Purpose

Test two decision architectures under required-gate disablement:

- a fixed-contract engine that preserves the original coverage requirements; and
- a dynamic-coverage engine that silently shrinks those requirements to match the
  remaining enabled gates.

The data is generated, not collected from users or production systems.

## What is manipulated

The intervention disables one required gate at a time. It does not remove evidence.
The trace events, outcome records, direct costs, rate card, baseline, policy, and
evidence digest are unchanged across the complete, fixed-contract, and
dynamic-coverage evaluations.

This distinction is fundamental. The matrix tests decision-contract drift, not
ordinary missing-data behavior.

## Composition

- 98 deterministic scenarios: 96 factorial cases and 2 gate-isolation cases.
- 10 synthetic tasks per scenario.
- 6 single required-gate disablements per scenario.
- 588 result rows.
- 510 comparisons whose complete-case decision is not `SCALE`.
- No prompts, model responses, personal data, customer identifiers, or secrets.

## Generation

`false_green.py` creates the matrix documented in
`FALSE_GREEN_PROTOCOL.md`. Every task contains one directly priced model event and
one deterministic business outcome. Values were hand-selected to create separable
quality, unit-cost, tail-risk, business-value, counterfactual, and runtime-cap
boundary conditions.

## Result fields

`false_scale_transition=true` means:

```text
complete decision != SCALE
and
dynamic-coverage decision == SCALE
```

`fixed_contract_refused=true` additionally means the fixed-contract engine returned
`INCOMPLETE` for that transition.

Each row records:

- the disabled gate and its coverage dimension;
- full, fixed-contract, and dynamic-coverage evidence digests;
- decision-contract digests for all three engine configurations;
- all three decisions;
- the two transition labels; and
- complete-case economic metrics used by the gates.

## Observed fixture results

- 23 false `SCALE` transitions under dynamic coverage.
- 4.5% of the 510 complete-case non-`SCALE` intervention comparisons.
- 3.9% of all 588 intervention comparisons.
- 588 of 588 fixed-contract evaluations returned `INCOMPLETE`.
- 0 false `SCALE` transitions under the fixed contract.

The zero result follows from the fixed-coverage invariant. Neither percentage is a
production prevalence estimate.

## Known limitations

- Factor values are constructed and are not sampled from an empirical distribution.
- Each task has one event, so multi-call topology is not represented.
- Cost allocation is exact by construction; missing or noisy billing is not modeled.
- Outcome labels are deterministic and have no annotator disagreement.
- Disablements are one at a time and do not study interacting gate failures.
- The dynamic-coverage comparator is a deliberately weak architecture, not a named
  vendor implementation.
- The experiment does not test removed outcomes, baselines, task-manifest entries,
  failed runs, policy thresholds, or cost fields.

## Intended uses

- Regression testing fixed-coverage refusal semantics.
- Teaching that all enabled checks passing is not equivalent to all required checks
  passing.
- Generating hypotheses for evaluation on real, permissioned cases.

## Out-of-scope uses

- Estimating enterprise or vendor failure prevalence.
- Claiming that `INCOMPLETE` eliminates other false approvals.
- Ranking vendors or models.
- Estimating financial savings.
- Setting enterprise policy thresholds.
- Making safety or compliance certifications.
