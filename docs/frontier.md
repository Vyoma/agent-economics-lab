# Economic Assurance Frontier

## The decision it makes

The frontier answers one bounded question:

> Which tested agent configuration is the lowest-cost candidate that stays within
> a predeclared harmful-transition tolerance on the same fingerprinted tasks?

The unit of comparison is a paired task identity, not an aggregate dashboard window.
The reference and every candidate must contain exactly the same task IDs, SHA-256
input digests, and rubric versions. Missing or changed tasks and planned arms return
`INCOMPLETE`; the tool never silently drops an unmatched failure.

## Run it

```bash
python3 -m agent_economics frontier \
  examples/compute-frontier/manifest.json \
  --output-dir /tmp/agent-economics-frontier
```

The output directory contains:

- `frontier.md`, a review-ready decision record;
- `frontier.json`, the machine-readable result; and
- `frontier.svg`, a dependency-free cost-quality plot.

## Frozen plan

The manifest names the complete experiment family before comparison:

```json
{
  "schema_version": 1,
  "experiment_id": "support-budget-frontier-v1",
  "reference_arm": "premium-8-step",
  "arms": {
    "premium-8-step": "arms/premium-8-step.json",
    "balanced-4-step": "arms/balanced-4-step.json"
  },
  "max_breakage_rate": 0.05,
  "min_cost_reduction_rate": 0.25,
  "confidence_level": 0.95,
  "bootstrap_samples": 5000,
  "seed": 20260722,
  "min_paired_tasks": 150,
  "task_manifest": "task-manifest.json",
  "task_manifest_digest": "8ab1d32aff8ff1d42fa3d7fecff28bc36548dd1c9905b972a0ed701c874298d4"
}
```

Do not remove a candidate after seeing its result. The target nominal familywise
error budget is computed from the complete planned candidate count.

## Required evidence per arm

The plan references one shared task manifest with a SHA-256 input digest and rubric
version per `task_id`. Each arm is a normalized JSON evidence bundle with:

- one or more trace events per `task_id`;
- exactly one outcome per `task_id`;
- exact coverage of the shared task-manifest IDs;
- the same baseline and economic policy as the reference;
- explicit business value, human minutes, remediation cost, and incident loss;
- `direct_cost_usd` for every non-priced event, including `0.0` when the event is
  explicitly free or included; and
- a rate card and explicit nonnegative token counts for model events that omit
  direct cost.

An absent non-model cost is unknown, not free. Frontier evaluation fails closed on
that ambiguity.

## Quality rule

A harmful transition is a task where the reference outcome is acceptable and the
candidate outcome is unacceptable. The estimand is the absolute rate of this joint
event in the full paired task population, not the rate conditional on reference
success. For each candidate, the tool computes an exact one-sided
Clopper-Pearson upper bound.

This matters when no regressions were observed. With a small sample, the upper bound
remains large; zero observed failures is not treated as zero risk.

## Cost rule

Effective cost includes:

```text
model and tool spend + human review + remediation + incident loss
```

The tool resamples paired task rows with a fixed seed and computes a one-sided lower
percentile bound for the candidate's cost-reduction rate. Pairing preserves shared
task difficulty between the candidate and reference.

The target nominal familywise alpha is divided across both quality and cost tests
for every planned candidate. The exact quality endpoint receives this adjustment;
the percentile-bootstrap cost endpoint remains approximate and includes Monte Carlo
error. Plans must provide at least 20 expected resamples in the adjusted lower tail.
A candidate is eligible only when:

1. its normal assurance decision is `SCALE`;
2. its exact breakage upper bound is within tolerance;
3. its cost-reduction lower bound clears the target; and
4. the reference and complete experiment family pass all completeness rules.

The selected arm is the lowest observed full-cost arm among eligible tested
candidates. The tool does not interpolate an untested continuous budget threshold.

## Design requirements for real studies

- Freeze task input digests, rubric versions, candidate family, margins, and the
  analysis plan before
  inspecting results.
- Randomize or counterbalance route order when making causal claims.
- Preserve failed and timed-out runs; missing failures create survivorship bias.
- Record model, prompt, tool, policy, and orchestration versions in trace arguments.
- Use stable task IDs and prevent duplicate or near-duplicate tasks from inflating N.
- Predeclare subgroup checks when aggregate quality could hide a critical regression.
- Treat bootstrap intervals as sampling uncertainty under the observed design, not a
  repair for biased labels, confounding, or incomplete cost capture.

## Claim boundary

The frontier can say which tested configuration satisfied a declared rule on one
frozen matched dataset. Without randomized or counterbalanced assignment it reports
a paired association, not a causal effect. It does not validate the outcome rubric,
guarantee production generalization, or certify future provider behavior.
