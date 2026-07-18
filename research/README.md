# False-Green Assurance Benchmark

## Research question

When required economic evidence is removed from an agent-readiness review, can the
remaining checks produce `SCALE` even though the complete assurance case would not?

## Falsifiable hypotheses

- **H1:** At least one single-dimension ablation will produce a false-green `SCALE`
  on the controlled scenario matrix.
- **H2:** Required-coverage enforcement will convert every such false green to
  `INCOMPLETE`.
- **H3:** Removing counterfactual coverage will expose scenarios where the agent is
  positive in isolation but economically worse than the named alternative.

H1 is falsified if no ablation changes a complete non-`SCALE` decision to `SCALE`.
H2 is falsified if the production engine returns `SCALE` after any required
dimension is removed. H3 is falsified if counterfactual removal produces no false
greens in the scenario matrix.

## Run it

```bash
make benchmark
make reproduce
```

The benchmark has no network, model, or third-party dependency. It deterministically
generates 96 factorial ten-task scenarios plus two gate-isolation boundary cases,
then evaluates six single-dimension ablations per scenario.

## Experimental factors

| Factor | Controlled values |
|---|---|
| Acceptable tasks out of 10 | 5, 8, 10 |
| Trace cost per task | $0.10, $1.50 |
| Human minutes per failed task | 0, 5 |
| Single-task tail loss | $0, $10 |
| Baseline cost per attempt | $0, $4 |
| Baseline acceptable rate | 70%, 95% |

Two additional boundary cases isolate distributed human cost and low absolute
business value so the unit-economics and business-value gates can each be tested
without a second gate masking the result.

Each scenario is evaluated with complete coverage, then with one of these checks
removed: outcome quality, unit economics, tail risk, business value,
counterfactual, or runtime caps.

Two reducers are compared:

1. **Unsafe available-only:** silently treats whichever checks remain as complete.
2. **Fail-safe coverage:** returns `INCOMPLETE` when a required dimension is absent.

The full generated rows are in [`results/false_green_results.csv`](results/false_green_results.csv).
The benchmark card is in [`results/SUMMARY.md`](results/SUMMARY.md).

## Interpretation boundary

This experiment validates software semantics under controlled perturbations. It
does not establish:

- the prevalence of incomplete evidence in enterprises;
- the causal effect of an assurance process on production incidents;
- that the sample thresholds are appropriate for a real domain; or
- that six dimensions exhaust agent economic or safety assurance.

Those questions require redacted or independently collected workload cases. The
synthetic benchmark is useful because every decision reversal is attributable to a
known removed dimension.
