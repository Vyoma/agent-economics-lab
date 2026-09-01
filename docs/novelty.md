# What is novel here

This page exists because the answer kept shrinking under scrutiny, and a claim
that shrinks quietly is worse than one that shrinks in public. Everything below
is stated at the width the evidence supports, with the citations that narrowed it.

The short version: **almost nothing here is a new idea. The assembly may be new,
and the discipline demonstrably works.** Those are different claims and they are
worth different amounts.

## What is not novel

Each of these was claimed at some point in this repository's history and each was
refuted by an adversarial prior-art sweep. They are listed rather than deleted
because the corrections are the useful part.

| Claim once made here | Refuted by |
|---|---|
| Mutation testing applied to the harness rather than the code | Di Guglielmo, Fummi, Pravadelli, *Vacuity analysis for property qualification by mutation of checkers*, DATE 2010. Black, Okun, Yesha, *Specification mutation*, ASE 2000. Synopsys Certitude, commercially. |
| A coverage metric for evals, analogous to code coverage | Chockler, Kupferman, Vardi built coverage metrics over specifications by mutation. Schuler and Zeller's checked coverage already answers "is this check load-bearing". |
| A question no evaluation framework reports | Maiorano, *Automated Self-Testing as a Quality Gate*, arXiv:2603.15676, March 2026: leave-one-out gate ablation for LLM release decisions, same domain, same mechanism, predating this package. |
| Incomplete evidence is not a pass | Assurance 2.0 evaluates over true / false / **unsupported** and propagates it. OMG SACM 2.1 has `needsSupport`. GSN has the undeveloped goal. A June 2026 post stated the thesis sentence verbatim, in this domain, before the first commit. |

One further correction belongs here because it is about a number rather than an
idea. The fixed-contract kill rate was published as a result and is analytically
constant: removing a dimension's only providers puts it in `required - enabled`,
so the engine refuses unconditionally. A sweep of all 252 non-empty subsets of the
shipped checks returns 1.0 every time. It is a regression test on an invariant,
not a measurement, and `research/results/mutation-score/` records it as
`detected_by_coverage_contract_by_construction`.

## What was claimed later, and what the sweeps left of it

Two mechanisms were added after the corrections above, each with a landscape
entry asserting what was absent from the field. Both entries were written by
their author. Both were then put to an independent refutation sweep, and both
came back **partially novel** with the framing gone and a narrow remainder.

### Coverage closure over dynamic delegation

Gone: "applied to structure discovered at runtime, in an agent delegation tree,
as a shipped check." Mishra and Sharad (arXiv:2606.09692, June 2026) name
**delegation closure** as a requirement and state the coverage-accounting
principle directly. Nian et al. (arXiv:2604.05485, April 2026) define an
accounted-fraction over delegation events with a magnitude-weighted gap burden,
arguing for the weighting in nearly the words used here. ISA 600 and ISA 705
settled the concept decades ago, SOC 2's carve-out method is the same
disjunction, and cost-weighted accounted-fraction is a published FinOps KPI.

Survives: **the denominator is the contract, not the ground truth.** The agent
work measures whether the record captured what happened. This measures whether
anyone undertook to assess what the record already shows. A run can be perfectly
instrumented, every subagent traced, and still score zero closure because none
was declared.

### Attestation of evidence-producing instruments

Gone: the metrology framing, and any suggestion the mechanism is new. Usami et
al. (arXiv:2606.15610, June 2026) already argue a judge should be reported as a
measurement instrument, with a metrological protocol. Eval Factsheets specified
the record fields in December 2025. Outside AI the whole loop is routine: PPAP
rejects a submission on Gauge R&R, CLIA makes a lab stop reporting an analyte
after two failed proficiency events and sets a literal calibration interval, and
ISO/IEC 17025 goes further by recalling results already issued. Closest of all,
DO-330 and ISO 26262-8 tool qualification is the same mechanism, and its
independent-verification exemption is the same carve-out.

Survives, narrowly: an age limit evaluated against a caller-supplied `as_of`
rather than the wall clock, and an `INCOMPLETE` outcome **distinct from FAIL**,
so unknown quality does not route to STOP. Tool qualification is one-time and
version-bound; a stochastic labeller changes without a version bump, so its
certificate has to lapse on a clock.

