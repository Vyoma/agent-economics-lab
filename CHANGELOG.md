# Changelog

## 0.3.0 - 2026-07-27

- Correct the gate-disablement benchmark claim from evidence deletion to
  decision-coverage drift.
- Add a separate nine-case raw evidence-ablation benchmark with generated CSV and
  JSON artifacts.
- Bind every assurance result to a digest of ordered checks, versions, coverage,
  failure routes, and reducer semantics.
- Add deterministic invariant tests for missing coverage, gate monotonicity, check
  reordering, and optional-diagnostic noninterference.
- Report frontier breakage over all attempted tasks and, descriptively, among
  reference-acceptable tasks.
- Mark frontier cost ranking as post-selection exploratory and require held-out,
  nested, or independent confirmation for generalization.
- Bind each frontier arm to both its evidence and decision-contract digests.

## 0.2.0 - 2026-07-22

- Add the paired Economic Assurance Frontier.
- Add exact one-sided harmful-regression bounds.
- Add deterministic paired-bootstrap cost-reduction bounds.
- Add a Bonferroni-adjusted nominal confidence target across the frozen candidate
  family, with a minimum bootstrap-tail resolution rule.
- Fail closed on missing arms, mismatched task input digests or rubric versions,
  invalid numeric evidence, unknown event costs, baseline or policy drift,
  inconsistent shared-model rates, and insufficient paired sample size.
- Generate portable Markdown, JSON, and SVG frontier artifacts.
- Canonicalize economic aggregation, decision endpoints, and currency rendering for
  byte-stable artifacts across supported Python runtimes.
- Add a transparent 180-task, four-arm synthetic experiment, protocol, data card,
  tests, and contribution template.

## 0.1.0 - 2026-07-17

- Publish the dependency-free single-arm assurance engine.
- Add composable checks, canonical evidence digests, and bounded routing decisions.
- Add the original gate-disablement conformance benchmark, lessons, and modularity
  demo.
