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

On a single day of concentrated work, the mechanisms in this repository caught
six real defects, four of them in the work of the person adding them:

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
