# Contributing an audit

The corpus grows one dataset at a time, and nothing about the discipline
requires the author of this repository to be the one holding the instrument.
This page is the whole contract: an entry that satisfies it gets merged no
matter who submits it, and an entry that does not gets returned no matter who
submits it, including us. Every rule below exists because this project broke
it once and published the scar.

## Start with the scaffold

```bash
python3 research/corpus/audit_any.py <owner/dataset>      # is there anything here?
python3 research/corpus/scaffold_entry.py <owner/dataset> # then the plumbing
```

The first prints a census: coverage, duplicate work, and agreement wherever a
dataset carries two outcome signals. It is deliberately not a finding.

The second emits the boilerplate this contract requires, read from the
dataset's own schema: the freeze spec, an extractor, the findings record and
the test skeleton. It refuses a dataset whose licence is undeclared, and what
it emits is a proposal in the same sense the census is: guessed from column
names and value shapes, worth editing, never worth committing unread.

Everything it emits is the part that does not require judgement. What it
leaves you is the row count, the extractor's fields, the base rate, the
verification pass, the statement, the action, the scope, and one guard proven
to fire. That is the entry; the rest was typing.

A spec in `SPECS` gets an upstream verifier for free, because
`verify_corpus.VERIFIERS` registers every SPECS slug. A standalone freezer
does not, and owes one.

## What qualifies

A publicly downloadable dataset of agent trajectories or run records, pinned
to a named revision, whose license permits publishing derived metadata. The
dataset does not need to look defective; a clean bill is a result, recorded
with the same care as a defect, and an auditor that only ever finds problems
is indistinguishable from one that manufactures them.

## Start with a census, not a blank file

```bash
python3 research/corpus/audit_any.py <owner/dataset> --rows 1000
```

Points the corpus's own checks at any dataset served by the Hugging Face
rows API: outcome coverage, duplicate transcripts, positives at minimum
effort, and agreement between two outcome signals where a dataset carries
them. It proposes column roles rather than deciding them, and prints a
census rather than findings, because the steps below are what turn one
into the other. Directory-structured datasets need a bespoke freezer;
`research/corpus/freeze_cogym.py` is the smallest worked example.

## The freeze: content-free, complete, refusing

Add a spec to [research/corpus/freeze.py](../research/corpus/freeze.py) and
commit the frozen output. The rules are mechanical and each is enforced by a
test or by the freeze itself:

- **Content-free.** Frozen rows carry hashes, byte lengths, labels,
  identifiers, and small scalars, never messages, patches, logs, prompts, or
  problem text. The content-sweep test fails the build on a forbidden key.
  If a check needs content, the check re-fetches at the pinned revision and
  reduces to content-free facts before anything is committed
  ([patch_check.py](../research/corpus/patch_check.py) is the pattern).
- **Complete.** Freeze every row of every split you audit, never a sample.
  A partial arm is recorded as not-obtained, not silently included: a rate
  computed over a partial population is a different number wearing the same
  name.
- **Refusing.** A truncated cell aborts the freeze: a hash of a truncated
  cell is a hash of nothing. An expected row count is declared up front and
  a mismatch is an error.
- **Pinned.** Record the dataset revision and license in the spec. Hashes
  must be re-derivable from upstream at that revision by anyone.

## The verifier: not optional

Add an entry to `VERIFIERS` in
[research/corpus/verify_corpus.py](../research/corpus/verify_corpus.py). It
takes the slug and a sample size and re-derives rows from upstream, calling
your freezer's own extractor on freshly fetched bytes rather than
reimplementing the extraction, so what is proven is that the same source and
the same code give the committed file. Check every fetched byte against the
hash the freeze recorded. A row that cannot be fetched is a failure of the
check, never a silent skip.

A frozen document with no verifier fails `make verify-corpus`. This is the
newest rule in this contract and it exists because the project broke it:
verification covered only the datasets frozen through one transport and
skipped the rest, so six of fourteen published findings could not be checked
against source by anyone, while the run printed the count of what it had
checked as though it were the count of what exists.

## The checks: base rates before accusations

Run the shared family in [research/corpus/corpus_report.py](../research/corpus/corpus_report.py):
outcome census, cross-check agreement where the dataset carries two outcome
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
the frozen evidence, no hand-typed numbers. `make corpus` byte-compares the
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
