# Findings index

Every audit result this project has published, with a stable
identifier, the date it was first published, the command that checks
it, and the scope it does not claim.

**12 standing: 6 defects, 4 measurements, 2 clean bills.** Clean bills are listed here with the same weight as defects, because
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
| `AEL-2026-008` | 2026-09-02 | measurement | `SWE-rebench-openhands-trajectories` | Model-generated tests, measured against adjudicated outcomes on the 31,389 rows carrying both signals, agree at Cohen's kappa 0.062 |
| `AEL-2026-009` | 2026-09-03 | measurement | `PostTrainBench-Trajectories` | Runs the contamination judge flagged score +0.209 accuracy above clean runs when pooled, which reads as cheating paying twenty points |
| `AEL-2026-010` | 2026-09-03 | defect | `PostTrainBench-Trajectories` | 260 of 1,842 runs carry no usable outcome: 208 ship no metrics file and 52 ship one that is not valid JSON |
| `AEL-2026-011` | 2026-09-03 | measurement | `cogym-real-trajectories` | Across 191 sessions where the same person rated both the artifact and their overall satisfaction, the two ratings agree exactly 50% of the time... |
| `AEL-2026-012` | 2026-09-03 | defect | `cogym-real-trajectories` | The communication rating is present on 50 of 228 sessions and the artifact rating on 191; only overall satisfaction is on every session |

## The findings in full

### AEL-2026-001 - defect, 2026-08-31

**Dataset.** [`tarsur385/swebench-verified-trajectories`](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) at `b55979d6`

The gemini-3-pro arm reports info.resolved true on all 500 tasks while its own info.scores.resolved reads "unknown" on all 500, so its 100% resolution rate is confirmed by nothing in the dataset. Nine of those runs record at most one API call and no spend.

**Check it.** `make outcome-audit && make verify-upstream`

**What it does not claim.** A statement about this third-party upload at this revision. Not a measurement of any model, and not a claim that the dataset is wrong: the cross-check field the dataset itself ships is what reveals it.

### AEL-2026-002 - measurement, 2026-08-31

**Dataset.** [`tarsur385/swebench-verified-trajectories`](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) at `b55979d6`

The gpt-5.2-codex and gpt-5.2-high arms carry byte-identical transcripts on all 500 tasks, and info.resolved disagrees between the copies on 44 of them: the label agrees with itself 91.2% of the time on identical input, against a 20.6-point spread across the nine scored arms.

**Check it.** `make outcome-audit && make verify-upstream`

**What it does not claim.** Test-retest, filed as such. Repeatability is not validity: an instrument that scores identical inputs identically every time can be systematically wrong about all of them. What causes the 8.8% is not established here.

### AEL-2026-003 - clean bill, 2026-09-01

