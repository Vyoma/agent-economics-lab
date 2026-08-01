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
- [Transparent fixture generator](../examples/compute-frontier/generate.py)

The checked-in 180-task study is synthetic. It validates the implementation and
selection rule, not production impact.

## 2. Decision-Coverage Drift Conformance

**Question:** When a required gate is disabled, can an engine that silently shrinks
required coverage to match the remaining gates manufacture a `SCALE` decision?

The deterministic stress test generates 96 factorial scenarios plus two boundary
cases, then runs six single-gate disablements per scenario. It compares a
dynamic-coverage engine with the fixed-contract coverage behavior. The evidence
bundle is unchanged in every comparison.

- [Protocol](FALSE_GREEN_PROTOCOL.md)
- [Data card](FALSE_GREEN_DATA_CARD.md)
- [Generated rows](results/decision-coverage-drift/results.csv)
- [Summary](results/SUMMARY.md)
- [Structured summary](results/decision-coverage-drift/summary.json)

This benchmark validates routing semantics under constructed perturbations. The
zero fixed-contract result follows from the required-coverage invariant and should
not be described as an empirical ecosystem result or a missing-data experiment.
Because gate removal is the one operator the invariant catches by construction,
this experiment cannot speak to how hard the harness is to fool. Experiment 3
exists for that question.

## 3. Harness Mutation Score

**Question:** Under which mutation operators does the fixed contract actually
outperform a dynamic one?

Two operators are injected across the same 98-scenario matrix, with equivalent
mutants excluded from the denominator. `REMOVAL` deletes a required gate.
`SUBSTITUTION` replaces one with a permissive implementation that keeps the same
ID, version, declared coverage, and failure route.

Removal is killed 510/510 by the fixed contract, which is forced by the coverage
invariant. Substitution is killed 487/510 by *both* engines: identical scores,
because required coverage still appears satisfied. The per-check implementation
fingerprint in the decision-contract digest changes for 588/588 substitutions and
is the only mechanism that surfaces them.

- [Summary](results/mutation-score/summary.md)
- [Structured summary](results/mutation-score/summary.json)
- [Executable](../mutation_score.py)

The honest reading: the fixed contract removes one failure mode by construction
and leaves the more realistic one to digest review.

## 4. Decision Sensitivity Sweep

**Question:** How much of a verdict is the agent, and how much is the economic
assumptions behind it?

A 48-cell grid of incident-loss and remediation-cost assumptions is swept per
scenario, plus six perturbations of the baseline acceptable rate. 43 of 98
scenarios never change verdict; 55 change in three or more cells. A 50% baseline
error flips the counterfactual gate in 25 of 98.

- [Summary](results/sensitivity/summary.md)
- [Structured summary](results/sensitivity/summary.json)
- [Executable](../sensitivity_sweep.py)

Flip counts characterize this matrix under this policy. They are not a production
prevalence estimate, and they are a reason to publish a fragility index beside
any verdict.

## 5. Raw Evidence Ablation

**Question:** What happens when an outcome record, cost field, policy threshold,
manifest row, baseline, or timed-out event is actually deleted while the decision
contract remains fixed?

The nine-case boundary fixture produces four operational refusals and five
`ASSIST` to `SCALE` transitions. The five transitions expose current source-contract
limits: optional cost fields can be interpreted as zero, and a deleted attempt is
undetectable without a source-completeness contract.

- [Protocol](EVIDENCE_ABLATION_PROTOCOL.md)
- [Data card](EVIDENCE_ABLATION_DATA_CARD.md)
- [Generated rows](results/evidence-ablation/results.csv)
- [Structured summary](results/evidence-ablation/summary.json)

These are deliberately constructed conformance cases, not a measured enterprise
failure rate.

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
