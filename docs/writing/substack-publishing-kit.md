# Substack publishing kit

## Use this title

**Your AI Agent Passed Every Eval. One Required Eval Never Ran.**

## Subtitle

I disabled one required gate across 588 controlled comparisons. A system that let
its evidence contract shrink approved 23 unchanged workloads. A fixed contract
refused all 588.

## Why this is the right lead

The article is not framed as a response to a rejection. It is a compact applied
research contribution:

- one named failure mode;
- one controlled intervention;
- two decision architectures;
- one enforceable invariant;
- one separate boundary experiment;
- one non-synthetic public case;
- code, protocols, data, tests, and limitations.

That shape serves product readers and makes technical judgment legible to research
and applied AI labs. The article demonstrates the work instead of announcing an
interest in the work.

## Publication details

- Suggested slug: `ai-agent-required-eval-never-ran`
- Estimated reading time: 12 minutes
- Suggested Substack section: Applied AI Systems
- Suggested tags: AI agents, AI evaluation, applied AI, product management,
  open source
- Primary audience: product leaders, research engineers, agent engineers
- Secondary audience: enterprise AI architects, FinOps, risk, and governance

## Substack preview

I disabled one required gate across 588 controlled comparisons. A system that let
its evidence contract shrink approved 23 unchanged workloads. A fixed contract
refused all 588. Then I tested the boundary on public SWE-bench agent trajectories.

## Search description

An executable decision contract for AI agents that prevents missing evaluators from
silently improving a scale decision, with reproducible experiments and a public
SWE-bench case.

## Notes text for the first hour

Your agent passed every eval that ran.

That is not the same as every required eval running.

I built the counterexample: 588 gate disablements, 23 false `SCALE` transitions
when requirements followed enabled checks, and zero when the decision contract
stayed fixed.

The article includes the code, exact claim boundary, a raw-evidence deletion
experiment, and a non-synthetic SWE-bench case.

[SUBSTACK URL]

## Header image brief

A clean editorial diagram on a warm white background. On the left, six compact
cards labeled Outcome, Unit Cost, Tail Cost, Business Value, Counterfactual, and
Runtime Caps feed a fixed rectangular Decision Contract. The Tail Cost card is
faded and marked Disabled, but Tail Cost remains clearly visible inside the
contract. On the right, the output is a large amber `INCOMPLETE`. Use black,
off-white, muted amber, and one dark blue accent. No robot, brain, circuit board,
vendor logo, coins, or neon gradient.

Headline inside the image:

> A missing check is not a passing check.

Recommended alt text:

> Six evaluator cards feed a fixed AI agent decision contract. The Tail Cost
> evaluator is disabled, but its requirement remains, so the decision is
> INCOMPLETE.

## One call to action

Do not split attention across newsletter signup, consulting, a course, and the
repository. End with one action:

> Run the counterexample, copy the decision contract, and try to break the
> invariant on one real workflow.

Link it to:

`https://github.com/Vyoma/agent-economics-lab`

## Reply to Lenny

Send only after the Substack URL and every GitHub link work in a signed-out browser.

**To:** lenny@lennyrachitsky.com

**Subject:** I took your advice and ran the experiment

Hi Lenny,

You encouraged me to run with the idea, so I did.

I turned it into a reproducible article and open-source artifact about a subtle
agent-evaluation failure: "every enabled check passed" is not the same as "every
required check ran."

I disabled one required gate across 588 controlled comparisons. A decision engine
that let its evidence requirements shrink produced 23 false scale approvals. A
fixed-contract engine refused all 588. I also tested the claim boundary with raw
evidence deletions and a non-synthetic public SWE-bench case.

Article: [SUBSTACK URL]

Code, protocols, data, and tests:
https://github.com/Vyoma/agent-economics-lab

No ask. I wanted to close the loop and thank you for the push.

Vyoma

## LinkedIn launch post

Your AI agent passed every eval.

One required eval never ran.

I wanted to know whether that distinction could change a real scale decision, so I
built the counterexample.

I disabled one required gate at a time across 98 deterministic scenarios and six
required claims: 588 comparisons in total.

Two engines received the same evidence.

Engine A let required coverage follow whichever checks remained enabled.

Engine B kept the original decision contract fixed.

The result:

- Engine A produced 23 false `SCALE` transitions.
- Engine B produced zero.
- Engine B returned `INCOMPLETE` for all 588 missing-coverage cases.

Nothing about the agent improved. Only the definition of enough evidence got
smaller.

Then I attacked the boundary.

Deleting raw records exposed five cases where missing cost or execution evidence
could still improve an `ASSIST` decision to `SCALE`. So fixed gate coverage is not
enough. You also need a source-completeness contract.

Finally, I ran the framework on 40 public mini-SWE-agent trajectories across 20
paired SWE-bench Verified tasks. The more capable candidate resolved more tasks,
but the evidence still did not justify the requested scale claim.

The article includes:

