# The corpus: public agent-trajectory datasets, audited

Every dataset here was audited under the same discipline:
content-free evidence frozen at a named revision, checks from the
same family, and a refusal to guess at what the evidence does not
establish, excluded and counted instead. A clean bill
is a result, recorded with the same care as a defect; an auditor that
only ever finds problems is indistinguishable from one that
manufactures them.

What the entries say jointly, rather than one at a time, is in
[what the audits say together](PATTERNS.md).

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
| [FUSE-verifiers/HLE-Verifications](https://huggingface.co/datasets/FUSE-verifiers/HLE-Verifications) | `e838b3dd` | 649 | seven models asked to verify correctness reach within-question AUC 0.491 to 0.581 against a checkable answer; four of the seven have intervals containing 0.5 |
| [open-r1/OpenR1-Math-220k](https://huggingface.co/datasets/open-r1/OpenR1-Math-220k) | `e4e141ec` | 93,733 | 28,627 problems entered the published training set on a model judge's word alone, on rows where the symbolic checker had found nothing correct |
| [SALT-NLP/cogym-real-trajectories](https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) | `729096dc` | 228 | the only human-rated entry: one person's ratings of one session agree exactly 50% of the time, and the communication rating exists on 22% of sessions |
| [aisa-group/PostTrainBench-Trajectories](https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) | `39d3fcd7` | 1,842 | 260 runs carry no usable outcome; the contamination judge's apparent effect on scores is but only +0.018 [-0.019, +0.055], an interval containing zero, once benchmark composition is held fixed |
| [SWE-bench/SWE-smith-trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) | `08e109b4` | 76,002 | labels self-consistent across every duplicate; the `patch` column is not row-aligned (266 verbatim cross-repository patch groups); 2,255 duplicate rows in one split |
| [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) | `68195a14` | 80,036 | clean: every coherence probe passes; resolved rows always carry a patch and evaluation logs; no duplicate transcripts |
| [nebius/SWE-rebench-openhands-trajectories](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories) | `35455389` | 67,074 | clean labels; its recorded generated-test signal measures kappa 0.06 against adjudication over 31,389 runs, and agree 2.9 points less often than the majority-class baseline |
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

## FUSE-verifiers/HLE-Verifications, 649 questions and 32,450 graded responses

A second negative result on an outcome instrument, and deliberately
not called a replication of AEL-2026-008. That entry measured
whether an agent's own generated tests passing predicts hidden-test
resolution: an execution signal, scored by agreement. This measures
whether a model's quality score ranks answer-key correctness: a
graded judgment, scored by rank. Different construct, different
instrument class, different statistic. Two weak results about two
different things are two results, not one confirmed twice, and the
generality of the corpus rests on that distinction being kept.

649 Humanity's Last Exam questions, 50 candidate responses each.
Every response is marked correct or not by matching the published
answer, and every response is scored 0 to 5 by seven models the
dataset calls verifiers. The base rate is 51.4%,
so this is a near-balanced problem rather than one where a constant
answer scores well.

| verifier | scale | scored | questions | within-question AUC | 95% CI, family-adjusted | pooled |
|---|---|---:|---:|---:|---|---:|
| `gpt-oss-120b` | 0 to 5, continuous | 32,437 | 538 | 0.491 * | [0.464, 0.518] | 0.537 |
| `Qwen2.5-72B-Instruct` | 0 to 5 | 32,450 | 538 | 0.500 * | [0.483, 0.516] | 0.501 |
| `Skywork-Critic-Llama-3.1-70B` | 0 to 5 | 32,442 | 538 | 0.505 * | [0.486, 0.525] | 0.550 |
| `gptmini-high` | 1 to 5 | 32,450 | 538 | 0.515 * | [0.485, 0.544] | 0.578 |
| `deepseek_reasoner` | 1 to 5 | 32,417 | 538 | 0.535 | [0.511, 0.560] | 0.586 |
| `gpt5.2-high` | 0 to 5 | 32,297 | 536 | 0.547 | [0.513, 0.580] | 0.653 |
| `gemini-3-flash` | 0 to 5 | 13,166 | 441 | 0.581 | [0.557, 0.605] | 0.587 |

\* interval contains 0.5, so that grader is not distinguishable
from random at ranking within a question. 4 of seven are, and the same four are
indistinguishable before the correction as after it.

**Why within question, and why the pooled column is worse.** These
graders exist to pick the right response among fifty candidates to
the same question, so the question is the unit and the statistic is
how well a grader ranks inside one. Pooling all responses into a
single ranking lets a grader score well by detecting that a question
is easy, which is not the job. This entry published the pooled
figure first, and it flattered every grader: the range was 0.501 to 0.653 pooled and is 0.491 to 0.581 within question, with `Qwen2.5-72B-Instruct` crossing below chance. The gap between the two columns is the size of the
between-question difficulty effect, which is why both are shown.

**The graders are not on one scale, and ties decide the figures.**
The scale column is measured from the data, not taken from the card.
Five graders use six integer levels, two never emit 0 and use five,
and `gpt-oss-120b` is not on an integer scale at all. With fifty
responses to a question and six possible scores, nearly every
pairwise comparison inside a question is a tie, so the tie
convention is decisive rather than incidental: mid-rank throughout,
which is the Mann-Whitney treatment and the one that neither
rewards nor punishes a grader for refusing to discriminate. A
grader with more levels can separate responses the six-level
graders cannot, so the column is worth reading beside the AUC
rather than under it.

**Why AUC and not an accuracy.** The graders score against a rubric
the dataset does not publish, so no threshold can be justified from
the data, and picking one would be choosing how generous to be. AUC
asks only whether a higher score is more often a correct response,
which is the weakest assumption under which a grader could be said
to work at all. It is not comparable to the agreement floors in
SPEC section 7.2, which govern chance-corrected agreement
coefficients and held-out accuracy; there is no AUC floor in that
contract, and reading one across metric families is the category
error this project has already published once.

**Why the intervals are wide, twice over.** 32,450 responses sit
inside 649 questions and are not independent, so the bootstrap
resamples questions rather than responses; treating the responses as
independent would give intervals several times too tight and is the
error this corpus most often finds elsewhere. Then the intervals are
seven simultaneous claims, so they carry the same Bonferroni
correction the frontier protocol already applies to a family this
size, alpha / 2k = 0.00357 in each tail. At a nominal 95% each, the
chance that at least one of seven is wrong is about 30%. The
correction widens every interval and costs this entry its more
comfortable readings, which is the point of applying it. The draw
count is 6,000, the floor at which that tail still holds the
twenty resamples the protocol demands; an earlier 400 put Monte
Carlo noise in the published third decimal.

**Prior work.** That model judges are imperfect is established: MT-Bench measured judge agreement with human preference,
RewardBench scores reward models against it, and position,
verbosity and self-preference bias each have a literature. What
those measure is a judge against human preference on a curated set.
This measures a shipped dataset's own scoring columns against an
answer key, per question, at a pinned revision, and reports what a
consumer of that dataset would get. The result is a census of
published data, not a leaderboard entry, and it is not evidence
that model grading cannot work.

**What it does not establish.** Every response was generated by one
model, so this measures graders on that model's output rather than
on output in general. The ground truth is exact matching against a
published answer, with a model used to parse answer formats, so it
is checkable but not untouched by a model. HLE is adversarially
hard by construction. And one (question, grader) pair of 4,543
was excluded because that grader scored 47 of 50 responses and
nothing in the data says which 47; the alignment is unknowable, so
it is dropped and counted rather than zipped, which would have
silently truncated to the shorter list.

**One grader is mostly absent, and it is the top row.** `gemini-3-flash` carries no score on 19,284 of the 32,450 responses, scoring 441 of 538 rankable questions. Its figure is computed on the subset it
did score, the missingness is not random with respect to outcome,
and the direction of the resulting bias is unknown. It is left in
the table with its coverage stated rather than dropped, because
dropping the highest scorer without saying so would be the more
flattering choice.

Evidence: [frozen/hle-verifiers.json](corpus/frozen/hle-verifiers.json),
content-free, carrying the SHA-256 of the source file it read.

## open-r1/OpenR1-Math-220k, 93,733 problems in a published training set

The two entries above needed a rare kind of dataset, one shipping a
proxy signal and a checkable one on the same rows. This dataset
appears to be a third. It carries `correctness_math_verify`, a
symbolic check against the published answer, and
`correctness_llama`, a 70B model asked the same question, both
attached to the same generations.

They cannot be compared. The judge was run only where the symbolic
check had already found nothing correct, and the freeze bears that
out exactly: across the 28,627 rows carrying both columns, the
number with even one symbolically correct generation is
0. The symbolic column is constant there, and a constant
agrees with everything at chance. A first pass computed Cohen's
kappa over these rows, got -0.000, and nearly published it.

What survives is structural, and it matters more than the statistic
would have. This is training data, not an evaluation. The filtering
field `correctness_count` equals the judge's count on all
28,627 dual-signal rows and the symbolic count on all
65,106 others, without exception. So 28,627 problems,
30.5% of the published set, are present only because the
judge overruled a checker that had rejected every candidate. The
judge accepted 42,271 of 55,808 rejected generations,
75.7% (95% CI 75.4% to 76.0%, bootstrapped over
problems, since generations cluster inside them). Across the seven
source strata the rate runs 74.9% to 79.5%, and a chi-square test of homogeneity does not
detect a difference between them (X2 = 6.72, df = 6, p = 0.35) at n = 55,808.
That is consistent with one common rate rather than proof of one,
which is the most a failure to reject supports. An earlier draft
called the range flat and concluded from the word that it was not
one problem set's quirk, which is an eyeball standing where a test
belongs.

This is not evidence that the judge is wrong. A symbolic checker
that cannot parse a valid answer and a judge that waves through an
invalid one produce the same two columns. Distinguishing them needs
the answers themselves, so a verification pass re-fetched
398 admitted generations, selected by hash rank,
every shard checked against the SHA-256 the freeze recorded, and
compared the final boxed answer with the published one:

- choice letter against value: 158
- published answer multivalued: 133
- unresolved other: 86
- both numeric and differ: 18
- matches published answer: 2
- no boxed answer: 1

It does not settle the question, and it is reported as failing to.
Most of the gap is shape rather than substance: a generation boxing
a multiple-choice letter against a published value, or a published
answer carrying several roots at once. Of the 398 checked, only 20 reduce to an unambiguous number on both sides at all, and of those 18 disagree: 90% of the comparable cases, not the 4.5% a reader gets by dividing into everything. This entry published the second figure first, which mixes "could not compare" into "compared and agreed" and is the denominator error the corpus finds elsewhere. The honest reading is that the comparable subset is small and mostly disagrees, and that answer-format heterogeneity is itself the likeliest reason the symbolic check failed here to begin with.
Only where both sides reduce
to a single unambiguous number and differ does the comparison bear
on the judge, and this project has already published a
re-adjudicator whose 186 disagreements were every one its own
parser's blindness, so the parser here is treated as the third
instrument in the room rather than the referee.

The finding is therefore about provenance, not accuracy: the
correctness of a third of a widely used training set rests on an
unaudited model judgment, and the shipped columns are arranged so
that no one downloading it can audit that judgment against the
checkable signal sitting beside it.

Evidence: [frozen/openr1-math.json](corpus/frozen/openr1-math.json)
and [frozen/openr1-math-answers.json](corpus/frozen/openr1-math-answers.json), content-free, carrying the
SHA-256 of every parquet shard read.

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
+0.018, and its 95% interval is [-0.019, +0.055]: it contains zero, so within
benchmarks this dataset does not show contamination paying at all.
The pooled figure's interval is [+0.173, +0.241] and does not
contain zero, which is what makes the pair a Simpson case rather
than two noisy numbers.

**No ratio is published between them, deliberately.** An earlier
draft said the pooled figure was larger by a factor of 11.5,
which is arithmetic on two point estimates. A ratio whose
denominator's interval contains zero has effectively unbounded
uncertainty; bootstrapping this one gives an interval running from
about -110 to +107. The reportable fact is the pair of intervals
above, not the number you get by dividing them. An earlier draft
also offered that contaminated runs beat clean ones in only 2 of 5 benchmarks as corroboration; that
is a sign test at n=5 with a two-sided p of 1.0, and it corroborates
nothing. It is stated here as a count and nothing is inferred from
it.

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

- Raw agreement 51.4%, against a majority-class baseline of 54.2%: consulting the proxy is **-2.9 points** (95% CI -5.0 to -0.9, clustered over 5,870 instances) against always answering with the commoner label. The interval excludes zero, so the proxy is reliably worse than the baseline it has to beat, not merely unhelpful on average.
- Cohen's kappa **0.062**, 95% CI [0.047, 0.077] bootstrapped over 5,870 instances. Reliably above zero and far too small to act on. This entry said "indistinguishable from guessing" before the interval existed, which was wrong in the direction of overstating: chance is zero and this excludes zero. The useful statement is the line above it, that the signal is worse than the baseline it has to beat.
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
adjudicated outcome. That is not an accusation: publishing
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
and, where raw logs ship beside graded-test lists, the
re-adjudication verdict. `research/corpus/corpus_report.py` renders
this document from the frozen evidence alone; `make corpus` fails
when the two disagree. No prompts, responses, patches, or logs are
stored.

**Every entry re-derives from upstream, and that is enforced rather
than asserted.** `make verify-corpus` holds one verifier per frozen
document, each using the transport its freeze used, and each
re-running the freezer's own extractor on freshly fetched bytes:
what it proves is that the same source and the same code produce the
committed file. A frozen document with no verifier fails the run.
That rule is new because it had to be: the verifier once covered
only the datasets frozen through one transport and silently skipped
the rest, so six of the fourteen findings here rested on evidence no
reader could check, including the two this corpus leans on hardest.
It printed the count of what it had checked, which reads as the
count of what exists.
