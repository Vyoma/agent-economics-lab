# The corpus: public agent-trajectory datasets, audited

Every dataset here was audited under the same discipline:
content-free evidence frozen at a named revision, checks from the
same family, and a refusal to guess at what the evidence does not
establish, excluded and counted instead. A clean bill
is a result, recorded with the same care as a defect; an auditor that
only ever finds problems is indistinguishable from one that
manufactures them.

Each dataset is an independent public upload; an arm or model name
inside one identifies a set of runs in that dataset, not a number any
vendor published, and nothing here is a measurement of a model.

| dataset | revision | rows | what the audit found |
|---|---|---:|---|
| [tarsur385/swebench-verified-trajectories](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) | `b55979d6` | 5,000 | 1 of 10 arms never confirmed by its cross-check; one duplicated arm pair, labels 91.2% self-consistent ([full audit](OUTCOME_AUDIT.md)) |
| [togethercomputer/CoderForge-Preview-32B…](https://huggingface.co/datasets/togethercomputer/CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories) | `753f0504` | 500 | clean: reward re-derives from the raw logs on all 434 parseable rows |
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
