# Your AI Agent Passed Every Enabled Check. One Required Check Never Ran.

I disabled one required gate at a time across 588 synthetic gate-disablement
comparisons. An engine that redefined completeness around the remaining gates
produced 23 false `SCALE` transitions. A fixed-contract engine refused to decide.

An agent failed the tail-risk gate, so the system returned `ASSIST`.

Then the tail-risk gate was disabled. Every remaining gate passed, and the same
workload returned `SCALE`.

Nothing about the agent improved. The definition of enough evidence got smaller.

## I call this decision-coverage drift

Decision-coverage drift is the failure mode where the definition of sufficient
coverage silently shrinks to match whichever checks remain enabled.

The distinction sounds small:

```text
all enabled checks passed
```

is not the same claim as:

```text
all required checks passed
```

This matters in modular agent systems because checks fail to run for ordinary
reasons. A service times out. A module is disabled during an incident. A team
removes an expensive evaluator. A deployment uses a different configuration than
the one that was reviewed.

If the decision layer infers completeness from the checks that happened to return,
the system has changed the question without changing the answer label.

## The six dimensions in this experiment

Agent Economics Lab treats a scale decision as an economic assurance case. The
controlled fixture requires six dimensions:

1. outcome quality;
2. cost per acceptable outcome;
3. tail cost;
4. absolute business value;
5. value versus a named counterfactual; and
6. runtime call and spend caps.

These are not claimed to be universally sufficient. They are a declared contract
for this experiment.

## Two decision architectures

Both architectures receive the same evidence bundle. The intervention disables
exactly one required gate.

The dynamic-coverage engine recomputes required coverage from the gates that remain:

```text
required coverage = coverage supplied by enabled gates
```

The fixed-contract engine preserves the original six requirements:

```text
required coverage = the declared decision contract
```

If an enabled gate no longer supplies one of those requirements, the fixed-contract
engine returns `INCOMPLETE`.

No evidence field is removed in this benchmark. This is a configuration-ablation
experiment, not a missing-data experiment.

## The controlled result

The benchmark contains 98 deterministic synthetic scenarios. Ninety-six form a
fixed factorial matrix, and two boundary cases isolate unit economics and absolute
business value. Each scenario is evaluated under six single-gate disablements.

That produces 588 comparisons:

```text
dynamic-coverage engine    23 false SCALE transitions
fixed-contract engine       0 false SCALE transitions
fixed-contract refusal    588 INCOMPLETE decisions
```

The 23 transitions are a fixture result. They show that this failure mode exists in
the constructed matrix. They do not estimate how often enterprise systems exhibit
it.

The zero is different. It is an enforced invariant:

```text
if required coverage is not supplied:
    decision = INCOMPLETE
```

The implementation does not discover a universal method for eliminating false
approvals. It guarantees one narrower property: disabling a sole-provider gate
cannot produce `SCALE` while the original coverage contract remains fixed.

## Missing evidence is a separate experiment

Deleting raw records and fields asks a different question. The repository therefore
ships a second benchmark that removes outcome records, cost fields, baseline data,
task-manifest entries, policy thresholds, and a timed-out event without changing
the gates.

In nine controlled boundary cases, four omissions are rejected at the schema or
evidence boundary and mapped operationally to `INCOMPLETE`. Five omissions still
allow an `ASSIST` case to become `SCALE`.

That result exposes a remaining engineering boundary: fixed gate coverage cannot
prove that the underlying records are complete. Explicit zero values, frozen task
and attempt inventories, and source-specific completeness contracts are separate
requirements.

Again, five of nine is not a prevalence estimate. The cases were chosen to make
each omission decision-relevant.

## Reproduce both claims

Both experiments run locally with Python 3.10 or newer and no third-party runtime
packages:

```bash
python3 false_green.py
python3 evidence_ablation.py
```

The repository checks in the complete
[decision-coverage drift protocol](../research/FALSE_GREEN_PROTOCOL.md),
[588 comparison rows](../research/results/decision-coverage-drift/results.csv),
[raw evidence-ablation protocol](../research/EVIDENCE_ABLATION_PROTOCOL.md), and
[nine ablation rows](../research/results/evidence-ablation/results.csv). Tests
verify that regenerated artifacts are byte-identical before publication.

## Three operating rules

No outcome label, no scale.

No named counterfactual, no ROI.

No required coverage, no green.

In implementation terms:

1. Declare the decision contract before evaluating the workload.
2. Bind every result to both an evidence digest and a decision-contract digest.
3. Refuse to issue a bounded decision when required coverage is absent.

Diagnostics can explain. Typed gates can route. Missing requirements must remain
visible.

## What this does not establish

The fixtures are synthetic. They do not establish that 23 is common, that these six
dimensions are sufficient for every enterprise, or that tail-risk and runtime gates
are the checks most often omitted.

The paired configuration frontier is also a controlled fixture. Its selected
winner's observed cost and rank are post-selection exploratory evidence. Production
generalization requires a held-out confirmation set, nested selection and
evaluation, or an independent frozen replication.

The next operational step is to make the burden of proof explicit, then test it on
permissioned real workflows with frozen rubrics, complete failed runs, full cost
attribution, and independent reproduction.

The code, protocols, generated rows, and limitations are in
[Agent Economics Lab](https://github.com/Vyoma/agent-economics-lab).
