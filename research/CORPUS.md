# The corpus: public agent-trajectory datasets, audited

Every dataset here was audited under the same discipline:
content-free evidence frozen at a named revision, checks from the
same family, and a refusal to guess at what the evidence does not
establish, excluded and counted instead. A clean bill
is a result, recorded with the same care as a defect; an auditor that
only ever finds problems is indistinguishable from one that
manufactures them.

Every result here is also in the [findings index](FINDINGS.md), one
citable line each with a stable identifier, a priority date, and the
command that checks it.

Entries are open to third parties under one written contract:
[contributing an audit](../docs/contributing-an-audit.md). An entry
that satisfies it gets merged no matter who submits it; one that
does not gets returned no matter who submits it, including us.

Each dataset is an independent public upload; an arm or model name
inside one identifies a set of runs in that dataset, not a number any
vendor published, and nothing here is a measurement of a model.

| dataset | revision | rows | what the audit found |
|---|---|---:|---|
| [tarsur385/swebench-verified-trajectories](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) | `b55979d6` | 5,000 | 1 of 10 arms never confirmed by its cross-check; one duplicated arm pair, labels 91.2% self-consistent ([full audit](OUTCOME_AUDIT.md)) |
| [togethercomputer/CoderForge-Preview-32B…](https://huggingface.co/datasets/togethercomputer/CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories) | `753f0504` | 500 | clean: reward re-derives from the raw logs on all 434 parseable rows |
| [SALT-NLP/cogym-real-trajectories](https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) | `729096dc` | 228 | the only human-rated entry: one person's ratings of one session agree exactly 50% of the time, and the communication rating exists on 22% of sessions |
| [aisa-group/PostTrainBench-Trajectories](https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) | `39d3fcd7` | 1,842 | 260 runs carry no usable outcome; the contamination judge's apparent effect on scores is 12x smaller once benchmark composition is held fixed |
| [SWE-bench/SWE-smith-trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) | `08e109b4` | 76,002 | labels self-consistent across every duplicate; the `patch` column is not row-aligned (266 verbatim cross-repository patch groups); 2,255 duplicate rows in one split |
| [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) | `68195a14` | 80,036 | clean: every coherence probe passes; resolved rows always carry a patch and evaluation logs; no duplicate transcripts |
| [nebius/SWE-rebench-openhands-trajectories](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories) | `35455389` | 67,074 | clean labels; its recorded generated-test signal measures kappa 0.06 against adjudication over 31,389 runs |
| [JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified](https://huggingface.co/datasets/JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified) | `dd79e254` | 1,785 | `resolved` column present, populated on 0 rows |

## togethercomputer/CoderForge-Preview-32B, SWE-bench Verified, 500 rows

The dataset ships the raw evaluation log and the graded-test lists
beside every published `reward`, which permits the strongest check in
this corpus: re-deriving each label from the log instead of comparing
two fields the same pipeline wrote.

On every one of the **434 rows the parser could fully
read, the re-derived resolution equals the published reward**:
0 disagreements. The published rate on those rows is
confirmed, not merely self-consistent.

The refusals, counted: 64 rows use log formats the parser does not
read and 2 depend on whether XFAIL
counts as a pass, so they are
excluded, not guessed. The first draft of this parser read only
pytest's format and would have reported 186 false disagreements on
Django's; a graded test the parser cannot locate now makes the row
UNPARSED, never a finding.

Outcome census: {'0.0': 203, '1.0': 297}. No duplicate
transcripts. No positive outcome on a run of one step or fewer.

## SALT-NLP/cogym-real-trajectories, 228 human-agent sessions

Every other entry here audits a coding agent, and every outcome
instrument in them is automated: a cross-check column, a
re-adjudication from logs, model-generated tests, an LLM judge.
This is neither. 228 real human-agent collaboration sessions across
related_work, tabular_analysis, travel_planning, where the outcome labels were
typed by the person who was in the session. It is the one entry
whose instrument is the thing every other instrument gets validated
against.

**What a rating covers.** Overall satisfaction is on every session,
the artifact rating on 84%, and the
communication rating on only 22% - 50 sessions, not 228. A
reader computing communication quality from this dataset is
computing it over a fifth of it, and the schema does not say so.

**How far apart one person's answers run.** These are different
questions, so they are not expected to match, and this is emphatically
not a test-retest measurement: nobody was asked the same thing twice.
What it bounds is how much a single number labelled "the human
rating" can carry.

| pair | n | exact | mean gap | 2+ apart | quadratic-weighted kappa |
|---|---:|---:|---:|---:|---:|
| outcomeRating vs agentRating | 191 | 50% | 0.60 | 9% | 0.625 |
| outcomeRating vs communicationRating | 50 | 52% | 0.68 | 14% | 0.515 |
| agentRating vs communicationRating | 50 | 42% | 0.70 | 12% | 0.639 |

The artifact rating and overall satisfaction, the two closest of the
three, land at quadratic-weighted kappa 0.625 - just
above the 0.60 floor this package demands of an automated outcome
instrument before it will issue a green decision, and they disagree
by two points or more on 9%
of sessions. The point is not that people are unreliable. It is that
human judgement of one session is several numbers rather than one,
so any instrument validated against "human agreement" inherits
whichever question was asked, and datasets rarely record which.

**A suspicion that died at base rate**, recorded because the
pipeline is supposed to kill these before they are published: very
short sessions rated highly would suggest satisfaction untethered
from work done. There are 4 sessions of
three events or fewer, mean rating 3.0. Four sessions establish nothing.

Evidence: [frozen/cogym.json](corpus/frozen/cogym.json), content-free
and more carefully than usual because these are real people - ratings, counts and hashes, never the query, the feedback text, or
the event log.

## aisa-group/PostTrainBench-Trajectories, 1,842 autonomous runs

The most-downloaded agent-trajectory dataset on the hub, and the
only entry here that is not a table. Each row is a run in which an
agent was given a base model, an evaluation script and ten hours on
an H100, and had to make the model better: the open-ended shape the
field keeps proposing as the successor to benchmarks. Three
independent signals per run make it auditable - a measured accuracy
from the evaluation script, an LLM judge's verdict on whether the
agent contaminated its training data, and a wall clock against a
priced budget.

**A finding that does not survive its own stratification.**
Contaminated runs score far better than clean ones:
a pooled difference of +0.209 accuracy.
Published as it stands, that is a headline about cheating paying
twenty points. It is mostly composition. Contamination is not
spread evenly: 39% of `bfcl`
runs are flagged, 47% of all
contamination sits there, and `bfcl` has a
clean-run mean of 0.673 against a corpus
where most benchmarks sit near 0.2. Pooling therefore credits that
benchmark's easiness to contamination. Holding benchmark fixed and
weighting by size, the difference is
+0.018 - smaller by a factor of
12 - and contaminated runs beat clean ones
in only 2 of
5 benchmarks with enough of both to
compare. The honest statement is that this dataset does not show
contamination reliably paying, and that anyone computing the pooled
number gets an answer eleven times too large.

**What is missing, counted rather than dropped.**
208 runs ship no metrics file and
52 ship one that is not valid JSON, so
260 of 1,842 runs
(14.1%) carry no usable
outcome at all. A further 331 runs carry no
contamination verdict, so they are neither clean nor flagged; a
leaderboard built from this dataset has to decide what to do with
them, and the dataset does not say.

**The judge is an instrument, and nothing here validates it.**
It flags 176 of 1,511 judged runs as
contaminated and 2 as having trained a
disallowed base model. Those verdicts govern whether a run counts.
No agreement measurement against human adjudication ships with the
dataset, so the flags are unvalidated in exactly the way
[AEL-2026-008](FINDINGS.md) measured elsewhere. This is a gap in
what can be established, not a claim that the judge is wrong.

Median run length is 7.3 hours of H100 time
against a ten-hour cap. Evidence:
[frozen/posttrainbench.json](corpus/frozen/posttrainbench.json);
every figure recomputes offline with `make corpus`.

## SWE-bench/SWE-smith-trajectories, three splits, 76,002 rows

The official SWE-bench organisation's training-trajectory release,
behind their published SWE-agent-LM-32B. Its card's prose describes
5,017 trajectories and its size category says 1K-10K; the dataset
serves 76,002 rows (25,826 ticks, 24,100 tool, 26,076 xml).

**What is clean, stated with the same care as the defects.** The
outcome labels agree with themselves everywhere: across all
18,167 duplicate-transcript groups,
0 label disagreements. And the
"resolved with an empty patch" suspicion the first rows raised
dies at base rate: the patch field is empty on 27.1% of all rows and 27.5% of resolved ones, so emptiness
is a population artifact of the column, not a property of the label.

**Duplication.** The xml split contains
2,255 rows that are verbatim
duplicates of other rows in the same split, identical in id,
transcript, and label. 14,984 transcripts
appear byte-identically in both the tool and xml splits, so
training on both sees those examples twice. None involve ticks.

**The `patch` column is not row-aligned.**
266 distinct non-empty patch
contents, covering 1,933 rows, each
appear verbatim under instances from two or more different
repositories. A hash collision on a trivial diff would explain
that, so a verification pass re-fetched every row of the first
50 hash-ranked groups of the
266 and reduced each patch to
content-free facts: 50 of
50 are non-trivial unified diffs,
34 contain rows whose patch touches paths
foreign to the instance's repository under a deliberately generous
matcher, and one 457-byte patch appears under
10 rows spanning Red-DiscordBot and python-dotenv and python-markdownify
(0 fetch or hash failures). Whatever the
column records, it is not reliably the fix for its row.

The scope of that claim, stated precisely: the model was fine-tuned
on `messages`, not `patch`, so this is a defect in an auxiliary
column a consumer might filter or evaluate by, not evidence that
the training signal or the labels are wrong. Evidence:
[frozen/swesmith-*.json](corpus/frozen/) and
[frozen/swesmith-patch-check.json](corpus/frozen/swesmith-patch-check.json);
reproduce the verification with `python3 research/corpus/patch_check.py`.

## nebius/SWE-agent-trajectories, 80,036 rows

SWE-agent runs over SWE-bench-style tasks with the outcome label,
the generated patch, and the raw evaluation logs beside every row.
13,389 of 80,036 rows are marked
resolved, and every coherence probe this corpus knows passes:

- All 13,389 resolved rows carry a non-empty
  patch (0 exceptions) and
  non-empty evaluation logs
  (0 exceptions). Empty
  patches (9,478) and empty logs
  (9,397) occur only on unresolved
  rows, under exactly the exit statuses that should produce them
  (context exhaustion, early exit, submitted-no-patch).
- 0 duplicate transcripts
  across all 80,036 rows.

A clean bill, with its strength stated precisely: this is
coherence, weaker than the CoderForge entry's re-adjudication,
because the dataset does not ship the graded-test lists a
re-derivation needs. One artifact of ours, recorded so nobody
mistakes it for a finding: the frozen id is instance::model, which
repeats 75,817 times because the
dataset legitimately holds several attempts per pair; the
transcripts are all distinct.

## nebius/SWE-rebench-openhands-trajectories, 67,074 rows

OpenHands runs where each row records the adjudicated `resolved`
label and, on some rows, whether the model's own generated tests
passed. The labels are coherent: only
56 empty patches, every one unresolved;
runs that hit the iteration cap resolve at
18%
against 48% overall;
0 duplicate transcripts.

**What the dataset makes measurable is the interesting part.**
Model-generated tests are widely proposed as a cheap outcome
instrument. Here both signals sit on the same
31,389 rows, which is a validity
measurement at scale:

- Raw agreement 51.4%, Cohen's kappa
  **0.062** - indistinguishable from guessing.
- Conditioned on the generated tests themselves being judged
  correct (9,444 rows): kappa
  0.101, precision
  0.729. Better, and still a sixth
  of the 0.60 kappa floor this package requires of an outcome
  instrument.
- Where the generated tests were judged incorrect
  (21,868 rows): kappa
  0.020, pure noise - and that is
  the majority of rows carrying the signal.

Scope, stated exactly: this measures the generated-test *method*,
not a defect of the dataset - recording both signals side by side
is what made the measurement possible at all, and the signal is
absent on 35,685 rows,
so nothing here extrapolates to them. Evidence:
[frozen/nebius-sweagent.json](corpus/frozen/) and
[frozen/nebius-openhands.json](corpus/frozen/); every figure
recomputes offline.

## JetBrains-Research, SWE-bench test-minus-verified, 1,785 rows

The `resolved` column is null on all 1,785 rows. 1,221 runs report
`exit_status` "Submitted" and 564
"LimitsExceeded"; none carries an
adjudicated outcome. That is not an accusation — publishing
trajectories without scoring them is a legitimate choice, and the
column is honestly null rather than defaulted to a flattering value.
It is a warning to consumers: a resolution rate computed from this
dataset divides by zero scored runs, and any figure quoted from it
was made somewhere else.

No duplicate transcripts. Outcome census: {'null': 1785}.

## How an entry gets here

`research/corpus/freeze.py` fetches rows at a revision bracketed by
the repository SHA (refusing a snapshot that moved mid-fetch, a
partial arm, or a truncated cell), keeps identifiers, outcome fields,
step counts, and SHA-256 hashes of the content it refuses to copy,
and — where raw logs ship beside graded-test lists — the
re-adjudication verdict. `research/corpus/audit.py` renders this
document from the frozen evidence alone; `make corpus` fails when the
two disagree. No prompts, responses, patches, or logs are stored.