- the failure definition;
- the controlled protocol and generated rows;
- the enforced invariant;
- the public case;
- the one-page decision contract;
- the limitations; and
- commands to reproduce everything locally.

No outcome label, no scale.

No named counterfactual, no ROI.

No required coverage, no green.

Article: [SUBSTACK URL]

Code: https://github.com/Vyoma/agent-economics-lab

#AIAgents #AIEvals #AppliedAI #ResearchEngineering #OpenSource

## X launch thread

**Post 1**

Your AI agent passed every eval.

One required eval never ran.

I disabled one required gate across 588 controlled comparisons. A system that let
its evidence contract shrink approved 23 unchanged workloads. A fixed contract
refused all 588.

[SUBSTACK URL]

**Post 2**

The failure is simple:

`all enabled checks passed`

is not:

`all required checks passed`

I call it decision-coverage drift. The agent does not improve. The definition of
enough evidence gets smaller.

**Post 3**

The invariant:

```text
if required coverage is not supplied:
    decision = INCOMPLETE
```

This does not eliminate false approvals in general. It guarantees one narrower
property: disabling a sole-provider gate cannot produce `SCALE` under the original
contract.

**Post 4**

I also deleted raw records.

Four of nine omissions were refused. Five still improved `ASSIST` to `SCALE`.

Why? Missing costs became zero, or a timed-out run vanished without an independent
attempt ledger.

Decision completeness and source completeness are different.

**Post 5**

Then I tested 40 public mini-SWE-agent trajectories on 20 paired SWE-bench tasks.

Opus resolved 14/20 versus Haiku's 11/20, but cost more per attempt and per resolved
task. The engine said `STOP`; the uncertainty-aware frontier said `HOLD`.

Promising is not proven.

**Post 6**

Everything is reproducible:

```bash
python3 false_green.py
python3 evidence_ablation.py
make public-case
```

Code, protocols, generated rows, tests, and limitations:

https://github.com/Vyoma/agent-economics-lab

## Hacker News submission

**Title:**

> Show HN: A fixed evidence contract for deciding whether AI agents should scale

**First comment:**

Hi HN, I built this after noticing a decision-layer failure that ordinary eval
dashboards can hide.

If the set of required checks is inferred from the checks that happen to run,
disabling a failing evaluator can turn the same evidence from `ASSIST` into
`SCALE`. I call this decision-coverage drift.

The repository has two separate experiments:

1. 588 single-gate disablement comparisons. Dynamic coverage produces 23 false
   `SCALE` transitions. A fixed contract produces zero and refuses all 588.
2. Nine raw-evidence deletions. Four are refused; five expose where source
   completeness still fails.

There is also a small non-synthetic case built from 40 public mini-SWE-agent
trajectories on 20 paired SWE-bench Verified tasks.

The runtime has no third-party dependencies. The repo includes the protocols,
generated rows, tests, data cards, result cards, exact claim limitations, and a
one-page contract.

I would especially value attempts to break the invariant or identify a source
omission the current contracts cannot detect:

https://github.com/Vyoma/agent-economics-lab

## Discovery sequence

The goal is concentrated technical proof, not maximum posting volume.

### Publication day

1. Publish the Substack article as the canonical URL.
2. Confirm every link in a signed-out browser.
3. Send the short reply to Lenny.
4. Publish the LinkedIn post with one result graphic.
5. Publish Post 1 of the X thread and the remaining thread immediately after it.
6. Pin the repository and article on the GitHub profile.

### Day two

1. Submit the repository to Hacker News as a `Show HN`.
2. Answer technical objections with links to protocols, tests, and limitations.
3. Turn strong objections into issues or new falsification cases.

### Day three

Publish one narrow technical follow-up:

> A fixed eval contract cannot prove a trace export is complete.

Use the nine raw-evidence deletions. This shows that the first article is a
research program, not a one-off launch.

### The lab-facing rule

Do not tag labs, ask for a job, or claim that the work solves evaluation in
general. Make the artifact easy to inspect:

- the finding in the first screen;
- the command in the first minute;
- the invariant in plain code;
- the non-synthetic case before the limitations;
- the limitations beside each result;
- issues labeled for replication, source adapters, and counterexamples.

When contacting an individual researcher, send one sentence about the exact
overlap with their work and one falsifiable question. Do not send a generic
portfolio pitch.

## Final publication check

- [ ] Use the exact recommended title and subtitle.
- [ ] Add the header image and alt text.
- [ ] Replace every `[SUBSTACK URL]`.
- [ ] Confirm all GitHub links resolve on `main`.
- [ ] Run all three commands from a fresh checkout.
- [ ] Keep the synthetic limitation next to the 23-transition result.
- [ ] Keep the public benchmark limitation next to the SWE-bench result.
- [ ] Do not call the 23 transitions enterprise incidents or a prevalence rate.
- [ ] Do not describe one OpenTelemetry contract as universal vendor support.
- [ ] Confirm there are no em dashes or en dashes.
- [ ] Send the Lenny reply only after the public article is live.
- [ ] Use one primary call to action.
