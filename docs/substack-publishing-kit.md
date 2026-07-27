# Substack Publishing Kit

## Recommended title

The Missing Product Spec for AI Agents

## Subtitle

Your agent passed every enabled check. That does not mean every required check ran.
Here is a practical decision contract for deciding whether to scale, assist, stop,
or refuse to decide.

## Publication details

- Suggested slug: `missing-product-spec-for-ai-agents`
- Estimated reading time: 10 minutes
- Suggested tags: AI agents, product management, AI evaluation, enterprise AI
- Primary audience: product leaders, AI engineers, enterprise AI architects
- Secondary audience: finance, FinOps, risk, and governance leaders

## Substack preview text

An evaluator disappears. Every remaining check passes. The same AI agent moves from
ASSIST to SCALE even though nothing about it improved. The missing product artifact
is a fixed decision contract that keeps the definition of enough evidence from
shrinking.

## Search description

A practical one-page decision contract for AI agents that separates performance
from evidence completeness and routes each workload to INCOMPLETE, SCALE, ASSIST,
or STOP.

## Header image brief

A clean editorial diagram on a light background. A fixed rectangular decision
contract lists six required checks: Outcome, Unit Cost, Tail Cost, Business Value,
Counterfactual, Runtime Caps. Six matching gate cards feed the contract, but the
Tail Cost gate is visibly disabled. The requirement remains visible inside the
fixed contract. On the right, the output is a large amber `INCOMPLETE`, not a green
check. Minimal typography, no robot imagery, no circuit-board clichés, and no
vendor logos.

Recommended alt text:

> Six required gate cards feed a fixed agent scale decision contract. The Tail Cost
> gate is disabled, but its requirement remains, so the output is INCOMPLETE.

## Article call to action

Use only one primary call to action:

> Copy the decision contract, run the two local experiments, and test one real agent
> workflow before expanding its autonomy, traffic, or spend.

Link the words "decision contract" to:

`https://github.com/Vyoma/agent-economics-lab/blob/main/templates/agent-scale-decision-contract.md`

Link "two local experiments" to:

`https://github.com/Vyoma/agent-economics-lab`

Publish the repository file before activating the first link.

## Email to Lenny

**To:** lenny@lennyrachitsky.com

**Subject:** I took your advice: the missing product spec for AI agents

Hi Lenny,

You encouraged me to run with the idea, so I did.

I turned it into a practical article and a runnable open-source artifact. The core
idea is simple: "all enabled checks passed" is not the same as "all required checks
ran." Product teams need a fixed decision contract before an agent earns more
autonomy, traffic, or spend.

The article includes a one-page worksheet, plus a reproducible experiment showing
how the same agent can move from ASSIST to SCALE when a required check disappears
and the system silently lowers its evidence bar.

Article: [SUBSTACK URL]

Code and worksheet: https://github.com/Vyoma/agent-economics-lab

No ask. I wanted to close the loop and thank you for the push.

Vyoma

## LinkedIn launch post

Your AI agent passed every enabled check.

Did every required check run?

Those are different questions.

I tested what happens when one required gate disappears from an agent scale
decision. Across 588 deterministic synthetic gate-disablement comparisons:

- an enabled-checks-only engine produced 23 false SCALE transitions;
- a fixed-contract engine produced zero; and
- the fixed-contract engine returned INCOMPLETE every time required coverage was
  missing.

The benchmark is not a prevalence estimate. It proves a narrower failure mode:
nothing about the agent has to improve when the definition of enough evidence gets
smaller.

I wrote a practical guide for product and engineering teams, including a one-page
decision contract that binds:

- outcome quality;
- cost per acceptable outcome;
- tail cost;
- absolute and counterfactual value; and
- runtime caps.

No outcome label, no scale.

No named counterfactual, no ROI.

No required coverage, no green.

Read: [SUBSTACK URL]

Run it: https://github.com/Vyoma/agent-economics-lab

#AIAgents #ProductManagement #EnterpriseAI #AIEvals #OpenSource

## Short X post

Your AI agent passed every enabled check.

Did every required check run?

I disabled one required gate at a time across 588 synthetic comparisons. An engine
that silently shrank required coverage produced 23 false SCALE transitions. A
fixed-contract engine returned INCOMPLETE.

The missing product spec is a decision contract.

[SUBSTACK URL]

## Final publication check

- [ ] Publish the blank decision-contract worksheet to the repository.
- [ ] Replace `[SUBSTACK URL]` in the email and social copy.
- [ ] Confirm the article links resolve in a private Substack preview.
- [ ] Keep the synthetic-fixture limitation next to the benchmark result.
- [ ] Keep "23 false SCALE transitions," not "23 enterprise failures."
- [ ] Keep "five omissions across two source-completeness gaps," not "five gaps."
- [ ] Send the Lenny note only after the public article and worksheet both resolve.
- [ ] Use the header image alt text.
- [ ] Add a first comment with the runnable commands.
