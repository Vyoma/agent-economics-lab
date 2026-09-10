# Findings index

Every audit result this project has published, with a stable
identifier, the date it was first published, the command that checks
it, what to do about it if you use the dataset, and the scope it does
not claim.

**16 standing: 6 defects, 8 measurements, 2 clean bills.** Clean bills are listed here with the same weight as defects, because
an auditor that only ever finds problems is indistinguishable from
one that manufactures them.

A published finding is never edited in place. It is superseded by a
new identifier or retracted with a reason, and either way the
original entry stays. Numbers below are fixed text so a citation
does not move; a test recomputes each of them from the frozen
evidence and fails the build if the two ever disagree.

| id | date | kind | dataset | finding |
|---|---|---|---|---|
| `AEL-2026-001` | 2026-08-31 | defect | `swebench-verified-trajectories` | The gemini-3-pro arm reports info.resolved true on all 500 tasks while its own info.scores.resolved reads "unknown" on all 500, so its 100%... |
| `AEL-2026-002` | 2026-08-31 | measurement | `swebench-verified-trajectories` | The gpt-5.2-codex and gpt-5.2-high arms carry byte-identical transcripts on all 500 tasks, and info.resolved disagrees between the copies on 44 of... |
| `AEL-2026-003` | 2026-09-01 | clean bill | `CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories` | Clean bill |
| `AEL-2026-004` | 2026-09-02 | defect | `SWE-smith-trajectories` | The patch column is not row-aligned |
| `AEL-2026-005` | 2026-09-02 | defect | `SWE-smith-trajectories` | The xml split contains 2,255 rows that are verbatim duplicates of other rows in the same split, identical in id, transcript and label, and 14,984... |
| `AEL-2026-006` | 2026-09-01 | defect | `agent-trajectories-swe-bench-test-minus-verified` | The resolved column is present and populated on none of the 1,785 rows, so a consumer computing a resolution rate from this dataset gets no signal... |
| `AEL-2026-007` | 2026-09-02 | clean bill | `SWE-agent-trajectories` | Clean bill across 80,036 rows |
| `AEL-2026-008` | 2026-09-02 | measurement | `SWE-rebench-openhands-trajectories` | Model-generated tests, measured against adjudicated outcomes on the 31,389 rows carrying both signals, agree at Cohen's kappa 0.062, 95% CI... |
| `AEL-2026-009` | 2026-09-03 | measurement | `PostTrainBench-Trajectories` | Runs the contamination judge flagged score +0.209 accuracy above clean runs when pooled, 95% CI [+0.173, +0.241], which reads as cheating paying... |
| `AEL-2026-010` | 2026-09-03 | defect | `PostTrainBench-Trajectories` | 260 of 1,842 runs carry no usable outcome: 208 ship no metrics file and 52 ship one that is not valid JSON |
| `AEL-2026-011` | 2026-09-03 | measurement | `cogym-real-trajectories` | Across 191 sessions where the same person rated both the artifact and their overall satisfaction, the two ratings agree exactly 50% of the time... |
| `AEL-2026-012` | 2026-09-03 | defect | `cogym-real-trajectories` | The communication rating is present on 50 of 228 sessions and the artifact rating on 191; only overall satisfaction is on every session |
| `AEL-2026-013` | 2026-09-03 | measurement | `HLE-Verifications` | Seven models the dataset calls verifiers scored 32,450 responses to 649 Humanity's Last Exam questions, against correctness established by... |
| `AEL-2026-014` | 2026-09-04 | measurement | `OpenR1-Math-220k` | The default split ships two verification columns on the same generations: correctness_math_verify, a symbolic check against the published answer,... |
| `AEL-2026-015` | 2026-09-10 | measurement | `SWE-rebench-openhands-trajectories` | Selective prediction does not repair the generated-test proxy of AEL-2026-008; it makes the shortfall larger |
| `AEL-2026-016` | 2026-09-10 | measurement | `HLE-Verifications` | Forcing the seven graders of AEL-2026-013 to abstain where they are least confident does not rescue them |

