# Protocol: False-Green Decisions Under Evidence Ablation

## Fixed analysis

The benchmark evaluates every scenario in the fixed Cartesian matrix. No rows are
discarded and no thresholds are tuned after observing results.

For each scenario:

1. Evaluate the complete default assurance composition.
2. Remove exactly one required gate.
3. Evaluate the reduced composition with coverage enforcement enabled.
4. Evaluate the same reduced composition with the missing dimension silently
   removed from the required set. This is the unsafe comparator.
5. Record all three decisions and the complete-case metrics.

## Primary metric

```text
unsafe false-green rate =
  count(full != SCALE and unsafe_available_only == SCALE)
  / count(full != SCALE)
```

The denominator is computed over ablation comparisons, not unique scenarios,
because each removed assurance dimension is a separate intervention.

## Safety invariant

```text
count(full != SCALE and fail_safe == SCALE) == 0
```

Any nonzero result is a release-blocking regression.

## Secondary analysis

Report false-green counts separately for outcome quality, unit economics, tail
risk, business value, counterfactual, and runtime-cap ablations.

## Reproducibility

- Python 3.10+
- no runtime dependencies
- no randomness
- canonical scenario IDs
- deterministic row order
- checked-in generated results
- `make reproduce` verifies code, tests, lessons, and result equality
