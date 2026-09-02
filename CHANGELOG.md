# Changelog

## 0.9.0 - 2026-09-02

The SCALE semantics changed, the instrument was pointed at the wild, and the
engine got a measured envelope.

### Decision contract

- **Breaking:** a `SCALE` the audit refuses is returned as `INCOMPLETE`
  carrying the audit's grounds, on every shipped surface (`evaluate --ci`,
  the GitHub Action, `decide()`). The only reachable green is one the audit
  has no grounds against: outcome instrument attested (validity methods
  only; test-retest measures repeatability and cannot clear the floor),
  delegation accounted, spend priced. `ASSIST`, `STOP`, and `INCOMPLETE`
  pass through untouched.
- `evaluate` grew `--attestations`, `--as-of`, `--independently-verified`,
  and `--omit-check`; the Action grew the matching inputs.
- Check resolution moved to a registry (id -> builder), so gates that need
  evidence context can be named on every surface, including claims.

### Found in the wild

- `research/CORPUS.md`: a registry of public agent-trajectory datasets
  audited under one discipline, with content-free frozen evidence. Four
  entries at 0.9.0: tarsur385 (one arm's 100% never confirmed by its own
  cross-check; one duplicated arm pair, labels 91.2% self-consistent),
  CoderForge (clean: rewards re-derive from raw logs), SWE-smith (patch
  column not row-aligned; 2,255 duplicate rows in one split; labels clean
  everywhere), JetBrains (`resolved` populated on 0 of 1,785 rows).
- `make verify-upstream`: frozen rows spot-check against the upstream
  dataset at its pinned revision, one fetch per row, findings' rows always
  included.
- `docs/contributing-an-audit.md`: the contract under which third-party
  entries merge.

### Scale

- Measured envelope at `docs/at-scale.md`: linear, ~9,600 events/s on the
  full decision path, 979 MiB peak at one million events; CI ratio guard.
- Fixed while measuring: recursive cycle detection died at ~1,000-deep
  chains with the error swallowed as "could not run" (iterative now, proven
  at 50,000); the evidence was hashed fifteen times per decision (once
  now); `dataclasses.asdict` serialization replaced by direct field access
  with a byte-identity guard.

## 0.8.0 - 2026-07-31

Tightens the decision contract, adds a judge eval, and expands the test suite to
stress, property, statistical, and regression coverage.

### Decision contract

- **Breaking:** the contract is now `assurance.decision-contract@2`. Every check
  entry records an `implementation_digest`, a SHA-256 over the normalized source of
  its `run` function. Declared identity alone cannot distinguish an enforcing gate
  from a same-named, same-coverage gate that no longer enforces anything, so the
  fingerprint is what makes a permissive substitution visible. All published
  contract digests change and every checked-in artifact is regenerated.
- Checks whose source cannot be retrieved (built-ins, C functions,
  `functools.partial`, interactively defined callables) are refused rather than
  admitted with an unbindable implementation.
- Summed costs route through a guarded reducer. Individually valid finite values can
  produce an unrepresentable total, and a fail-closed engine must answer that with an
  explained refusal rather than a stdlib `OverflowError`. `percentile` validates its
  probability argument.

### Harness measurement

- `mutation_score.py` injects two operators and excludes equivalent mutants.
  Gate **removal** is detected by the coverage contract by construction, so a
  perfect score against it is arithmetic rather than evidence. Gate
  **substitution**, where a replacement keeps its ID, version, coverage, and failure
  route while enforcing nothing, is the operator that discriminates: the fixed
  contract scores 95.5% against it, identical to a dynamic engine. The
  implementation fingerprint is what surfaces those cases.
- `sensitivity_sweep.py` reports decision robustness across a 48-cell grid of
  economic assumptions plus baseline perturbations. 55 of 98 scenarios change verdict
  under plausible assumptions, and a 50% baseline error flips 25 counterfactual
  gates. The grid now shares one fixture construction with the drift benchmark so the
  identity cell reproduces the unperturbed verdict exactly.
- `false_green.build_evidence` accepts economic overrides. Coverage-drift artifacts
  remain byte-identical.
- `mutation-score`, `sensitivity`, and `completion-vs-verdict` are wired into
  `make reproduce` with pinned, byte-verified artifacts.
- `completion_vs_verdict.py` replaces `real_trace_verdict.py`, which described the
  synthetic Claude Code fixture as a captured session.

### Inference: single provider, enforced

- `agent_economics/kimi_client.py` is the package's only inference egress. Provider,
  model, request contract, and retry policy are declared once, ending duplication
  that had already let the two integrations drift to different reasoning depths.
- `tests/test_inference_routing.py` enforces the boundary: no module may open its own
  connection, declare a second endpoint, import another provider's SDK, reference
  another provider's host, or reach the client from an undeclared module. A separate
  assertion keeps the deterministic kernel free of inference, since a model call
  there would void byte-reproducible verdicts.
- `agent-economics capabilities` reports the active provider, model, reasoning
  effort, and egress path.

### Kimi request contract

Pinned to the documented `kimi-k3` contract:

