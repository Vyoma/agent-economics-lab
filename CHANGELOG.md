# Changelog

## 0.7.0 - 2026-07-29

- Add a separate `claude-code-tree` converter for parent plus persisted subagent
  transcripts.
- Attribute child and recursively nested calls to the root economic task that
  owns the delegation.
- Verify and remove duplicated fork bootstrap envelopes before cost accounting.
- Bind every parent transcript, child transcript, and child metadata file into
  the frozen source inventory.
- Add cross-file dependency edges from delegation through child execution.
- Resolve cyclic child graphs through deterministic component boundaries while
  preserving the diagnostic cycle finding.
- Select the complete cumulative usage variant from streamed message fragments,
  exclude only explicit zero-usage API-error placeholders, and retain
  zero-compute child transcripts without inventing events.
- Hash mixed root prompt structures in memory without decoding or emitting their
  content.
- Refuse missing file pairs, unknown delegation links, duplicate identities,
  spawn cycles, inconsistent depth, source drift, and unexpanded delegation.
- Extend the CLI, package capabilities, composite GitHub Action, and Python
  matrix reproduction path.
- Add a content-marked conformance tree with byte-reproducible bundle and report.

## 0.6.0 - 2026-07-28

- Add one contract-first OpenTelemetry GenAI adapter pinned to Semantic
  Conventions 1.43.0 and GenAI commit `799e014`.
- Prove the shared mapper against content-safe Langfuse and Arize OpenInference
  fixtures with pinned upstream provenance.
- Add `otel-genai` to the CLI and composite GitHub Action.
- Introduce a shared strict conversion-contract boundary for both offline
  adapters.
- Add typed dependency edges to canonical evidence and bind present edges into
  the evidence digest.
- Populate real edges from Claude Code `parentUuid` and OpenTelemetry
  `parentSpanId`.
- Add a diagnostic-only directed-cycle check that cannot alter routing.
- Consolidate publication material under `docs/writing/` and repair navigation.
- Regenerate every checked artifact under the expanded decision contract.

## 0.5.0 - 2026-07-28

- Add a composite GitHub Action for normalized-bundle, CSV-evidence, and offline
  Claude Code conversion modes.
- Preserve the CLI decision contract in CI: only `SCALE` passes, while
  `INCOMPLETE`, `ASSIST`, and `STOP` fail with exit codes 2, 3, and 4.
- Reject partial or conflicting Action input modes as `INCOMPLETE`.
- Upsert the generated Markdown assurance report on pull requests when the caller
  explicitly provides a GitHub token.
- Expose decision, exit-code, and report-path outputs for downstream workflows.
- Dogfood all three input modes against the checked-in support, Claude Code, and
  public SWE-bench examples.
- Add a single scope and priority document for the GitHub Action, OpenTelemetry
  adapter, typed dependency edges, and documentation consolidation.

## 0.4.0 - 2026-07-28

- Add a contract-first Claude Code JSONL converter and separate `convert` CLI
  workflow.
- Deduplicate streamed assistant fragments into unique model calls and join tool
  uses to exactly one result through the parent-UUID graph.
- Require explicit outcomes, pricing tiers, cache rates, client/server tool cost,
  baseline, and policy instead of inferring economic semantics from the transcript.
- Freeze raw and content-redacted source inventories and embed a conversion receipt
  that binds source, conversion contract, and canonical evidence digests.
- Remove prompt, response, thinking, result, argument-key, argument-value, and raw
  source-ID content from normalized output.
- Reject stale inventories, incomplete tool calls, sidechains, billing-context
  drift, and unexpanded delegation that may hide nested model spend.
- Add byte-reproducible template, bundle, report, and adversarial adapter tests.
- Keep the checked-in Claude Code conformance fixture explicitly synthetic and
  separate from claims based on public or permissioned evidence.
- Add a non-synthetic, content-redacted public case from 40 MIT-licensed
  mini-SWE-agent trajectories on 20 paired SWE-bench Verified tasks.
- Publish both a `STOP` AssuranceCase and a `HOLD` paired frontier comparing Opus
  4.6 with Haiku 4.5 using observed outcomes, estimated spend, and API-call counts.

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
