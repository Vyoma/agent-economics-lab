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

**The wrong statistic, and it flattered.** The seven-grader result was
published as AUC pooled over all 32,450 responses. Those graders exist to
pick the right response among fifty candidates to one question, so the unit
is the question and the statistic is how well a grader ranks inside one;
pooling lets a grader score by noticing a question is easy. Every published
figure moved when this was corrected, and every one moved down: the range
was 0.501 to 0.653 and is 0.491 to 0.581 within question, one grader crossed
below chance, and four of seven now have intervals containing 0.5. The
pooled column is kept beside the corrected one because the gap between them
is the size of the effect that was being mistaken for grader skill
([research/CORPUS.md](../research/CORPUS.md)).

**"Chance" for a number that was not chance.** A Cohen's kappa of 0.062 was
published as "indistinguishable from guessing". Chance is zero, and the 95%
interval, clustered over 5,870 instances, is [0.047, 0.077]. The signal is
reliably non-zero and far too small to act on, which are different
statements, and the published one overstated in the direction of the
argument being made. The figure that actually decides anything was missing
entirely: raw agreement is 51.4% against a majority-class baseline of 54.2%,
so consulting the proxy costs 2.9 points, 95% CI [0.9, 5.0].

**A ratio whose denominator could not carry one.** The contamination finding
said the pooled effect was larger than the stratified one by a factor of
11.5. Neither figure had an interval. Bootstrapped, the pooled difference is
+0.209 [+0.173, +0.241] and the stratified is +0.018 [-0.019, +0.055], which
contains zero, so the ratio between them runs from about -110 to +107. It
was arithmetic on two point estimates presented as a quantity. Withdrawing
it made the finding stronger: within benchmarks the effect does not shrink,
it disappears.

**A per-item rate read as an aggregate one.** The README used the label's
8.8% per-task self-disagreement as though it were the uncertainty on an
arm's resolution rate, concluding that small gaps between models could not
be resolved. Those are different quantities and the second is about three
times smaller: a coin-split of 44 disagreements moves a 500-task rate with a
standard deviation of 0.7 points, so the unresolvable band is roughly 2.6
points. Computing it surfaced the better fact, which the paragraph had
missed: those 44 disagreements split 22 each way, so both twin arms report
an identical 72.8%. The per-task label is unreliable and the aggregate is
not.

**A category omitted because it was empty.** The fragility table printed
ROBUST 43 and BRITTLE 55, which sum to 98 and imply there is no third band.
FRAGILE is 0 of 98, and the emptiness is the informative part: nothing is
mildly sensitive, so the flips come from one dominant assumption rather than
graded sensitivity, and 56.1% should not be read as a continuous score.

**One factor, three renderings.** The PostTrainBench overstatement appeared
as `12x`, "eleven times" and `11.5` in three places: two render sites
rounding with `:.0f`, and a hardcoded word that stopped tracking the
computation ([research/corpus/corpus_report.py](../research/corpus/corpus_report.py)).

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

**A claim called flat without a test.** An acceptance rate was reported as
"flat across every source stratum, so it is not one problem set's quirk",
which is an eyeball over a 4.6-point range with a conclusion drawn from the
word. A chi-square test of homogeneity gives X2 = 6.72, df = 6, p = 0.35 at
n = 55,808. The claim survives and now states what a failure to reject
supports, which is consistency with one common rate rather than proof of
one.

**Seven simultaneous intervals at a single-comparison alpha.** The grader
intervals were published at a nominal 95% each. Seven such claims are a
family and the chance at least one is wrong is about 30%. This package
already applies a Bonferroni correction to a family that size in its
frontier code and was not applying it here. Corrected at alpha / 2k, which
widens every interval; the same four still contain 0.5, so the finding
survives the stricter test rather than depending on the looser one.

## Tools that reported confidently and falsely

**A verifier that cried wolf twice before working.** The upstream
corpus verifier's first version reported schema drift as disagreement: a
field added to an extractor after a freeze made ten rows "re-derive" a
value the evidence never claimed to hold. Its second version keyed rows by
an identifier this corpus contains 4,209 collisions of - documented in the
entry the author had written - kept one row per collision, and reported ten
mismatches that were entirely its own. A verifier that cries wolf is worse
than none ([research/corpus/verify_corpus.py](../research/corpus/verify_corpus.py)).

**A fail-open in the package's own public surface.** `decide` evaluates and
audits as one act, withholding a SCALE the audit has grounds against. It was
not exported. `evaluate_bundle` was, so a library consumer reaching for the
obvious name got the engine alone, and on a bundle shipped in this
repository the engine returns SCALE where the gate returns INCOMPLETE on
unattested instruments. The reassuring answer was the default one, in the
package built to argue that it should not be
([tests/test_entry_points.py](../tests/test_entry_points.py)).

**A verifier reporting the count of what it had checked as the count of what
exists.** The corpus verifier covered the datasets frozen through one
transport and silently skipped the rest. Six of fourteen published findings
therefore rested on evidence no reader could re-derive from source,
including the two the front page leans on hardest, while the run printed
"70 rows checked across 7 datasets" and exited zero. Every frozen document
now has a verifier and one without fails the run: 10,100 rows across 11 of
11. This is the same failure the module's own docstring was written to
prevent, committed by the module.

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
