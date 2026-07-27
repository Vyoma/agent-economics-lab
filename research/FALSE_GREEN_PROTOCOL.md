# Protocol: Decision-Coverage Drift Under Required-Gate Disablement

## Question

Can a decision engine produce `SCALE` after a required gate is disabled if it
silently redefines complete coverage to match whichever gates remain enabled?

This protocol uses **decision-coverage drift** for that failure mode. It is a term
defined by this project, not an established name in the research literature.

## Claim boundary

This is an engine-conformance experiment. It changes check configuration, not
evidence. No trace, outcome, cost, baseline, or policy field is removed. The fixture
does not estimate how often production systems disable gates or experience false
approvals.

## Frozen scenario matrix

The benchmark evaluates all 96 combinations of:

| Factor | Values |
|---|---|
| Acceptable tasks out of 10 | 5, 8, 10 |
| Direct trace cost per task | USD 0.10, USD 1.50 |
| Human minutes on an unacceptable task | 0, 5 |
| Incident loss on the first task | USD 0, USD 10 |
| Baseline cost per attempt | USD 0, USD 4 |
| Baseline acceptable rate | 0.70, 0.95 |

Two additional constructed cases isolate the unit-economics and absolute-value
gates. No rows are discarded and no thresholds are tuned after observing results.

The fixed policy requires:

- acceptable rate at least 0.80;
- cost per acceptable outcome no more than USD 2;
- p95 task cost no more than USD 8;
- trace cost per task no more than USD 1;
- calls per task no more than 3;
- expected net value per attempt at least USD 0; and
- incremental net value versus the baseline at least USD 0.

## Required coverage and gate mapping

The fixed decision contract requires six dimensions:

| Coverage dimension | Sole default provider |
|---|---|
| `outcome_quality` | `gate.acceptable-rate@1` |
| `unit_economics` | `gate.unit-economics@1` |
| `tail_risk` | `gate.tail-cost@1` |
| `business_value` | `gate.net-value@1` |
| `counterfactual` | `gate.counterfactual@1` |
| `runtime_caps` | `gate.runtime-caps@1` |

## Intervention and architectures

For every scenario and coverage dimension:

1. Evaluate the complete check composition under the fixed six-dimension contract.
2. Disable exactly one required gate.
3. Evaluate the reduced composition while preserving the fixed contract.
4. Evaluate the same reduced composition after redefining required coverage as the
   union of coverage declared by the remaining enabled gates.
5. Record the three decisions, evidence digests, decision-contract digests, and
   complete-case economic metrics.

Let `C` be the complete checks, `R` the fixed required coverage, `g_d` the disabled
gate, and `coverage(C)` the union of coverage supplied by enabled gates.

- Fixed-contract architecture: `D(E, C - g_d, R)`.
- Dynamic-coverage architecture:
  `D(E, C - g_d, coverage(C - g_d))`.

The same evidence bundle `E` is used for all three evaluations.

## Outcomes

A false `SCALE` transition is:

```text
complete decision != SCALE
and
dynamic-coverage decision == SCALE
```

The primary descriptive rate is:

```text
false SCALE transitions
/ complete-case non-SCALE gate-disablement comparisons
```

Also report the count over all 588 disablements. These denominators are intervention
comparisons, not unique scenarios or samples from an enterprise population.

## Theorem-like conformance invariant

For a valid evidence bundle and successfully executing enabled checks:

```text
required coverage is not a subset of enabled gate coverage
implies
fixed-contract decision == INCOMPLETE
```

Because each disabled gate is the sole default provider of one required dimension,
the fixed-contract engine should return `INCOMPLETE` for all 588 disablements. This
is an enforced software property, not an empirical discovery.

## Falsification criteria

- The fixed-coverage invariant is falsified by any successful evaluation with
  missing required gate coverage that returns a decision other than `INCOMPLETE`.
- The unchanged-evidence claim is falsified if the full, fixed-contract, and
  dynamic-coverage evidence digests differ within any row.
- The frozen fixture result is falsified if regeneration does not produce exactly
  98 scenarios, 588 comparisons, and 23 false `SCALE` transitions.
- The per-dimension existence claim is falsified if any of the six disabled gates
  produces zero false `SCALE` transitions in this frozen matrix.
- No result here can establish production prevalence, universal sufficiency of the
  six dimensions, or the behavior of a named commercial system.

## Reproducibility

- Python 3.10+
- no runtime dependencies
- no randomness
- canonical scenario IDs and deterministic row order
- checked-in CSV, Markdown, and JSON results
- `make reproduce` verifies tests and the compatibility CSV
