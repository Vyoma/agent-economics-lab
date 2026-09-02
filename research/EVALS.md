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
| Does it work on data it did not produce? | 6 public datasets audited | 3 with verified findings, 3 clean bill | an arm name identifies runs in a dataset, never a measurement of a model |
| Do the published claims still verify? | 14 claims in the ledger | `make ledger` fails the build on any REFUTED or unpinned-UNVERIFIED claim | verification binds evidence digests, not the truth of the world |

## Reading it honestly

Three of these rows are conformance against synthetic fixtures the
harness itself generated; they establish that the contract behaves
as specified, not that the specification catches everything that
matters. The rows that carry field weight are the last three: real
defects found by pre-registered search in this codebase, real
findings in third-party data that reproduce from upstream, and a
ledger where a refuted claim is a permanent red build until
retracted. The evidence-ablation row records the instrument's two
known blind spots in its own scorecard, because an eval suite that
cannot embarrass its subject is advertising.