## The findings in full

### AEL-2026-001 - defect, 2026-08-31

**Dataset.** [`tarsur385/swebench-verified-trajectories`](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) at `b55979d6`

The gemini-3-pro arm reports info.resolved true on all 500 tasks while its own info.scores.resolved reads "unknown" on all 500, so its 100% resolution rate is confirmed by nothing in the dataset. Nine of those runs record at most one API call and no spend.

**Check it.** `make outcome-audit && make verify-upstream`

**If you use this dataset.** Drop the gemini-3-pro arm or report its rate as unconfirmed. Do not quote the 100%.

**What it does not claim.** A statement about this third-party upload at this revision. Not a measurement of any model, and not a claim that the dataset is wrong: the cross-check field the dataset itself ships is what reveals it.

### AEL-2026-002 - measurement, 2026-08-31

**Dataset.** [`tarsur385/swebench-verified-trajectories`](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) at `b55979d6`

The gpt-5.2-codex and gpt-5.2-high arms carry byte-identical transcripts on all 500 tasks, and info.resolved disagrees between the copies on 44 of them: the label agrees with itself 91.2% of the time on identical input, 95% CI [88.4%, 93.4%], against a 20.6-point spread across the nine scored arms.

**Check it.** `make outcome-audit && make verify-upstream`

**If you use this dataset.** Treat the two gpt-5.2 arms as one arm. If you rank arms in this dataset, 8.8 points is the floor below which a difference is indistinguishable from the label disagreeing with itself.

**What it does not claim.** Test-retest, filed as such. Repeatability is not validity: an instrument that scores identical inputs identically every time can be systematically wrong about all of them. What causes the 8.8% is not established here.

### AEL-2026-003 - clean bill, 2026-09-01

