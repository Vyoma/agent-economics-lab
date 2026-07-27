# The Missing Product Spec for AI Agents

**Subtitle:** Your agent passed every enabled check. That does not mean every
required check ran. Here is a practical decision contract for deciding whether to
scale, assist, stop, or refuse to decide.

In a controlled fixture, an AI agent failed its tail-risk check, so the decision
engine kept it in assisted mode.

In the next configuration, that evaluator was disabled. Every remaining check
passed, and the same agent was approved to scale.

Nothing about the agent improved. The definition of enough evidence got smaller.

This is an easy failure to hide inside a green dashboard. The dashboard may be
correct about every check it received. It is answering the wrong question.

It answers:

> Did every enabled check pass?

The product decision requires:

> Did every required check run, and did every one pass?

That difference matters as teams give agents more autonomy, traffic, and budget.

## The missing artifact is a decision contract

A recent conversation in Lenny's Newsletter called
[evals the modern version of a PRD](https://www.lennysnewsletter.com/p/how-braintrust-uses-ai-agents-evals).
That is a useful framing. Evals turn product judgment into measurements a team can
run repeatedly.

But measurements do not automatically create a scale decision.

An agent can pass its quality evals and still be a bad business decision. It can
create value on average and still have an unacceptable tail. It can beat a token
budget while shifting expensive cleanup to humans. It can look better than nothing
while remaining worse than the workflow it is supposed to replace.

A **decision contract** defines which measurements are mandatory, what complete
means, and how missing or failed checks route. It answers:

> For this workload, under this policy, with this complete evidence, has the system
> earned the right to operate with less assistance or at greater scale?

This is not a claim to have invented assurance or abstention. NIST defines an
[assurance case](https://csrc.nist.gov/glossary/term/assurance_case) as an auditable
artifact connecting claims, arguments, evidence, and assumptions. Fail-closed
systems refuse unsafe states. Selective systems can abstain instead of forcing an
answer.

The useful synthesis is to apply those principles to an agent scale decision, bind
the evidence and policy into a portable artifact, and make its refusal semantics
executable.

## Six claims, fixed before the result

There is no universal checklist for every agent. A coding agent and a claims agent
do not have the same risk boundary. The contract must be specific to a named
workload and population.

The open-source reference implementation I built requires six dimensions:

| Required claim | The product question it answers |
|---|---|
| Outcome quality | Did the agent produce an acceptable result? |
| Cost per acceptable outcome | What did success cost after failures and rework? |
| Tail cost | Are a few tasks hiding an operationally dangerous tail? |
| Absolute business value | Does the workflow create value at all? |
| Counterfactual value | Is it better than the process it will replace? |
| Runtime caps | Can a task exceed its allowed calls or spend? |

Teams can add domain-specific requirements such as privacy, authorization,
fairness, or clinical safety. What matters is that the required claims, thresholds,
evidence sources, failure routes, owner, and expiry are fixed before the candidate
result is examined.

## Copy the one-page contract

I turned the idea into a blank
[agent scale decision contract](https://github.com/Vyoma/agent-economics-lab/blob/main/templates/agent-scale-decision-contract.md).
Use it for one workflow, not the entire platform.

It separates two independent properties.

**Performance:** Did the evidence meet the declared thresholds?

**Completeness:** Was every required claim supplied by a known, versioned check,
and did the source prove that all expected records were present?

That leads to four outputs:

| Decision | Meaning |
|---|---|
| `INCOMPLETE` | A required claim or source-completeness guarantee is missing. |
| `SCALE` | Required evidence is complete and every scale gate passes. |
| `ASSIST` | A gate with a declared `ASSIST` route failed, so human oversight or tighter limits remain. |
| `STOP` | A gate with a declared `STOP` route failed. |

Each gate owns an explicit failure route. `INCOMPLETE` is different. It means the
system does not have the evidence required to issue the bounded decision at all.

A refusal creates work. Someone has to restore the evaluator, repair the export,
reconcile the run ledger, or review a changed contract. A silent green result
creates no such pressure.

Here is what the included synthetic support case produces:

```text
Decision                         ASSIST
Acceptable outcomes              6 / 8
Cost / acceptable outcome        $3.50
Incremental value / attempt      $2.77
Why not SCALE                    quality, unit cost, tail cost, runtime caps
```

The agent creates more expected value than the human-only baseline, but it does not
earn unattended scale. Positive ROI is not permission for greater autonomy.

When completing the contract, ask three uncomfortable questions:

1. **Can absence become zero?** Omitted, null, or blank cost fields must be rejected
   before defaults. An explicit `0.0` must retain source provenance.
2. **Can a failed execution disappear?** A task manifest is not enough when several
   attempts can occur inside one task. Reconcile frozen expected attempt IDs and
   terminal statuses against an independent run ledger.
3. **Can a requirement disappear with its check?** If disabling a check also
   removes its requirement, the system silently lowers the bar.

## I tested the third failure mode

I built a deterministic synthetic benchmark around one narrow intervention:
disable one required gate.

The fixture contains 98 scenarios and six required gates, producing 588
single-gate disablement comparisons. Each comparison runs through two
architectures:

- an enabled-checks-only engine that redefines required coverage around the gates
  that remain; and
- a fixed-contract engine that preserves the original six requirements.

The result:

```text
enabled-checks-only engine    23 false SCALE transitions
fixed-contract engine          0 false SCALE transitions
fixed-contract refusals      588 INCOMPLETE decisions
```

The 23 transitions show that this failure mode exists in the constructed fixture.
They do not estimate how often production systems exhibit it.

The zero has a different interpretation. It is an enforced software invariant:
disabling a sole-provider gate cannot produce `SCALE` while the original contract
remains fixed.

I use **decision-coverage drift** for the failure mode where the definition of
sufficient evidence shrinks to match whichever checks happen to run.

## A fixed contract still cannot prove its source is complete

Gate coverage and raw evidence completeness are separate problems. A check can run
successfully on an incomplete export.

I tested that boundary separately by deleting records and fields while keeping the
decision contract fixed. Across nine constructed cases, four omissions were
rejected at the schema or evidence boundary. Five decision-producing omissions
changed `ASSIST` to `SCALE`.

Those five transitions came from two source gaps:

- optional cost omissions could become zero; and
- a deleted timed-out execution event was undetectable without an independent run
  ledger.

These are designed boundary cases, not prevalence data. A digest can bind a result
to the evidence that was evaluated. It cannot prove that an upstream source
supplied everything that should exist.

Production decisions therefore need both fixed decision coverage and explicit
source-completeness contracts.

## The Monday-morning test

Take one agent workflow your team is considering for broader deployment. Put its
product owner, an engineer, and the person accountable for cost or risk in one
room.

1. Define one unit of work and one observable acceptable outcome.
2. Name the real counterfactual and draw the full cost boundary, including failures,
   human review, remediation, and incident loss.
3. Freeze the thresholds, required claims, and each gate's failure route.
4. Map every claim to its evidence source, check, missing-data semantics, and
   independent task and run ledgers.
5. Disable one required check and delete one raw execution event. Confirm that
   neither action can improve the decision.

Then bind the output to evidence and decision-contract digests, add an owner and
expiry, and rerun it when evidence, policy, or composition changes.

When a reviewer or control plane pins the expected contract digest, teams can add
or remove evaluators and observability tools without letting requirements vanish
silently. An intentional contract change creates a new version and digest that must
be reviewed.

## Three rules for every agent dashboard

No outcome label, no scale.

No named counterfactual, no ROI.

No required coverage, no green.

The open-source
[Agent Economics Lab](https://github.com/Vyoma/agent-economics-lab) includes the
one-page contract, runnable benchmarks, generated evidence, protocols, and
limitations. It runs locally with Python 3.10 or newer and no third-party runtime
packages:

```bash
python3 false_green.py
python3 evidence_ablation.py
```

Copy the contract and test one real, permissioned workflow before expanding its
autonomy, traffic, or spend.

The interesting question is no longer whether the dashboard is green.

It is whether the agent has earned the right to scale.

---

*Vyoma Gajjar is a principal AI architect and educator who builds enterprise agent
systems and adoption programs. Her work focuses on the boundary between technical
evaluation, operating economics, and the decisions organizations must defend.*
