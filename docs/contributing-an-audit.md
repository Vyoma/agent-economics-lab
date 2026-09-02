# Contributing an audit

The corpus grows one dataset at a time, and nothing about the discipline
requires the author of this repository to be the one holding the instrument.
This page is the whole contract: an entry that satisfies it gets merged no
matter who submits it, and an entry that does not gets returned no matter who
submits it, including us. Every rule below exists because this project broke
it once and published the scar.

## What qualifies

A publicly downloadable dataset of agent trajectories or run records, pinned
to a named revision, whose license permits publishing derived metadata. The
dataset does not need to look defective; a clean bill is a result, recorded
with the same care as a defect, and an auditor that only ever finds problems
is indistinguishable from one that manufactures them.

## The freeze: content-free, complete, refusing

Add a spec to [research/corpus/freeze.py](../research/corpus/freeze.py) and
commit the frozen output. The rules are mechanical and each is enforced by a
test or by the freeze itself:

- **Content-free.** Frozen rows carry hashes, byte lengths, labels,
  identifiers, and small scalars — never messages, patches, logs, prompts, or
  problem text. The content-sweep test fails the build on a forbidden key.
  If a check needs content, the check re-fetches at the pinned revision and
  reduces to content-free facts before anything is committed
  ([patch_check.py](../research/corpus/patch_check.py) is the pattern).
- **Complete.** Freeze every row of every split you audit, never a sample.
  A partial arm is recorded as not-obtained, not silently included: a rate
  computed over a partial population is a different number wearing the same
  name.
- **Refusing.** A truncated cell aborts the freeze — a hash of a truncated
  cell is a hash of nothing. An expected row count is declared up front and
  a mismatch is an error.
- **Pinned.** Record the dataset revision and license in the spec. Hashes
  must be re-derivable from upstream at that revision by anyone.

## The checks: base rates before accusations

Run the shared family in [research/corpus/audit.py](../research/corpus/audit.py)
— outcome census, cross-check agreement where the dataset carries two outcome
signals, duplicate-transcript groups with label agreement, degenerate
positives. Then, before any suspicion becomes a finding:

- **It must survive its base rate.** "Resolved rows with empty patches"
  died here when empty patches turned out equally common among failures.
  The first draft of the re-adjudicator reported 186 disagreements that were
  all its own parser's blindness. Compute the boring denominator first.
- **It must survive a verification pass.** An accusatory claim gets a
  targeted re-fetch: deterministic (hash-ranked) selection, every fetched
  byte checked against the frozen hash, an unfetchable row counted as a
  failure of the check, never a silent skip.
- **Its scope must be stated exactly.** Say what the finding is not:
  whether it touches the labels, the training signal, any model, or only an
  auxiliary column. The SWE-smith entry is the template.

## The rendering: numbers that recompute

Every published figure is computed by the entry's section in `audit.py` from
the frozen evidence — no hand-typed numbers. `make corpus` byte-compares the
committed [research/CORPUS.md](../research/CORPUS.md) against a fresh render.
Each figure gets a recomputation test, and at least one guard must be proven
non-vacuous by corrupting the evidence and watching it fire; this repository
shipped a guard that passed with the defect deliberately restored, which is
why that proof is now mandatory.

## The submission

One pull request: the spec, the frozen JSON, any verification sidecar and its
script, the `audit.py` section, and the tests. The entry names its auditor.
Review checks exactly the rules above, and CI enforces most of them. Priority
belongs to the entry's date in the ledger, so a finding you verified today is
yours today even if the write-up lands next week.
