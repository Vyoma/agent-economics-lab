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

## Read the output correctly

The report is a **census, not a finding**. Four things it produces, and
what each does and does not mean:

- **Outcome coverage** — how many rows carry a usable value in each column
  that looks like an outcome. A column populated on a fraction of rows
  means any rate computed from it has a denominator nobody stated. Strings
  where a verdict belongs (`"unknown"`) count as absent, not as data.
- **Duplicate work** — transcripts that hash identically. Training or
  evaluating on both copies counts the same work twice, and this is
  invisible without hashing.
- **Two outcome signals on the same rows** — the important one. When a
  dataset records two outcome-ish columns, their agreement is measurable
  rather than assumed. Below kappa 0.60 the signal would not clear the
  floor this package requires of an outcome instrument.
- **Positives at minimum effort** — successes recorded against no work.

## Before calling anything a finding

Two steps, both of which have killed real suspicions in this corpus:

1. **Check the base rate.** "Resolved runs with empty patches" looked like
   a defect until the empty rate turned out identical among failures. A
   difference that looks dramatic pooled has more than once been
   composition: stratify before believing it.
2. **Verify against upstream**, not against your own copy — otherwise a
   misread source agrees with itself.

Agreement between two columns is only a reliability measurement if they
are the same question asked twice. Two *different* questions diverging is
expected and means something else entirely. The tool cannot tell which,
and neither can a reader who does not check the dataset card.

## Then

To turn a census into a corpus entry, follow `docs/contributing-an-audit.md`:
content-free frozen evidence at a pinned revision, figures that recompute,
one guard proven non-vacuous by corruption, and the scope stated exactly.
Worked examples of every shape are in `research/corpus/`.

Findings already on the record, with the command that checks each, are in
`research/FINDINGS.md`. What eight of them say jointly is in
`research/PATTERNS.md`.