- Verdicts are forced through a strict JSON schema derived from the rubric. Moonshot
  Flavored JSON Schema accepts only `type`, `enum`, and `required` for validation and
  rejects range keywords with HTTP 400, so bounds are stated in each field's
  `description` and enforced by `_validate_verdict` after parsing.
  `assert_mfjs_compatible` raises locally before a request goes out.
- `max_completion_tokens` replaces `max_tokens`, at 32768 for the judge and 65536 for
  the analyst. Reasoning shares the budget, so it must fit `reasoning_effort=max`.
- Sampling parameters are omitted because K3 fixes them server-side.
- Request timeouts follow the reasoning depth: 60s low, 180s high, 420s max. A
  chat-sized timeout turns every deep-reasoning call into repeated timed-out attempts.
- The invariant system prompt is sent first so automatic context caching keeps a
  stable prefix.
- Retries cover `408/409/425/429/5xx`. Everything else raises `KimiRequestError` and
  is not caught by `judge`: a rejected schema or credential is a defect in the
  request, not a verdict about the task, so the run aborts without writing outcomes.
- All three Moonshot credential systems are reachable. Keys and base URLs are not
  interchangeable across the international Open Platform, the China Open Platform,
  and Kimi Code, and Kimi Code uses a different path as well as a different host.
  `MOONSHOT_BASE_URL` selects the system and is validated against `KIMI_HOSTS`, so it
  cannot redirect inference to another provider.
- `401` responses name the system that was called, tabulate all three with their
  consoles, and give the override to reach each. Keys are stripped of surrounding
  whitespace and quotes, and templated or too-short values are refused locally
  instead of costing a network round trip.
- `check_kimi_auth.py` and `make kimi-doctor` report key shape and per-system HTTP
  status without printing the key.
- The judge audit sidecar records `model_id`, `reasoning_effort`, and
  `output_contract` alongside every per-criterion score.

### Judge eval

- `research/eval/judge-eval-set.json` holds 25 cases across eight categories, with
  expected labels that follow from the rubric's own weights. A test asserts that
  arithmetic against the rubric file: accuracy plus policy clears the threshold, so a
  blunt correct answer must pass, while policy plus tone cannot, so a factually wrong
  answer cannot.
- `make kimi-eval` reports agreement, per-class precision and recall, a confusion
  matrix, a per-category breakdown, and a **false-accept rate**, the error that
  inflates `acceptable_rate` and can turn a `STOP` into a `SCALE`. Judge errors are
  counted apart from the confusion matrix so an outage cannot read as strictness.
- `--limit`, `--only`, and `--repeat` support smoke runs, single-case checks, and
  verdict-stability measurement. Full verdicts are saved and rationales printed for
  any disagreement.
- Measured: `kimi-k3` at `reasoning_effort=max` scores 95.8% agreement on eval
  version 1 and 100% on version 3, both with a 0% false-accept rate and no errors.
  Version 1 is the stronger evidence: version 3 was partly informed by the model
  under test, and two of its verdicts sit 0.02 from the threshold. Every recorded run
  is pinned to the eval version it measured, and a test requires those caveats to stay
  attached to a perfect score.
- Judge calibration: `kimi-k3` requires caveats about permissions and recoverability
  before endorsing destructive operations, and scores comparable non-destructive
  product-specific answers well above threshold. Supply product ground truth in the
  `context` column or true statements can be scored as unsupported.

### Label sensitivity

On identical traces, rates, baseline, policy, and decision-contract digest, swapping
hand-authored labels for `kimi-k3` labels moved the support fixture from `ASSIST` to
`STOP`, took the acceptable rate from 75.0% to 37.5%, moved cost per acceptable
outcome from $3.50 to $14.76, and flipped incremental net value from $2.77 to
$-3.13. Neither label set is validated ground truth; the finding is the leverage the
label source holds over the verdict.

### Tests

- `tests/test_stress_properties.py`: fail-closed behavior on hostile economics,
  derived-metric consistency across 200 randomized scenarios, determinism under event
  permutation, monotonicity of cost and quality, and 1000-task scale.
- `tests/test_frontier_statistics.py`: the exact Clopper-Pearson bound checked
  against its closed form at zero observations, monotonicity, interval tightening,
  and paired-bootstrap pairing preservation.
- `tests/test_regressions.py`: one test per invariant the release establishes.
- `tests/test_harness_reports.py`, `tests/test_inference_routing.py`, and
  `tests/test_kimi_eval.py` cover the harness artifacts, the provider boundary, and
  the eval scoring math.

### Documentation

- `docs/landscape.md` records fail-closed required coverage as prior art: GitHub
  required status checks, Kubernetes `failurePolicy: Fail`, in-toto layouts, SLSA,
  OPA, DO-178C, and ISO 26262. The mechanism is borrowed; the economic dimensions it
  is applied to are the contribution.
- `README.md` adds a plain-language summary, quotes literal `make demo` output with a
  test asserting every quoted line matches the engine, and surfaces the sensitivity
  and mutation-score results rather than burying them.
- `docs/kimi-integration.md` documents the request contract, the three credential
  systems, the eval, and the calibration finding.
- `assets/demo.gif` is removed. A recording cannot be re-verified when the code
  changes, and its claim-boundary text no longer matched the engine.
- Stale links to `frontier.svg` and `research/NOTE.md` are removed.

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
