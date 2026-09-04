# What the audits say together

Each entry in [the corpus](CORPUS.md) is a statement about one
dataset. These are the three things the entries support jointly and
none supports alone. Every figure is computed from the same frozen
evidence the entries use; `make patterns` regenerates this page and
the build fails if it drifts.

## Outcome instruments, side by side

This package refuses a green decision unless the instrument that
produced the outcome labels is attested at kappa 0.60
or better. Two datasets in this corpus happen to record two outcome
signals on the same rows, which makes the instrument measurable
rather than assumed. Nobody had put them next to each other.

| instrument | measured against | statistic | value | n | clears 0.60? |
|---|---|---|---:|---:|---|
| model-generated tests | adjudicated hidden-test outcome | Cohen's kappa | 0.062 | 31,389 | **no** |
| one person's artifact rating | the same person's satisfaction rating | quadratic-weighted kappa | 0.625 | 191 | yes |

The two are not the same kind of measurement and the table should
not be read as a ranking. The first compares an automated signal
against an adjudicated one and is a validity measurement. The
second compares two questions put to the same person, so it is a
spread between constructs, not a reliability figure - the human was
never asked the same thing twice.

What survives that caveat is worth stating plainly. The cheap
automated oracle the field reaches for when there is no answer key
lands at chance. And the human judgement everything else is
validated against, asked two adjacent questions about one session,
spreads by more than the margin most published instrument
comparisons are arguing over. Anything reported as agreement with
human labels inherits whichever question was asked, and none of
these datasets record which.

## The outcome column is often not an outcome

Five entries carry a field a consumer would read as the outcome.
How much of it is populated varies by more than an order of
magnitude, and no dataset announces the difference:

| dataset | field | rows without a usable value |
|---|---|---:|
| `agent-trajectories` | `resolved` | 1,785 of 1,785 (100.0%) |
| `cogym-real-trajectories` | `communicationRating` | 178 of 228 (78.1%) |
| `PostTrainBench-Trajectories` | `accuracy` | 260 of 1,842 (14.1%) |
| `SWE-smith-trajectories` | `resolved` | 0 of 76,002 (0.0%) |
| `SWE-agent-trajectories` | `target` | 0 of 80,036 (0.0%) |

Two of the five are complete. One is empty. The pattern that
matters for a reader is not the average but the range: a rate
computed from any of these without checking the denominator is a
rate over an unknown population, and two of the five would give a
number quietly computed over a fraction of the dataset.

## Duplication is easy to ship and invisible downstream

In one dataset alone: 2,255
rows are verbatim duplicates of other rows in the same split, and
14,984 transcripts appear
byte-identically in two splits, out of 76,002 rows. A second dataset
publishes two model arms whose transcripts are identical on every
one of 500 tasks. Neither is visible without hashing, neither is
mentioned on a dataset card, and training or evaluating on both
halves counts the same work twice.

## What this does not establish

Eight datasets, chosen partly because they were auditable at all,
are not a sample of anything. These are not prevalence estimates,
and a reader who leaves with "agent datasets are unreliable" has
taken more than the evidence gives. Every figure above is a
statement about a named dataset at a named revision, and the
[findings index](FINDINGS.md) keeps each one attached to the
command that checks it.

The honest summary is narrower and still worth having: when these
datasets were checked, the checks that failed were about whether
the outcome could be trusted at all, rather than about the agents.
