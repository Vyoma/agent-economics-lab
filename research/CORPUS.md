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
