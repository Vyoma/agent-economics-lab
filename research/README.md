# Research Artifacts

Agent Economics Lab separates its flagship paired experiment from lower-level engine
conformance so a software invariant is not mistaken for external empirical evidence.

## 1. Economic Assurance Frontier

**Question:** Which tested agent configuration is the lowest-cost candidate whose
uncertainty-bounded harmful-regression risk stays within a frozen policy?

The artifact aligns identical task input digests and rubric versions across a
reference and complete candidate
family, reconstructs full downstream cost, uses an exact one-sided upper confidence
bound on harmful regressions, and uses a paired lower confidence bound for cost
reduction. Missing tasks, arms, cost evidence, or assurance coverage return
`INCOMPLETE`.

- [Protocol](FRONTIER_PROTOCOL.md)
- [Data card](FRONTIER_DATA_CARD.md)
- [Generated decision](results/frontier/frontier.md)
- [Machine-readable result](results/frontier/frontier.json)
- [Cost-quality plot](results/frontier/frontier.svg)
- [Transparent fixture generator](../examples/compute-frontier/generate.py)

The checked-in 180-task study is synthetic. It validates the implementation and
selection rule, not production impact.

## 2. False-Green Engine Conformance

**Question:** When a required assurance dimension is removed, can a reducer that
silently redefines available evidence as complete manufacture a `SCALE` decision?

The deterministic stress test generates 96 factorial scenarios plus two boundary
cases, then runs six single-check ablations per scenario. It compares an unsafe
available-only reducer with the production fail-safe coverage behavior.

- [Protocol](PROTOCOL.md)
- [Data card](DATA_CARD.md)
- [Generated rows](results/false_green_results.csv)
- [Summary](results/SUMMARY.md)
- [Research note](NOTE.md)

This benchmark validates routing semantics under constructed perturbations. The
zero false-green safe result follows from the required-coverage invariant and should
not be described as an empirical ecosystem result.

## External validation gate

The next evidence milestone is one permissioned, redacted matched-task study from a
real agent workflow with:

- at least 100 paired task input fingerprints;
- at least three tested configurations;
- a frozen rubric and candidate family;
- complete failed and timed-out runs;
- explicit model, tool, labor, remediation, and incident costs;
- randomized or counterbalanced route order for causal interpretation; and
- an independent reproduction.
