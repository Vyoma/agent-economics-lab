# Public SWE-bench economic case

This is a non-synthetic, content-redacted economic case built from 40 public
mini-SWE-agent trajectories on 20 paired SWE-bench Verified tasks.

It compares:

- candidate: `claude-opus-4.6`;
- reference: `claude-4.5-haiku-high`;
- agent harness: mini-SWE-agent; and
- outcome: the published SWE-bench hidden-test result.

The source is the MIT-licensed
[public trajectory dataset](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories/tree/b55979d6b24850b72ae4d80f912526280cd6058a)
at revision `b55979d6b24850b72ae4d80f912526280cd6058a`.

## Result

| Measure | Opus candidate | Haiku reference |
|---|---:|---:|
| Resolved | 14/20 (70%) | 11/20 (55%) |
| Published estimated spend | $8.44 | $5.37 |
| Mean spend per attempt | $0.42 | $0.27 |
| Spend per resolved task | $0.60 | $0.49 |
| Published API calls | 526 | 1,181 |

Opus produced four beneficial outcome transitions and one harmful transition
against Haiku on the same tasks. It improved observed resolution by 15 percentage
points while increasing mean spend by 56.9%.

The AssuranceCase says `STOP`. The paired frontier says `HOLD`.

That is not a contradiction. The public run shows better observed quality and fewer
calls, but not cheaper acceptable outcomes. With one observed harmful transition
in 20 pairs, the exact one-sided upper bound is 24.9%, above the predeclared 5%
limit. No dollar value is assigned to a benchmark resolution, so the case cannot
claim that the extra three net resolutions justify the extra spend.

## What is observed and what is declared

| Field | Treatment |
|---|---|
| Outcome | Observed `info.resolved`, cross-checked against `info.scores.resolved` |
| Run spend | Observed `info.model_stats.instance_cost`, labeled as a client estimate |
| API calls | Observed `info.model_stats.api_calls` |
| Task identity | Public SWE-bench instance ID |
| Business value | Conservatively credited as zero because the public benchmark does not publish it; this is not a value estimate |
| Human, remediation, incident cost | Explicitly zero and outside this benchmark scope |
| Counterfactual | Haiku on the identical 20 task IDs |
| Quality and cost limits | Frozen from the paired reference, except net value, which must be non-negative |

The source manifest stores no prompt, reasoning, tool output, patch, or response.
It stores the complete upstream file digest so a reviewer can retrieve and verify
the original public trajectory.

## Outcome-blind selection

The task selection rule is:

1. intersect task IDs present for both fixed model labels;
2. sort lexicographically;
3. take every twentieth task from offset zero; and
4. keep the first 20.

The rule uses no outcome or cost field. This case is descriptive and small. It does
not estimate population-wide performance or prove production ROI.

The manifest freezes SHA-256 digests for both the 500-task eligible universe and
the selected 20 task IDs. The digest encoding is newline-terminated, sorted UTF-8
task IDs.

## Reproduce

```bash
make public-case
```

The build emits:

- [content-free source manifest](runs.json);
- [candidate AssuranceCase](assurance-case.md);
- [paired frontier report](frontier/frontier.md);
- normalized evidence for both arms in `arms/`; and
- source and decision digests in every report.

`freeze_source.py` regenerates `runs.json` from downloaded upstream files. The
checked-in test suite rebuilds every published report byte for byte. Large
normalized arm bundles are generated in `/tmp` and deliberately kept out of Git.

For example, download the two pinned model folders with the Hugging Face CLI and
point the freezer at `swebench_verified_raw`:

```bash
hf download tarsur385/swebench-verified-trajectories \
  --repo-type dataset \
  --revision b55979d6b24850b72ae4d80f912526280cd6058a \
  --include "swebench_verified_raw/claude-opus-4.6/*/*.traj.json" \
  --include "swebench_verified_raw/claude-4.5-haiku-high/*/*.traj.json" \
  --local-dir /tmp/public-swebench

python3 examples/public-swebench/freeze_source.py \
  --raw-root /tmp/public-swebench/swebench_verified_raw
```
