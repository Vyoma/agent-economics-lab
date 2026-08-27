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

## What might be novel, and is not yet established

Two mechanisms were added later and carry landscape entries asserting what is
absent from the field. **Those entries were written by their author and have not
survived an independent refutation sweep.** Given that two earlier claims from the
same author were destroyed by such sweeps, one by a paper predating the work by
four months, the honest status of both is *unverified*.

- **Coverage closure over dynamic delegation** (`agent_economics/delegation.py`).
  A pinned contract assumes required evidence can be enumerated before the run.
  That stops holding when the agent spawns subagents at runtime. Rather than
  enumerate, require closure: each delegation is declared or it is unaccounted,
  and unaccounted delegation is missing coverage. Prior art in composition is
  deep: modular assurance cases, contract-based design, GSN away goals, dynamic
  safety cases. The unverified part is applying it to structure discovered at
  runtime as a check that refuses.

- **Attestation of the instruments that produced the evidence**
  (`agent_economics/provenance.py`). Contracts record which instrument produced
  the labels; nothing recorded whether it works. An unattested, weakly agreeing,
  or lapsed instrument forces `INCOMPLETE`. This is a metrology calibration
  certificate, expiry included, applied to eval instruments. Prior art is a
  century deep. The unverified part is *gating a deployment decision* on
  calibration state rather than reporting it.

If either sweep returns a subsuming citation, this section should shrink again
rather than be defended.

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

And the two unverified claims above are unverified. They should be read as
hypotheses until a sweep says otherwise.