**Dataset.** [`togethercomputer/CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories`](https://huggingface.co/datasets/togethercomputer/CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories) at `753f0504`

Clean bill. The published reward re-derives from the raw evaluation logs on every one of the 434 rows the parser could fully read, with no disagreements.

**Check it.** `make corpus`

**If you use this dataset.** Usable as published. The reward column re-derives from the raw logs on every row the parser could read.

**What it does not claim.** The strongest check in this corpus, because the dataset ships the graded-test lists and raw logs a re-derivation needs. It says nothing about the 66 rows the parser could not fully read, which are excluded and counted rather than assumed.

### AEL-2026-004 - defect, 2026-09-02

**Dataset.** [`SWE-bench/SWE-smith-trajectories`](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) at `08e109b4`

The patch column is not row-aligned. 266 distinct non-empty patch contents, covering 1,933 rows, each appear verbatim under instances from two or more different repositories; a re-fetch of every row in the first 50 hash-ranked groups found 50 of 50 are non-trivial unified diffs and 34 contain rows whose patch touches paths foreign to the instance's repository.

**Check it.** `make corpus && python3 research/corpus/patch_check.py`

**If you use this dataset.** Do not train, filter, or evaluate on the patch column. Use the transcript.

**What it does not claim.** An auxiliary-column defect in the official SWE-bench organisation's training-trajectory release. The model was fine-tuned on messages, not patch, so this is not evidence against the training signal or the labels, which are clean across all 18,167 duplicate-transcript groups.

### AEL-2026-005 - defect, 2026-09-02

**Dataset.** [`SWE-bench/SWE-smith-trajectories`](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) at `08e109b4`

The xml split contains 2,255 rows that are verbatim duplicates of other rows in the same split, identical in id, transcript and label, and 14,984 transcripts appear byte-identically in both the tool and xml splits, so training on both sees those examples twice. The dataset card's prose describes 5,017 trajectories where the dataset serves 76,002 rows.

**Check it.** `make corpus`

**If you use this dataset.** Deduplicate by transcript hash across both splits before training, or 14,984 examples are seen twice.

**What it does not claim.** Duplication and a card-versus-content discrepancy. Not a claim that either is unintentional.

### AEL-2026-006 - defect, 2026-09-01

**Dataset.** [`JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified`](https://huggingface.co/datasets/JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified) at `dd79e254`

The resolved column is present and populated on none of the 1,785 rows, so a consumer computing a resolution rate from this dataset gets no signal from the field that names one.

**Check it.** `make corpus`

**If you use this dataset.** Do not compute a resolution rate from this dataset. The field that would give you one is empty on all 1,785 rows.

**What it does not claim.** A statement about this revision. Labels may exist elsewhere; the finding is that this column carries none.

### AEL-2026-007 - clean bill, 2026-09-02

**Dataset.** [`nebius/SWE-agent-trajectories`](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) at `68195a14`

Clean bill across 80,036 rows. Every resolved row carries a non-empty patch and non-empty evaluation logs; empty patches and empty logs occur only on unresolved rows, under exactly the exit statuses that should produce them; no duplicate transcripts.

**Check it.** `make corpus`

**If you use this dataset.** Usable as published, on the checks run here.

**What it does not claim.** Coherence, weaker than AEL-2026-003's re-adjudication, because this dataset does not ship the graded-test lists a re-derivation would need.

### AEL-2026-008 - measurement, 2026-09-02

**Dataset.** [`nebius/SWE-rebench-openhands-trajectories`](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories) at `35455389`

Model-generated tests, measured against adjudicated outcomes on the 31,389 rows carrying both signals, agree at Cohen's kappa 0.062, 95% CI [0.047, 0.077] bootstrapped over 5,870 instances. That interval excludes zero, so the signal is real; it is also far too small to act on. The decision-relevant comparison is against the majority class: raw agreement is 51.4% where always answering with the commoner label scores 54.2%, so consulting the proxy costs 2.9 points, 95% CI [0.9, 5.0] points, an interval excluding zero. Conditioned on the generated tests themselves being judged correct, kappa is 0.101 with precision 72.9% on 9,444 rows; that split was chosen after seeing the pooled result and is not corrected for multiplicity.

**Check it.** `make corpus`

**If you use this dataset.** Do not gate releases on model-generated tests. Compare any outcome proxy against the majority-class baseline before trusting it: this one loses to always guessing the commoner label by 2.9 points, so consulting it is worse than not having it.

**What it does not claim.** A measurement of the generated-test method as an outcome instrument on this dataset, not a defect of the dataset: recording both signals side by side is what made the measurement possible. The signal is absent on 35,685 rows, so nothing here extrapolates to them, and this is one dataset in one domain.

### AEL-2026-009 - measurement, 2026-09-03

**Dataset.** [`aisa-group/PostTrainBench-Trajectories`](https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) at `39d3fcd7`

Runs the contamination judge flagged score +0.209 accuracy above clean runs when pooled, 95% CI [+0.173, +0.241], which reads as cheating paying twenty points. Holding benchmark fixed and weighting by size, the difference is +0.018 with a 95% CI of [-0.019, +0.055], which contains zero: within benchmarks the dataset does not show contamination paying at all. 39% of `bfcl` runs are flagged and it carries 47% of all contamination while having a clean-run mean of 0.673 against a corpus sitting near 0.2, so pooling credits that benchmark's easiness to contamination. No ratio between the two figures is published: a ratio whose denominator's interval contains zero is unbounded, and this one bootstraps to roughly [-110, +107].

**Check it.** `make corpus`

**If you use this dataset.** Stratify by benchmark before quoting any contamination effect. Pooled it looks like twenty points; within benchmarks the interval contains zero. If your own metric mixes populations with different baselines, the pooled number is measuring the mix.

**What it does not claim.** A statement about a confound in this dataset, not about whether contamination helps in general: the stratified estimate is observational, benchmarks are not randomised across runs, and the flags come from an unvalidated judge. It does establish that the pooled comparison anyone would compute first is an order of magnitude too large.

### AEL-2026-010 - defect, 2026-09-03

**Dataset.** [`aisa-group/PostTrainBench-Trajectories`](https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) at `39d3fcd7`

260 of 1,842 runs carry no usable outcome: 208 ship no metrics file and 52 ship one that is not valid JSON. A further 331 runs carry no contamination verdict, so they are neither clean nor flagged, and the dataset does not say how a consumer should treat them.

**Check it.** `make corpus`

**If you use this dataset.** Publish the denominator. 260 of 1,842 runs carry no usable outcome and 331 no contamination verdict; dropping them silently changes what your rate measures.

**What it does not claim.** A completeness statement about this revision. Not a claim that the missing runs failed, which is precisely what cannot be determined from an absent or unparseable metrics file.

### AEL-2026-011 - measurement, 2026-09-03

**Dataset.** [`SALT-NLP/cogym-real-trajectories`](https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) at `729096dc`

Across 191 sessions where the same person rated both the artifact and their overall satisfaction, the two ratings agree exactly 50% of the time and reach quadratic-weighted kappa 0.625, 95% CI [0.520, 0.708], an interval that straddles the 0.60 floor and so cannot decide against it at this sample, disagreeing by two points or more on 9% of sessions. That is barely above the 0.60 kappa floor this package requires of an automated outcome instrument.

**Check it.** `make corpus`

**If you use this dataset.** Do not substitute the artifact rating for overall satisfaction. They agree exactly half the time.

**What it does not claim.** These are different questions, not the same question asked twice, so divergence is expected and this is not a reliability or test-retest measurement. What it bounds is how much a single number called 'the human rating' carries: any instrument validated against human agreement inherits whichever question was asked, and datasets rarely record which. One platform, three tasks, 228 sessions.

### AEL-2026-012 - defect, 2026-09-03

**Dataset.** [`SALT-NLP/cogym-real-trajectories`](https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) at `729096dc`

The communication rating is present on 50 of 228 sessions and the artifact rating on 191; only overall satisfaction is on every session. A consumer computing communication quality from this dataset computes it over 22% of it, and the schema does not distinguish 'not rated' from a rating.

**Check it.** `make corpus`

**If you use this dataset.** Compute communication quality over the 50 sessions that carry it, or do not compute it. Over 228 it is 78% imputation.

**What it does not claim.** A completeness statement about optional fields the dataset card documents as optional. Not a claim the absences are unintentional; the finding is that the resulting denominators differ by field and nothing in the data announces it.

### AEL-2026-013 - measurement, 2026-09-03

**Dataset.** [`FUSE-verifiers/HLE-Verifications`](https://huggingface.co/datasets/FUSE-verifiers/HLE-Verifications) at `e838b3dd`

Seven models the dataset calls verifiers scored 32,450 responses to 649 Humanity's Last Exam questions, against correctness established by matching the published answer. Measured the way the graders are actually used, ranking candidates within a question, their discrimination runs from AUC 0.491 to 0.581. 4 of the seven have intervals containing 0.5, Bonferroni-corrected across the seven simultaneous claims at the same alpha / 2k the frontier protocol uses, including Skywork-Critic-Llama-3.1-70B, a model built to criticise, and gpt-oss-120b sits below chance at 0.491. Pooling all responses into one ranking instead reports 0.501 to 0.653, and that gap is between-question difficulty, not grader skill. This is a second negative result on an outcome instrument, not a replication of AEL-2026-008, which measured a different construct with a different statistic.

**Check it.** `make corpus`

**If you use this dataset.** Score your grader within question before you trust it, and on the responses it will actually rank. Four of seven models here could not be told from random at that task, and the pooled figure hides it.

**What it does not claim.** The seven are not on one scale: five use six integer levels, two never emit 0 and use five, and gpt-oss-120b is not integer-scaled. Ties take the mid-rank, which is decisive at fifty responses and six levels rather than incidental, though the grader with the most levels scores lowest, so ties are not hiding a signal. Intervals are family-adjusted across seven graders, so they are wider than a single-comparison reading; the same four contain 0.5 either way. AUC is threshold-free because the scoring rubric is not published, and it is not comparable to the agreement floors in SPEC 7.2, which govern chance-corrected agreement and held-out accuracy; there is no AUC floor in that contract. All responses come from one model, so this measures graders on that model's output rather than in general. Ground truth is exact matching against a published answer with a model used to parse answer formats: checkable, but not untouched by a model. HLE is adversarially hard by construction. gemini-3-flash, the highest scorer, carries no score on 19,284 of 32,450 responses and its figure is computed on the subset it did score, with the bias direction unknown. This is not a claim that model grading cannot work, only that on this data none of seven cleared a bar worth calling useful.

### AEL-2026-014 - measurement, 2026-09-04

**Dataset.** [`open-r1/OpenR1-Math-220k`](https://huggingface.co/datasets/open-r1/OpenR1-Math-220k) at `e4e141ec`

The default split ships two verification columns on the same generations: correctness_math_verify, a symbolic check against the published answer, and correctness_llama, a 70B model judge. They cannot be compared with each other, because the judge was run only on rows where the symbolic check had already found nothing correct: across all 28,627 rows carrying both columns, not one has a single symbolically correct generation. The filtering field correctness_count equals the judge's count on every one of those rows and the symbolic count on every one of the other 65,106, without exception. So 28,627 problems, 30.5% of this published training set, are present only because a model judge overruled a checker that had rejected every candidate, and the shipped columns leave no way to audit that judgment against the checkable signal sitting beside it. The judge accepted 75.7% of the generations the symbolic check rejected, a rate flat across every source stratum.

**Check it.** `make corpus`

**If you use this dataset.** Filter to rows whose correctness_math_verify contains a true before training on this split, or accept that 30.5% of your rows were admitted by a judge nobody scored.

**What it does not claim.** This is a claim about provenance, not about accuracy. It does not establish that the judge is wrong. A symbolic checker that cannot parse a valid answer and a judge that waves through an invalid one produce identical columns, and separating them needs the answers themselves. A verification pass re-fetched 398 admitted generations at the pinned revision, every shard checked against the freeze's own SHA-256, and found only 18 where the boxed answer and the published answer both reduce to a single unambiguous number and disagree. Most of the remaining gap is answer-format heterogeneity, a boxed multiple-choice letter against a published value or a published answer carrying several roots at once, which is itself the likeliest reason the symbolic check failed on these rows. That parser is a third instrument in the room, and this project has already published a re-adjudicator whose 186 disagreements were every one its own blindness, so its mismatches are reported as unresolved and never as judge errors. The fallback design is documented by the dataset's authors and is a reasonable answer to a checker that cannot parse every valid form; what is measured here is that its result is unauditable from the columns as shipped.

### AEL-2026-015 - measurement, 2026-09-10

**Dataset.** [`nebius/SWE-rebench-openhands-trajectories`](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories) at `35455389`

Selective prediction does not repair the generated-test proxy of AEL-2026-008; it makes the shortfall larger. The proxy emits a bare verdict with no confidence attached, so the only available gate is a second signal, gen_tests_correct. Abstaining unless the generated tests were themselves judged correct retains 30.1% of rows and lifts raw agreement from 51.4% to 65.4%, which is not a gain: abstention changes the population and therefore the baseline, and the majority class flips from unresolved at 54.2% to resolved at 70.4%. Scored against the best constant policy on the rows it keeps, the proxy goes from 2.9 points short, 95% CI [0.4, 5.5], to 5.0 points short, [3.2, 6.6]. On the 69.7% it would have abstained on it is 19.5 points short, [16.8, 22.2]. No arm clears its baseline and every interval lies entirely below zero. Always-fail is the right comparator only while unresolved is the commoner label; on the retained rows it scores 29.6%, so the proxy's apparent win over it there is a win over a policy nobody would run.

**Check it.** `make corpus`

**If you use this dataset.** Before reporting that abstention improved a grader, recompute the baseline on the retained subset. An accuracy quoted at partial coverage is not comparable to the same accuracy at full coverage, because the population and its majority class both moved. Here the confident subset is the easier subset, and the bar rose further than the proxy did.

**What it does not claim.** A measurement of one abstention rule on one dataset, not a claim that selective prediction cannot work. The gate is itself an adjudicated label that would not be available at the moment a release decision is made, so this is the best case for abstention on this proxy rather than a deployable policy, and the best case still loses. The gate was chosen because it is the only confidence-like signal the dataset ships; no threshold sweep was run, because a binary verdict has nothing to sweep. Intervals are clustered over the 5,870 instances and family-adjusted across the three arms. Compare AEL-2026-016, which asks the same question of graders that do emit a score and reaches the same answer by a different route.

### AEL-2026-016 - measurement, 2026-09-10

**Dataset.** [`FUSE-verifiers/HLE-Verifications`](https://huggingface.co/datasets/FUSE-verifiers/HLE-Verifications) at `e838b3dd`

Forcing the seven graders of AEL-2026-013 to abstain where they are least confident does not rescue them. Ranking each grader's questions by the standard deviation of the scores it gave and keeping the most confident quarter, 6 of 7 point estimates rise, and yet 5 of 7 intervals contain 0.5 at 25% coverage against 4 of 7 at full coverage. Abstention leaves the family further from a usable verdict, not closer, because the question is the independent unit and abstaining discards it: the interval widens faster than the estimate rises. Only gemini-3-flash, 0.581 to 0.657 [0.591, 0.718], and gpt5.2-high, 0.547 to 0.607 [0.514, 0.697], clear chance on the quarter they keep. The first draft of this analysis reported gpt5.2-high at 0.833 and was an artifact of the tie-break: three of the four confidence rules are integer-valued, so the coverage cutoff lands inside a block of tied questions, and that draft chose among them by sorting on the AUC being measured. Measured directly, the tie-break alone can move the retained figure by up to 0.657 under top-margin and 0.577 under spread, against 0.002 under the standard deviation rule published here.

**Check it.** `make corpus`

**If you use this dataset.** Score a selective-prediction curve on the unit your interval is computed over, and before believing the curve, measure how far the tie-break at the coverage cutoff could move it on its own. If that width is comparable to the effect you are reporting, you are reporting the tie-break: here it reaches 0.657 under one rule and 0.002 under another, over the same data and the same graders.

**What it does not claim.** Four confidence rules were computed: standard deviation, max minus min, the margin below the top score, and how many responses share the top score. Standard deviation is published because it is the only continuous one and the tie-break can move it by 0.002; the other three are recomputed beside it and no grader clears chance under any of them that does not clear it under this one. Intervals are family-adjusted across 14 claims, seven graders at two retained coverage levels, and are therefore wider than a single-comparison reading. Every caveat on AEL-2026-013 still applies, in particular that gemini-3-flash carries no score on 19,284 of 32,450 responses and is measured on the subset it scored, which is the grader that gains most here. This measures abstention on grader self-confidence, not on an external difficulty signal or a calibrated probability, neither of which this dataset ships. Compare AEL-2026-015, which asks the same question of a proxy with no score to threshold on and reaches the same answer.

## Citing one

Quote the identifier and the date: an identifier alone is ambiguous
once a finding is superseded. `AEL-2026-008 (2026-09-02)` names one
result, at one revision, with one published wording, and the command
beside it re-derives the number from content-free frozen evidence
without trusting this repository's own summary of it.

[The full audits, dataset by dataset.](CORPUS.md) [How to add one.](../docs/contributing-an-audit.md)
