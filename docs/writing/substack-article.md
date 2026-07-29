# Your AI Agent Passed Every Eval. One Required Eval Never Ran.

**Subtitle:** I disabled one required gate across 588 controlled comparisons. A
system that let its evidence contract shrink approved 23 unchanged workloads. A
fixed contract refused all 588.

An AI agent failed its tail-cost check, so the decision engine kept it in assisted
mode.

Then I disabled the tail-cost evaluator.

Every remaining check passed. The same workload, with the same evidence, was
approved to scale.

Nothing about the agent improved. The definition of enough evidence got smaller.

That is the most dangerous kind of green dashboard: one that is mathematically
correct about the checks it received and operationally wrong about the decision it
claims to support.

I built a small open-source experiment to make this failure reproducible. The
result is narrow, but it is useful:

| Decision architecture | False `SCALE` transitions | Refusals |
|---|---:|---:|
| Requirements follow enabled checks | 23 | 0 |
| Requirements stay fixed | 0 | 588 |

The experiment does not show that 23 is a common production failure rate. It
shows that an unchanged agent can receive a better decision when a required
evaluator disappears.

The fix is not another dashboard. It is a decision contract that stays fixed when
the evaluation stack changes.

## Evals are necessary. They are not the deployment decision.

An excellent recent article in Lenny's Newsletter called
[evals the modern version of a PRD](https://www.lennysnewsletter.com/p/how-braintrust-uses-ai-agents-evals).
I agree. Evals make product expectations executable.

Agent evals also have to inspect more than a final answer. Anthropic's guide to
[evaluating AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
distinguishes the full trajectory from the actual outcome in the environment.
That distinction matters. An agent can say it booked a flight without a
reservation existing. It can produce a correct patch after an expensive sequence
of retries. It can pass a task while creating a new operational tail.

But even a rigorous eval suite leaves a second question:

> Given the evidence we have, has this agent earned more autonomy, traffic, or
> budget?

That is not only a model-quality question. It is a bounded operating decision.

The agent may pass quality evals and still cost more per acceptable outcome. It may
create value on average while exceeding a hard per-task spend cap. It may look
better than doing nothing while remaining worse than the workflow it will replace.
It may pass every check that ran while a required check is missing.

I use **decision-coverage drift** for that last failure mode:

> The definition of sufficient evidence silently shrinks to match whichever
> checks happen to run.

The difference is one word:

```text
all enabled checks passed
```

is not the same claim as:

```text
all required checks passed
```

## The intervention: disable exactly one required gate

I created 98 deterministic scenarios. Ninety-six form a factorial matrix, and two
boundary cases isolate unit economics and absolute business value.

Each scenario has a fixed contract with six required claims:

1. Outcome quality
2. Cost per acceptable outcome
3. Tail cost
4. Absolute business value
5. Value versus a named counterfactual
6. Runtime call and spend caps

These are not universal requirements for every agent. They are the declared
contract for this experiment. A healthcare or financial workflow would need
additional domain-specific claims.

For each scenario, I disabled one gate at a time. That produced 588 comparisons.
The evidence did not change. Only the composition of the evaluation system
changed.

I sent each comparison through two architectures.

The first architecture recomputes required coverage from the gates that remain:

```text
required coverage = coverage supplied by enabled gates
```

The second preserves the original contract:

```text
required coverage = claims declared before evaluation
```

If a required claim loses its sole provider, the fixed-contract system returns
`INCOMPLETE`.

The complete result:

```text
requirements follow enabled checks    23 false SCALE transitions
requirements stay fixed                0 false SCALE transitions
fixed-contract refusals              588 INCOMPLETE decisions
```

The 23 is an empirical result from a constructed fixture. It proves existence, not
prevalence.

The zero has a different status. It comes from a software invariant:

```text
if required coverage is not supplied:
    decision = INCOMPLETE
```

The implementation does not eliminate false approvals in general. It guarantees
one precise property:

> Disabling a sole-provider gate cannot produce `SCALE` while the original
> decision contract remains fixed.

That is small enough to test, useful enough to enforce, and honest enough to
defend.

## A fixed contract is still not enough

The first experiment removes evaluators. It does not remove raw evidence.

Those are different failures.

A gate can run successfully on an incomplete export. A missing cost can become
zero. A timed-out attempt can disappear from the dataset. A digest can prove which
bytes were evaluated, but it cannot prove that an upstream system supplied every
record that should exist.

So I built a second experiment. This one deletes records and fields while keeping
the decision contract fixed.

Across nine deliberately chosen boundary cases:

- four omissions were rejected at the schema or evidence boundary;
- five omissions still changed an `ASSIST` decision to `SCALE`.

Those five transitions came from two source gaps:

- optional cost fields could be interpreted as zero;
- a deleted timed-out execution was undetectable without an independent run
  ledger.

Again, five out of nine is not a prevalence estimate. These cases were selected
because each omission could change the decision.

The practical lesson is that two completeness contracts are required:

1. **Decision completeness:** Did every declared claim receive coverage?
2. **Source completeness:** Did every expected task, attempt, event, and field
   arrive from the source?

One cannot substitute for the other.

## Then I tried the framework on public agent trajectories

Synthetic counterexamples are useful for isolating a mechanism. They are not a
substitute for a non-synthetic case.

I therefore built a public case from 40 real
[mini-SWE-agent trajectories](https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories/tree/b55979d6b24850b72ae4d80f912526280cd6058a)
covering 20 paired SWE-bench Verified tasks.

The candidate was Claude Opus 4.6. The reference was Claude Haiku 4.5. Both were
evaluated on the same task IDs using published hidden-test outcomes and published
client-estimated spend.

| Measure | Opus candidate | Haiku reference |
|---|---:|---:|
| Resolved | 14/20 | 11/20 |
| Mean spend per attempt | $0.42 | $0.27 |
| Spend per resolved task | $0.60 | $0.49 |
| Published API calls | 526 | 1,181 |

Opus resolved three more tasks and made fewer API calls. It also cost 56.9% more
per attempt and 23.3% more per resolved task.

The decision engine returned `STOP`. The paired uncertainty-aware frontier
returned `HOLD`.

That is not a contradiction. The candidate showed better observed quality, but it
did not show cheaper acceptable outcomes. One harmful transition in only 20 pairs
left the exact one-sided uncertainty bound above the predeclared limit. The public
benchmark also assigns no dollar value to a resolved task, so the evidence cannot
establish that three net additional resolutions justify the extra spend.

The correct answer was not "Opus is bad." It was:

> This evidence does not support the bounded scale claim that was requested.

That is what a useful decision system should say when performance is promising but
the claim is too strong for the evidence.

The public case is still limited. It is a small benchmark sample, not enterprise
ROI. It excludes human review, remediation, incident loss, and production value.
Prompts, reasoning, patches, and tool output are not republished. Every retained
trajectory is instead bound to its public source path and SHA-256 digest.

## The engineering problem is evidence composition

A decision contract is not a PDF that everyone forgets after review. It has to
survive a modular production system.

Teams change models, evaluators, observability vendors, rate cards, and local
policies. If every source adapter also decides what evidence means, requirements
will drift with the plumbing.

The open-source implementation therefore separates five layers:

```text
source export
    -> canonical economic evidence + digest
    -> typed, versioned checks
    -> fixed decision contract + digest
    -> INCOMPLETE / SCALE / ASSIST / STOP
```

I added two concrete source boundaries to test that separation:

- a Claude Code JSONL adapter that deduplicates streamed fragments and refuses
  incomplete price, delegation, or tool-call inventories;
- one pinned OpenTelemetry GenAI mapper exercised against content-safe Langfuse
  and Arize OpenInference fixtures.

The OpenTelemetry adapter only decodes economic attributes. It does not ingest
prompt text, responses, tool arguments, or tool results. Unknown operations,
unapproved trace-to-task mappings, unresolved parents, missing usage, and
incomplete rate cards produce `INCOMPLETE`.

This does not mean it supports every vendor export. It proves conformance to one
explicitly pinned contract across two independently maintained shapes. The
limitation is part of the artifact.

That boundary is intentional. Modularity should make components replaceable
without making the burden of proof replaceable.

## Copy this one-page decision contract

For one workload, before looking at the candidate result, write down:

| Contract field | Question |
|---|---|
| Unit of work | What exactly is one attempt? |
| Acceptable outcome | What observable state counts as success? |
| Population | Which users, tasks, and operating conditions are covered? |
| Counterfactual | What real process is the agent replacing? |
| Cost boundary | Which model, tool, human, remediation, and incident costs count? |
| Required claims | Which quality, value, tail, and runtime claims must hold? |
| Thresholds | What must be true before the result is known? |
| Failure route | Does a failed gate mean `ASSIST` or `STOP`? |
| Evidence inventory | Which tasks, attempts, events, and fields must exist? |
| Owner and expiry | Who owns the claim, and when must it be rerun? |

Then allow only four outputs:

| Decision | Meaning |
|---|---|
| `INCOMPLETE` | A required claim or source-completeness guarantee is missing. |
| `SCALE` | Evidence is complete and every scale gate passes. |
| `ASSIST` | A declared gate failed, so human oversight or tighter limits remain. |
| `STOP` | A declared stop condition failed. |

This is an executable version of an
[assurance case](https://csrc.nist.gov/glossary/term/assurance_case): a bounded
claim connected to evidence, argument, and assumptions.

Each result should carry both an evidence digest and a decision-contract digest.
If a team intentionally changes the contract, the second digest changes. The new
result may be valid, but it is visibly making a different claim.

## The Monday morning test

Choose one agent workflow your team wants to expand. Put the product owner, an
engineer, and the person accountable for cost or risk in the same room.

1. Define one unit of work and one observable acceptable outcome.
2. Name the workflow the agent will actually replace.
3. Count failed attempts, review, remediation, and tail events in the cost
   boundary.
4. Freeze the required claims, thresholds, and failure routes before examining
   the candidate result.
5. Freeze the expected task and attempt inventories.
6. Disable one required evaluator.
7. Delete one failed execution event.

If either deletion can improve the decision, the dashboard has not earned the
right to authorize scale.

## Three rules

No outcome label, no scale.

No named counterfactual, no ROI.

No required coverage, no green.

The full code, protocols, generated rows, public case, tests, conversion contracts,
and limitations are in
[Agent Economics Lab](https://github.com/Vyoma/agent-economics-lab).

You can reproduce the two counterexamples and the public case locally:

```bash
python3 false_green.py
python3 evidence_ablation.py
make public-case
```

The project runs with Python 3.10 or newer and has no third-party runtime
dependencies.

The question is not whether an agent passed the checks that happened to run.

It is whether the evidence is complete enough for the decision we are about to
make.

---

*Vyoma Gajjar is a principal AI architect and educator who builds enterprise agent
systems and adoption programs. Her open-source work focuses on agent evaluation,
operating economics, evidence contracts, and the gap between a promising result
and a decision an organization can defend.*
