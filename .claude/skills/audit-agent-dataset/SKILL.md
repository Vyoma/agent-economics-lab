---
name: audit-agent-dataset
description: Audit a public agent-trajectory dataset for outcome-label defects before training or evaluating on it. Use when someone asks whether a dataset's labels can be trusted, wants to check a Hugging Face agent/trajectory dataset, is choosing between datasets, or is about to report a number computed from one. Triggers: "audit this dataset", "can I trust these labels", "check <hf-dataset>", "is this eval data any good".
---

# Auditing an agent-trajectory dataset

Datasets of agent runs ship outcome columns that read as adjudicated and
sometimes are not. This audits one before anyone trains or reports on it.

## Run it

```bash
python3 research/corpus/audit_any.py <owner/dataset> --rows 1000
```

No dependencies beyond the standard library. Python 3.10+. Reads a sample
by default and labels every figure with the denominator it used.

Options that matter: `--rows N` (more rows, slower, and the API rate-limits
sustained use), `--outcome COLUMN` when the proposed roles are wrong, and
`--json` for a machine-readable report.

## Checking a published figure without trusting the publisher

`research/reproduce_hle.py` is the pattern: one file, standard library only,
importing nothing from this package, that fetches the source, checks it
against a recorded hash, and recomputes a headline from scratch. Where a
result matters, write that file. Re-deriving with the same extractor that
produced the evidence proves reproducibility; sharing no code with it is what
makes a second answer independent.

## Read the output correctly

The report is a **census, not a finding**. Four things it produces, and
what each does and does not mean:

- **Outcome coverage**: how many rows carry a usable value in each column
  that looks like an outcome. A column populated on a fraction of rows
  means any rate computed from it has a denominator nobody stated. Strings
  where a verdict belongs (`"unknown"`) count as absent, not as data.
- **Duplicate work**: transcripts that hash identically. Training or
  evaluating on both copies counts the same work twice, and this is
  invisible without hashing.
- **Two outcome signals on the same rows**: the important one. When a
  dataset records two outcome-ish columns, their agreement is measurable
  rather than assumed. Below kappa 0.60 the signal would not clear the
  floor this package requires of an outcome instrument.
- **Positives at minimum effort**: successes recorded against no work.

## If it is worth filing

`python3 research/corpus/scaffold_entry.py <owner/dataset>` emits the
plumbing from the dataset's own schema: the freeze spec, a content-free
extractor, the findings record and the test skeleton. It refuses a dataset
whose licence is undeclared. What it emits is a proposal, guessed from column
names and value shapes, and is never worth committing unread.

Scaffold a spec in `freeze.SPECS` rather than a standalone freezer where the
rows API can serve the dataset. A SPECS slug gets an upstream verifier for
free, because `verify_corpus.VERIFIERS` registers every one of them. A
standalone freezer owes a verifier of its own, and that debt is how six
findings once ended up unverifiable while the run reported success.

## Before calling anything a finding

Two steps, both of which have killed real suspicions in this corpus:

1. **Check the base rate.** "Resolved runs with empty patches" looked like
   a defect until the empty rate turned out identical among failures. A
   difference that looks dramatic pooled has more than once been
   composition: stratify before believing it.
2. **Verify against upstream**, not against your own copy, otherwise a
   misread source agrees with itself.

Agreement between two columns is only a reliability measurement if they
are the same question asked twice. Two *different* questions diverging is
expected and means something else entirely. The tool cannot tell which,
and neither can a reader who does not check the dataset card.

## Statistical traps that have caught this project

Each of these produced a published figure that had to be corrected. They are
listed because they recur, not because they are exotic.

- **Pooling across a grouping variable.** If graders score candidates within
  a question, pool across questions and a grader scores well by detecting an
  easy question. One entry published 0.501 to 0.653 pooled; measured within
  question it is 0.491 to 0.581, and four of seven graders fell to
  no-better-than-random. Pooling flattered every one of them.
- **A point estimate against a threshold.** A quadratic-weighted kappa of
  0.625 was passed against a 0.60 floor at n=191. Its interval runs to 0.520.
  Grade from the interval or say the sample cannot decide.
- **Simultaneous claims at a single-comparison alpha.** Seven intervals at a
  nominal 95% each carry about a 30% chance that one is wrong. Correct at
  alpha / 2k.
- **A ratio whose denominator may be zero.** A pooled effect was reported as
  11.5x a stratified one. The stratified interval contains zero, so the ratio
  bootstraps to roughly [-110, +107]. Report the pair, never the ratio.
- **The wrong denominator.** 18 disagreements over 398 checked reads as 4.5%
  when only 20 of the 398 were comparable at all. It is 18 of 20.
- **Agreement without its base rate.** Raw agreement of 51.4% sounds
  informative until the majority-class baseline is 54.2%. Compare to the
  dumbest baseline, not to chance.
- **A constant has no correlation.** Cohen's kappa over rows where one column
  never varies returns roughly zero and means nothing.

## Then

To turn a census into a corpus entry, follow `docs/contributing-an-audit.md`:
content-free frozen evidence at a pinned revision, figures that recompute,
one guard proven non-vacuous by corruption, and the scope stated exactly.
Worked examples of every shape are in `research/corpus/`.

Findings already on the record, with the command that checks each, are in
`research/FINDINGS.md`. What eight of them say jointly is in
`research/PATTERNS.md`.