### What the sweeps found in the code, not the claims

Both found the code failing to match its own docstring, which matters more than
the citations:

- `provenance.py` was **orphaned**. Not exported, not imported anywhere, so
  "an unattested instrument forces INCOMPLETE" was not true of the shipped
  system at all. Now exported and reachable.
- Its docstring described a **sole-provider carve-out that did not exist**; the
  gate refused on any failing instrument. Now implemented.
- It compared raw agreement, Cohen's kappa and held-out accuracy against **one
  threshold**, which is a category error ILAC-G8 exists to prevent. Floors are
  now per method, and an unknown method is refused rather than graded on another
  method's scale.
- `delegation.py` promised accounting could be satisfied by "the delegated work
  carrying a contract of its own". **That disjunct was never implemented**, and
  it is what in-toto sublayouts already provide. The promise is removed.

## A fifth claim, tested and refuted

The advice above was taken immediately and did not help.

The next claim was that eval frameworks silently convert a failed check into a
pass, which would have made refusing obviously correct. A survey against primary
sources **refuted it**. No mainstream framework treats a broken check as a pass.
The one clear case, Guardrails AI defaulting to `NOOP`, was fixed by its
maintainers in v0.6.0. DeepEval's `ignore_errors`, which looked identical, marks
the item a failure and defaults to off.

What survives is narrower and true: the field has converged on *not a pass* and
has not converged on *how to report not a score*. Silent denominator shrinkage is
common, and an explicitly counted un-scored state is a minority position. **UK
AISI Inspect holds it clearly, reports it better than this package does, and
predates it.**

The survey also found this repository committing the worst version of the
behaviour it was surveying: a judge outage written into the outcomes file as
`acceptable: false`. Fixed, and recorded in docs/landscape.md rather than quietly
corrected.

Five claims, five narrowings. The rate has not improved with practice.

## A sixth sweep, and what it took

