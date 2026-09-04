# How good is the instrument?

The scorecard for the auditor itself, every figure computed from the
frozen artifact that owns it, every experiment's own claim boundary
kept attached. Regenerate with `make evals`; each source is
byte-compared in `make reproduce`, so this page cannot drift from
the evidence it summarises.

| question | measurement | figure | what it does not establish |
|---|---|---:|---|
| Does a gutted gate survive? | substitution mutants (same id, version, coverage, route; enforcing nothing) | 487/510 killed by decision change; all 588 of 588 changed the contract digest, so no substitution is silent | synthetic conformance fixture, not harness hardness in the field |
| Does required coverage vanish with its gate? | 588 disable-one-gate comparisons | fixed contract: 0 false SCALE; dynamic coverage: 23 | conformance on synthetic bundles, not a production prevalence estimate |
| Does deleting raw evidence go unnoticed? | 9 evidence ablations | 4 refused outright; 5 ASSIST->SCALE transitions exposing two documented source-contract gaps | the gaps are boundary cases, recorded in the protocol, not a failure rate |
| Do the catalogued defects have discriminating probes? | 5 green defects, each re-run at its pinned pre-fix commit | every probe fails before the fix and passes after (`make green-defects`) | catalogued means found once; it is not a census of what remains |
| Does prospective search find anything? | pre-registered site list, committed before probing | 18 divergences probed, 3 real defects at 3 distinct sites | the count was published wrong twice (in the flattering direction both times); PROBE_RESULTS.md keeps that history |
| Does it work on data it did not produce? | 7 public datasets audited | 4 with verified findings, 3 clean bill | an arm name identifies runs in a dataset, never a measurement of a model |
| Do the published claims still verify? | 14 claims in the ledger | `make ledger` fails the build on any REFUTED or unpinned-UNVERIFIED claim | verification binds evidence digests, not the truth of the world |
| Does anything vanish on the way in? | every source unit in each of the four ingestion paths, cited by a decoded entity or named as excluded | 0 of 57 units orphaned; session-tree spend reconciles to the bundle with residual 0/0 tokens | the repository's own fixtures, which are small and were written here; it is conservation, not field-level fidelity |
| How good is the shipped judge (`kimi-judge@1`)? | agreement with hand-authored rubric-derived labels, 25 constructed cases | 95.8% agreement, 0% false-accept (eval-version 1) | not accuracy against production ground truth; constructed cases are easier than real ones, and the later 100% run is excluded here because the set was edited after seeing this judge |
| Are the frontier statistics right? | Clopper-Pearson bound against its closed form, plus distribution and monotonicity properties | exact to 9 decimal places across every tested trial size and alpha (`tests/test_frontier_statistics.py`) | the statistical kernel only; the frozen frontier study itself is synthetic and labelled so in its protocol |

## What is not measured

A scorecard that lists only what it measures reads as though that is
everything there is. These are the shipped capabilities with no
outcome figure above, named so the coverage claim is total, each
with what closing it would take:

- **`experiment.paired-budget-frontier@1`** - its statistical kernel is verified against closed forms (row above), but the frozen study is synthetic. Its protocol names the exit criterion: a permissioned matched-task study from a real workflow, three or more configurations, 100+ paired task digests, and an independent reproduction.
- **`kimi-analyst@1`** - no evaluation at all. It recommends fixes from a decided case, and nothing measures whether the recommendations are sound. Closing it means a labelled set of decided cases with expert remediations to score against - the same shape as the judge eval, which does not exist yet.
- **`renderer.frontier-json@1`** - byte-compared only. Closing it means a schema assertion over the emitted document, not one fixture diff.
- **`renderer.frontier-markdown@1`** - byte-compared only. Closing it means asserting the rendered comparison names every arm the case decided over.
- **`renderer.frontier-svg@1`** - byte-compared only. An SVG that renders misleadingly would pass.
- **`renderer.json@1`** - same as the markdown renderer; the JSON shape is asserted field by field in tests, but nothing measures whether it carries everything a consumer needs.
- **`renderer.markdown@1`** - byte-compared against checked-in fixtures, which proves the output has not changed, not that it is right. Closing it means a property test: every figure in the rendered case appears in the case object, and every breach appears in the prose.

## Reading it honestly

Several of these rows are conformance against synthetic fixtures
the harness itself generated - the mutation, coverage-drift and
ablation rows, and the ingestion row, whose fixtures were written
here. They establish that the contract behaves as specified, not
that the specification catches everything that matters.

The rows carrying field weight are the ones measured against
something this project did not author: real defects found by
pre-registered search in this codebase, real findings in
third-party data that reproduce from upstream, and a ledger where a
refuted claim is a permanent red build until retracted.

Two rows are deliberately the weaker number. The judge row publishes
95.8% rather than the later 100%, because the later eval set was
edited after observing the judge under test. The ablation row
records the instrument's two known blind spots. An eval suite that
cannot embarrass its subject is advertising.
