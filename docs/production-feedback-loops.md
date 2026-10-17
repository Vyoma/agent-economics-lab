# One feedback loop, three kinds of evidence

Predictive models, generative systems, and tool-using agents can share an
operational feedback loop. They cannot share one undifferentiated score.

The common loop is simple to draw:

```text
versioned decision -> observable action -> delayed outcome
        |                                      |
        +---------- stable join key -----------+
                               |
                         intervention test
                               |
                      advance, abstain, or roll back
```

The hard part is deciding what each arrow means before looking at the result.
A dashboard assembled after the fact can usually explain any movement. A useful
contract instead fixes the unit of decision, outcome definition, observation
window, joins, missing-data route, counterfactual, and rollback rule while the
system can still surprise us.

This repository ships that contract as dependency-free JSON and a closed
validator. The filled example is synthetic and covers a support stack containing
a predictive triage model, a generative drafting component, and a tool-using
agent.

```bash
python3 -m agent_economics.feedback_contract \
  examples/production-feedback-contract.json
```

The checked-in example validates to:

```text
VALID digest=b17f80b2b89e4801c67ee27ff5764c6fc467e6b025169bb68a56ee0959435e80
```

That digest binds the supplied policy. It is not a certificate that the policy
is correct.

## The shared spine

Every production feedback loop needs the same seven decisions.

1. **Unit.** Name the object that receives one decision: case, query, item,
   session, account, or task. Aggregating before this is defined makes the join
   ambiguous.
2. **Outcome.** Version the exact acceptance rule and state when the outcome is
   observable. "Resolved" and "not reopened within 14 days" are different
   labels.
3. **Join.** Specify how a decision becomes attributable to an outcome, how
   duplicates are handled, and what happens to late or unmatched records.
4. **Proxy.** State which primary outcome a cheap signal was checked against,
   how agreement was measured, where the proxy is allowed, and where it is
   forbidden.
5. **Intervention.** Change one named layer: data, model, retrieval, tool,
   routing, or policy. Give the test an owner and a rollback trigger.
6. **Counterfactual.** Record what would have happened without the change. A
   rising metric alone does not identify the cause.
7. **Failure route.** Missing outcomes or broken joins must become
   `INCOMPLETE`, `ABSTAIN`, or `HUMAN_REVIEW`, never a silent pass.

These fields are deliberately operational. "Improve quality" is not an
intervention. "Canary a frozen retrieval index against the current index and
roll back if delayed task outcome is flat or citation support worsens" is.

## The evidence must stay modality-specific

The shared spine does not erase different failure modes.

| System component | Evidence required before interpreting the outcome |
|---|---|
| Predictive model | Calibration, threshold policy, and pre-committed drift slices |
| Generative component | Prompt version, retrieval version, and binding to the primary task outcome |
| Tool-using agent | Tool-registry version, side-effect ledger, and human-handoff rule |

For a predictive model, ranking quality can improve while the operating
threshold becomes unsafe on a smaller slice. Calibration and threshold policy
therefore belong in the record separately.

For a generative component, a model version is not enough. A retrieval-index
change or prompt edit can move the outcome while the model stays fixed. Both
versions have to travel with the decision.

For an agent, the trace is not the complete unit of risk. The system can write,
send, purchase, delete, or escalate. A tool registry and side-effect ledger are
needed to reconstruct what it was allowed to do and what it actually changed.

The validator requires exactly the evidence surfaces for the modalities the
issuer declares. Declaring `predictive`, `generative`, and `agent` while
providing only an agent trace is invalid. Supplying an undeclared evidence block
is invalid too. This closed shape prevents a generic "evaluation complete" field
from standing in for three different audits.

## Proxies are useful only with a job description

Most production outcomes arrive late. Teams therefore reach for acceptance,
clicks, grader scores, latency, sentiment, or tool completion as faster signals.
The problem is not using proxies. The problem is letting a proxy silently become
the outcome.

The example permits same-session acceptance for diagnostic slicing and forbids
it as a deployment gate or substitute for the 14-day outcome. Two failure modes
are recorded: acceptance can precede a reopen, and silent abandonment can look
like acceptance.

This is intentionally stricter than attaching a correlation coefficient. A
correlation does not say what decision the proxy is allowed to make. Allowed
uses and forbidden uses turn validation into policy.

## A feedback loop should identify the next lever

When an outcome moves, the relevant question is not only whether the model got
better. The change may have come from a label definition, data mix, retrieval
index, tool interface, routing rule, or control policy.

The example carries three separate interventions:

- queue-specific labels for predictive calibration;
- a frozen curated retrieval index for the generative component;
- a deterministic pre-check before agent writes.

Each has its own test and rollback trigger. This makes the feedback loop a way
to choose the next engineering lever, not only a way to grade the current model.

## What the validator proves

The validator rejects unknown fields, duplicate JSON keys, non-finite numbers,
unsupported modalities, blank required values, mismatched modality evidence,
proxies bound to the wrong outcome, missing rollback semantics, and fail-open
routes. It canonicalizes the valid document and returns a SHA-256 digest.

It proves structural completeness relative to version 1 of this contract and
detects policy drift in the supplied record.

## What the validator does not prove

The validator does not establish that:

- the outcome represents real value;
- the label source is correct;
- a proxy relationship generalizes;
- an intervention caused the observed change;
- the chosen slices cover every important population;
- a human approval actually occurred;
- the issuer supplied truthful evidence.

Those are empirical, organizational, or cryptographic claims. They need data,
study design, independent review, or signed attestations. A structurally valid
contract merely makes their absence visible.

## Use the template as a pre-registration, not a postmortem

The blank contract is intentionally invalid. A team should fill it before the
canary starts, review it in version control, and bind the deployed system to the
resulting digest. After the observation window closes, the same identifiers and
rules should be used to assemble outcomes.

If a required outcome never arrives, the correct result is incomplete evidence,
not a smaller denominator. If the primary outcome changes, issue a new
definition version. If the intervention changes, issue a new digest. If a proxy
is promoted from diagnosis to gating, record the new allowed use and review the
evidence that justifies it.

The practical goal is not one universal evaluation score. It is a traceable
answer to a narrower question: which versioned decision changed which outcome,
under which policy, and what should the system do when the evidence is missing?

[Blank template](https://github.com/Vyoma/agent-economics-lab/blob/v0.10.2/templates/production-feedback-contract.template.json) ·
[filled synthetic example](https://github.com/Vyoma/agent-economics-lab/blob/v0.10.2/examples/production-feedback-contract.json) ·
[validator](https://github.com/Vyoma/agent-economics-lab/blob/v0.10.2/agent_economics/feedback_contract.py)