A September 2026 referee pass, run with instructions to reject, took the
economics lane whole: cost per confirmed outcome as an evaluation primitive is
*Cost-of-Pass* ([arXiv:2504.13359](https://arxiv.org/abs/2504.13359)) and
Kapoor et al. ([arXiv:2407.01502](https://arxiv.org/abs/2407.01502)), neither
of which five prior sweeps had surfaced — for a document claiming adversarial
sweeps, missing the two canonical citations of its own lane is the finding.
It also found the trajectory-audit lane populated (AgentLens, ATBench,
automated transcript scanners; see
[the landscape entry](landscape.md#auditing-benchmark-labels-and-trajectories-is-a-crowded-lane)).

Its verdict on what would earn a citation, recorded at full strength: for the
machinery, nothing — a researcher would cite in-toto, Inspect, ABC,
Cost-of-Pass, and the psychometrics line instead. Two narrow claims survive:
the documented defect record for the specific public datasets audited in
[research/CORPUS.md](../research/CORPUS.md), whose arm names circulate as
vendor model names while belonging to an individual upload; and the worked
demonstration that a check-source fingerprint is non-transitive through shared
helpers, as a cautionary footnote.

## The claim actually worth making

Not any single mechanism. Every one is borrowed:

| Mechanism | Borrowed from |
|---|---|
| Refuse when required coverage is missing | assurance cases |
| Bind the contract to check implementations | functional qualification |
| Account for delegated work | audit scope completeness |
| Calibrate the measuring instrument | metrology |

What has not been observed elsewhere is the **assembly**: one decision procedure
that refuses when any of the four fails, over a portable evidence artifact, as a
CI gate that exits non-zero and can be run by someone who did not build it.

That is a modest claim. It is also the only one that has survived every
adversarial pass so far, and it is stated at that width deliberately.

## What is demonstrated rather than claimed

This is not novelty and it is probably the more useful half.

## What survives adversarial review, and what does not

Two independent reviews of the claims below found the following, and all of it
was verified before being written down.

**Dead.** "Green defects are an unserved category" is false. Deriving a verdict
where no ground truth exists is the oracle problem (Barr et al., IEEE TSE 2015)
and the standard answer is metamorphic testing (Chen et al., 1998). This
repository already shipped three metamorphic relations in
`tests/test_stress_properties.py` while claiming in `GREEN_DEFECTS.md` that such
a defect is one "no single-case assertion can express". The relations existed;
they had only ever been applied to the decision kernel, never to `audit()`. That
claim was the sixth novelty claim made here without the adversarial prior-art
sweep this project's own process demands.

**Dead.** "Enumerate call sites that disagree about an optional argument, ranked
by how lopsided the disagreement is" is Engler et al., *Bugs as Deviant
Behavior* (SOSP 2001), including the ratio ranking. Arrived at independently,
which is not the same as arrived at first. Neighbouring work: differential
testing (McKeeman, 1998), N-version programming and its correlated-error
problem (Knight and Leveson, 1986).

**Close to tautological.** "The suite was green while the defect was live"
reduces to "the regression test did not exist yet", because every fix commit
here adds its test in the same commit. 5 of 5 is the expected result in any
repository.

**Wounded, badly.** No defect catalogued here was older than four days or ever
shipped in a tagged release. The last tag predates the modules most of them
live in. A project finding bugs in its own unreleased code is describing
ordinary development.

**Wounded.** The rule was derived from five defects and evaluated on the same
codebase. `research/HELD_OUT.md` runs it against six standard-library packages
and finds no defect in any of them. Converting a divergence into a defect took
domain knowledge every time it worked.

**Survives.** One author, hunting one class of error in an assurance package he
wrote, pre-registered a mechanically enumerated target list before probing it,
tabulated the misses, published the negative held-out result, and corrected the
count downward and then upward under review. Three real defects out of eighteen
candidates, one of them a fail-open on a documented input path. The technique is
old; the target is not. Applying deviance inference and metamorphic relations to
an assurance system's own honesty -- to the gates that decide whether to trust
an AI system, rather than to the system under test -- is a small delta, and it
is the one that holds.

**The durable part is not a technique at all.** It is that every number here is
gated by a test or a byte-comparison, every gate was broken on purpose to prove
it can fail, the pre-registration is a git object rather than a claim, and two
adversarial reviews were run and acted on rather than filed. That is copyable by
anyone, which disqualifies it as a moat and is the reason to write it down.

## The earlier framing, kept for the record

**Since writing that, it became the novelty.** The list below is no longer an
anecdote about diligence; it is a corpus with a measurable property. Five of
these defects have been pinned to the commit they were live at, and at every
one of those commits the entire test suite passed: 448, 448, 455, 462, 462
tests, all green, all with a real defect in the decision path.

Every bug benchmark I am aware of hands you a failing test and asks for a fix.
SWE-bench, Defects4J, BugsInPy and QuixBugs are all built that way; the failing
test is the task. Mutation testing inverts the roles but its mutants are
synthetic and the suite is the artefact being scored. A corpus of real defects
whose defining property is that the suite was *green* is a different object,
and `research/green_defects.py` builds it from git rather than from
reintroduction, so there is nothing synthetic in it.

What each entry carries that a defect list does not is the **discriminating
probe**: the concrete input that makes the wrong number visibly wrong. That is
the thing no test had. It is also the only technique on this page that ever
found anything, which is why the probes are committed and run rather than
described.

The honest limit is the population. Five defects, one repository, one author,
one day. A case series, not a rate. It cannot say how often this happens
elsewhere, and no sampling frame here would support the claim if it tried. It
establishes existence, mechanism, and a method.

On a single day of concentrated work, the mechanisms in this repository caught
eleven real defects, nine of them in the work of the person adding them:

1. The lint gate found `kimi_analyst.py` annotating its public API with names
   that had no module-level import, so `typing.get_type_hints()` raised
   `NameError` for any consumer introspecting the signatures.
2. The same gate found duplicate keys in a numeric allowlist, silently
   discarding one justification and leaving a published number documented for
   the wrong reason.
3. The Python floor guard explained a `make reproduce` failure that surfaced six
   frames deep inside an unrelated module as a mock error.
4. `test_pages_index` caught the published suite size drifting, twice.
5. `test_decision_kernel_is_inference_free` caught an inference vendor named in
   a comment inside the decision kernel.
6. The implementation fingerprint refused a check whose source could not be
   retrieved, rather than admitting it to a contract unfingerprinted.
7. An adversarial review of the audit found that a missing evidence instrument
   was a note while an unattested one was a ground. A bundle that declared what
   produced its labels was therefore unassessable until attested, and one that
   recorded nothing was assessable. The gate paid a team to delete the field.
   That is not a flattening at a boundary; it is a tool manufacturing the
   incentive to perform one, on the package's own honesty dimension.
8. With that fixed, the audit renderer still printed `$0.0000 of delegated
   spend` for a bundle built by `checks_only_bundle`, whose entire purpose is
   declaring that no rate card was supplied. The verdict was correct at every
   step: closure was 0%, the decision was INCOMPLETE. The refusal held in the
   logic and leaked at the last boundary, as a dollar figure to four decimal
   places, computed from event costs that nothing had ever priced.

9. Chasing that one to its root found the worst of the nine. Cost-weighted
   closure summed `direct_cost_usd or 0.0` rather than calling `TraceEvent.cost`,
   the resolver every other consumer uses, so any event priced by the rate card
   instead of an explicit figure weighed nothing. On a run with $100 of declared
   subagent spend and $18 of undeclared subagent spend, closure reported 100%
   and $0.00 unaccounted. That is a green verdict over exactly the condition the
   module exists to detect. Every adapter-built bundle sets an explicit cost,
   which is why it survived; the documented CSV evidence path leaves the column
   blank and prices from the rate card, and there it was live.

The eighth is the sharpest of the pair that reached a reader, because the API
that emitted the fabricated number is the one written specifically to refuse
fabricating economics. The ninth is the most serious outright: a fail-open on
the headline mechanism, caused by one `or 0.0` bypassing a resolver.

10. Fixing the ninth introduced the tenth, immediately. `delegation_closure_gate`
    called `assess_closure` without rates, though the view it receives carries
    them, so a bundle whose model events were rate-priced became unpriceable
    inside the gate while its rate card sat one attribute away. 462 tests did
    not cover a rate-priced delegation through the gate.
11. `TraceEvent.cost` answers 0.0 for any non-model event before consulting
    rates. That is right when a rate card exists to have priced the tool call
    and an unsupported claim when none does: which tools are billed is exactly
    what a rate card says. An undeclared subagent whose descendants were all
    `WebSearch` reported `$0.00` unaccounted.

The tenth is the useful one to sit with. It was introduced by the fix for the
ninth, in the same file, within the hour, by someone who had just written the
lesson about this exact class of error. The suite was green across it. What
caught it was constructing the input that would make the number wrong, which is
the only technique on this list that found anything.

Both were found by asking what a number would look like if it were wrong,
rather than by a test. Being right about the verdict is not the same as being
honest about the number, and the places these come apart are a renderer and an
arithmetic default, neither of which any gate inspects.

Separately, and most to the point: CI was red for five consecutive commits
because a generator walked git history at verification time, which works on a
full local clone and fails on every shallow CI checkout. Each of those commits
was verified locally and pushed without the run being read. That is precisely the
failure this repository argues about, committed by its author, five times, while
writing about it.

None of that is a research contribution. It is evidence that the discipline holds
under load, applied by someone actively trying not to trip it and tripping it
anyway.

## Limits

The composition claim rests on absence of evidence, which is weaker than evidence
of absence. No systematic search establishes that no product does all four.

The headline experiment runs on a synthetic fixture. It measures a property of a
specific eval design, not a production prevalence rate.

Closure measures declaration, not quality: a declared subagent is accounted for
even if nobody examined what it did. Attestation characterises the instrument,
not the individual label: a judge in calibration can still be wrong about a
particular task.

The two later claims have now been swept and both were narrowed; what is left of
them is stated above and in docs/landscape.md, with the citations that did the
narrowing. Neither should be described as novel without that context.

Four separate novelty claims have been made in this repository. Three were
destroyed outright and the fourth pair survived only in narrow, technical
remainders. Anyone tempted to make a fifth should assume the same outcome and
write it that way from the start.