**Dataset.** [`togethercomputer/CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories`](https://huggingface.co/datasets/togethercomputer/CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories) at `753f0504`

Clean bill. The published reward re-derives from the raw evaluation logs on every one of the 434 rows the parser could fully read, with no disagreements.

**Check it.** `make corpus`

**What it does not claim.** The strongest check in this corpus, because the dataset ships the graded-test lists and raw logs a re-derivation needs. It says nothing about the 66 rows the parser could not fully read, which are excluded and counted rather than assumed.

### AEL-2026-004 - defect, 2026-09-02

**Dataset.** [`SWE-bench/SWE-smith-trajectories`](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) at `08e109b4`

The patch column is not row-aligned. 266 distinct non-empty patch contents, covering 1,933 rows, each appear verbatim under instances from two or more different repositories; a re-fetch of every row in the first 50 hash-ranked groups found 50 of 50 are non-trivial unified diffs and 34 contain rows whose patch touches paths foreign to the instance's repository.

**Check it.** `make corpus && python3 research/corpus/patch_check.py`

**What it does not claim.** An auxiliary-column defect in the official SWE-bench organisation's training-trajectory release. The model was fine-tuned on messages, not patch, so this is not evidence against the training signal or the labels, which are clean across all 18,167 duplicate-transcript groups.

### AEL-2026-005 - defect, 2026-09-02

**Dataset.** [`SWE-bench/SWE-smith-trajectories`](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) at `08e109b4`

The xml split contains 2,255 rows that are verbatim duplicates of other rows in the same split, identical in id, transcript and label, and 14,984 transcripts appear byte-identically in both the tool and xml splits, so training on both sees those examples twice. The dataset card's prose describes 5,017 trajectories where the dataset serves 76,002 rows.

**Check it.** `make corpus`

**What it does not claim.** Duplication and a card-versus-content discrepancy. Not a claim that either is unintentional.

### AEL-2026-006 - defect, 2026-09-01

**Dataset.** [`JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified`](https://huggingface.co/datasets/JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified) at `dd79e254`

The resolved column is present and populated on none of the 1,785 rows, so a consumer computing a resolution rate from this dataset gets no signal from the field that names one.

**Check it.** `make corpus`

**What it does not claim.** A statement about this revision. Labels may exist elsewhere; the finding is that this column carries none.

### AEL-2026-007 - clean bill, 2026-09-02

**Dataset.** [`nebius/SWE-agent-trajectories`](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) at `68195a14`

Clean bill across 80,036 rows. Every resolved row carries a non-empty patch and non-empty evaluation logs; empty patches and empty logs occur only on unresolved rows, under exactly the exit statuses that should produce them; no duplicate transcripts.

**Check it.** `make corpus`

**What it does not claim.** Coherence, weaker than AEL-2026-003's re-adjudication, because this dataset does not ship the graded-test lists a re-derivation would need.

### AEL-2026-008 - measurement, 2026-09-02

**Dataset.** [`nebius/SWE-rebench-openhands-trajectories`](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories) at `35455389`

Model-generated tests, measured against adjudicated outcomes on the 31,389 rows carrying both signals, agree at Cohen's kappa 0.062. Conditioned on the generated tests themselves being judged correct, kappa is 0.101 with precision 0.729 on 9,444 rows; where they were judged incorrect, kappa is 0.020. The best case is a sixth of the 0.60 kappa floor this package requires of an outcome instrument.

**Check it.** `make corpus`

**What it does not claim.** A measurement of the generated-test method as an outcome instrument on this dataset, not a defect of the dataset: recording both signals side by side is what made the measurement possible. The signal is absent on 35,685 rows, so nothing here extrapolates to them, and this is one dataset in one domain.

### AEL-2026-009 - measurement, 2026-09-03

**Dataset.** [`aisa-group/PostTrainBench-Trajectories`](https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) at `39d3fcd7`

Runs the contamination judge flagged score +0.209 accuracy above clean runs when pooled, which reads as cheating paying twenty points. Holding benchmark fixed and weighting by size, the difference is +0.018, smaller by a factor of 11.5, and contaminated runs beat clean ones in only 2 of the 5 benchmarks with enough of both to compare. Contamination concentrates on bfcl, which carries 39% of its own runs flagged, 47% of all contamination, and a clean-run mean of 0.673 against a corpus where most benchmarks sit near 0.2.

**Check it.** `make corpus`

**What it does not claim.** A statement about a confound in this dataset, not about whether contamination helps in general: the stratified estimate is observational, benchmarks are not randomised across runs, and the flags come from an unvalidated judge. It does establish that the pooled comparison anyone would compute first is an order of magnitude too large.

### AEL-2026-010 - defect, 2026-09-03

**Dataset.** [`aisa-group/PostTrainBench-Trajectories`](https://huggingface.co/datasets/aisa-group/PostTrainBench-Trajectories) at `39d3fcd7`

260 of 1,842 runs carry no usable outcome: 208 ship no metrics file and 52 ship one that is not valid JSON. A further 331 runs carry no contamination verdict, so they are neither clean nor flagged, and the dataset does not say how a consumer should treat them.

**Check it.** `make corpus`

**What it does not claim.** A completeness statement about this revision. Not a claim that the missing runs failed, which is precisely what cannot be determined from an absent or unparseable metrics file.

### AEL-2026-011 - measurement, 2026-09-03

**Dataset.** [`SALT-NLP/cogym-real-trajectories`](https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) at `729096dc`

Across 191 sessions where the same person rated both the artifact and their overall satisfaction, the two ratings agree exactly 50% of the time and reach quadratic-weighted kappa 0.625, disagreeing by two points or more on 9% of sessions. That is barely above the 0.60 kappa floor this package requires of an automated outcome instrument.

**Check it.** `make corpus`

**What it does not claim.** These are different questions, not the same question asked twice, so divergence is expected and this is not a reliability or test-retest measurement. What it bounds is how much a single number called 'the human rating' carries: any instrument validated against human agreement inherits whichever question was asked, and datasets rarely record which. One platform, three tasks, 228 sessions.

### AEL-2026-012 - defect, 2026-09-03

**Dataset.** [`SALT-NLP/cogym-real-trajectories`](https://huggingface.co/datasets/SALT-NLP/cogym-real-trajectories) at `729096dc`

The communication rating is present on 50 of 228 sessions and the artifact rating on 191; only overall satisfaction is on every session. A consumer computing communication quality from this dataset computes it over 22% of it, and the schema does not distinguish 'not rated' from a rating.

**Check it.** `make corpus`

**What it does not claim.** A completeness statement about optional fields the dataset card documents as optional. Not a claim the absences are unintentional; the finding is that the resulting denominators differ by field and nothing in the data announces it.

## Citing one

Quote the identifier and the date: an identifier alone is ambiguous
once a finding is superseded. `AEL-2026-008 (2026-09-02)` names one
result, at one revision, with one published wording, and the command
beside it re-derives the number from content-free frozen evidence
without trusting this repository's own summary of it.

[The full audits, dataset by dataset.](CORPUS.md) [How to add one.](../docs/contributing-an-audit.md)
