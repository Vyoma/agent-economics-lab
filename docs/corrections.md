# Every time this project was wrong

A tool that decides whether to trust an AI system is only worth the
calibration of the people building it. This page is the evidence for that
calibration, or against it: the published numbers that were wrong, the
guards that guarded nothing, the tools that reported confidently and
falsely, and the claims withdrawn once someone looked properly.

It is deliberately not a list of bugs fixed. A bug found by a failing test
is the system working. What is recorded here is narrower and more
uncomfortable: cases where this project believed something, said so in
public or in a passing test, and was wrong.

Each entry names where the correction lives, so none of this has to be
taken on trust.

## Published numbers that were wrong

**A test-count precision nobody needed, corrected three times.** The front
page quoted an exact suite size. It went stale on every added test, failed
CI twice, and produced a merge conflict when two branches each corrected
it. The first two fixes automated the update; only the third asked whether
the precision was load-bearing. It states a floor now
([docs/index.md](index.md), guard in `tests/test_pages_index.py`).

**A spread published two ways.** The twin-arm finding quoted a 21-point
spread across scored arms in the findings index and 20.6 in the two
documents that compute it. 21 is the naive-rate spread; 20.6 the
confirmed-rate one. The index had promised every figure recomputes, and
this one had no guard, which is exactly how it drifted. The guard written
to fix it was itself wrong on the first attempt, counting resolved rows
over a scored denominator, and says so in its own comment
([tests/test_findings.py](../tests/test_findings.py)).

**One factor, three renderings.** The PostTrainBench overstatement appeared
as `12x`, "eleven times" and `11.5` in three places: two render sites
rounding with `:.0f`, and a hardcoded word that stopped tracking the
computation ([research/corpus/audit.py](../research/corpus/audit.py)).

**Twenty contradictions across twenty-six documents.** A cross-document
audit found stale adapter inventories, a four-versus-seven disagreement
about how many grounds withhold a verdict, a manifest printed in a doc that
did not match the one its own command runs, and a closing paragraph in the
page about retracted claims whose tally of retracted claims was itself
stale. Three of the twenty were in *generated, byte-compared* pages -
generation guarantees consistency with the generator, not correctness of
it.

## Guards that guarded nothing

**A scorecard filing the headline finding as a clean bill.** The
instrument scorecard counted clean datasets by matching the word "clean" in
the corpus prose. The row reading "clean labels; its recorded
generated-test signal measures kappa 0.062" matched, so the sharpest result
in the project was filed as a clean bill, in a generated page that
byte-compares and therefore shipped green. Counted from the findings
registry's own `kind` field now
([research/evals.py](../research/evals.py)).

**A property test that passed with the defect restored.** An audit gate's
property test was written, shipped, and only later run against deliberately
broken code - where it passed, because the bundles it generated had no
`label_source` for the gate to check. Every guard added since is required
to be watched failing before it is trusted, and several below were caught
by that rule.

**A guard that required a wrong number.** A test asserted a test count
above 2000, enforcing a double-counted figure the README described as an
error.

**Non-vacuity checks that were themselves wrong, three times.** Stripping
`breaches` from a case changed nothing visible, because the failing checks
carry the same text - the renderer was right and the test's premise was
wrong. Dropping `arms[-1]` from a frontier case changed nothing, because
that is the reference arm and the plan prints it separately. Dropping one
model call orphaned nothing, because record citations are redundant. All
three are kept as tests that assert the redundancy deliberately, rather
than deleted for being inconvenient.

## Tools that reported confidently and falsely

**A verifier that cried wolf twice before working.** The upstream
corpus verifier's first version reported schema drift as disagreement: a
field added to an extractor after a freeze made ten rows "re-derive" a
value the evidence never claimed to hold. Its second version keyed rows by
an identifier this corpus contains 4,209 collisions of - documented in the
entry the author had written - kept one row per collision, and reported ten
mismatches that were entirely its own. A verifier that cries wolf is worse
than none ([research/corpus/verify_corpus.py](../research/corpus/verify_corpus.py)).

**A liveness check reported as a progress check.** A twenty-hour dataset
freeze was reported as "advancing, not wedged" on the evidence of
accumulating CPU and an open socket. Both were true. Neither answered
whether it would finish: it held every fetched row in memory, had reached
2GB against the 12GB it needed, and had driven the machine into heavy swap.
It could never have completed.

**A process check that returned a confident zero.** Two freezes were
declared dead on the output of `pgrep -c`, which is not a count flag on
this platform: it errored, a shell fallback printed `0`, and the false
negative was acted on by launching duplicates of jobs that were running
fine. A broken check returning a clean negative is the exact failure this
project exists to name.

**A fidelity harness with its own failure mode.** The tool written to
detect silently dropped records shipped with a non-recursive glob that
missed a subdirectory, undercounting the source and therefore *hiding*
orphans. Caught by reading its first output
([research/adapter_fidelity.py](../research/adapter_fidelity.py)).

## Claims withdrawn

**Six novelty claims, all narrowed or refuted.** Each was published, then
destroyed or reduced by an adversarial prior-art sweep, with the citations
that did it recorded beside the claim. The sixth shipped without the sweep
the project's own process requires, and a review found the omission
immediately ([docs/novelty.md](novelty.md)).

**A prospective-search count published wrong twice, both times
flatteringly.** The number of real defects found by the pre-registered
search moved 3, then 2, then 3, and an accompanying rate was stated as
"roughly one site in eight" - a figure derivable from none of the
underlying numbers. The history is kept on the page rather than tidied
([research/PROBE_RESULTS.md](../research/PROBE_RESULTS.md)).

**A claim refuted by a file in the same test suite.** An earlier version of
the green-defect catalogue asserted a defect was one "no single-case
assertion can express", while three metamorphic relations that express
exactly that class sat in `tests/test_stress_properties.py`
([research/GREEN_DEFECTS.md](../research/GREEN_DEFECTS.md)).

## Suspicions killed before they were published

These never became findings, which is the point. Each looked like a
result, and each died against its own base rate.

**"Resolved runs with empty patches."** In a 76,002-row dataset, resolved
rows with no patch looked like outcomes untethered from work. The patch
field is empty on 27.1% of all rows and 27.5% of resolved ones: a property
of the column, not of the label.

**"Contamination pays twenty points."** Runs an integrity judge flagged
scored +0.209 accuracy above clean ones. Holding benchmark fixed, +0.018 -
contamination concentrates on the benchmark with the second-highest clean
baseline, so pooling credits that benchmark's easiness to cheating. The
published entry leads with the correction rather than the headline
([research/CORPUS.md](../research/CORPUS.md)).

**"Satisfaction untethered from work done."** Very short human-agent
sessions rated highly would have suggested ratings disconnected from
effort. There are four such sessions. Four sessions establish nothing.

## What this page does not do

It does not make the project reliable. A list of caught errors is evidence
about the catching, not about what remains uncaught, and the honest
reading of a page this long is that a system this size has more of these
than anyone has found. The catalogued defects in
[GREEN_DEFECTS.md](../research/GREEN_DEFECTS.md) carry the same caveat:
catalogued means found once, not a census of what remains.

The claim is narrower. Every entry above was found by a mechanism this
repository ships - a guard proven non-vacuous, a base-rate check, a
cross-document audit, an adversarial sweep - rather than by a user hitting
it in production. That is the property worth having, and it is the only one
this page establishes.
