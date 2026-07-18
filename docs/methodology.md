# Methodology

Agent Economics Lab treats economic readiness as a falsifiable assurance claim,
not a dashboard screenshot. The claim is deliberately narrow:

> For this named workload, observed over this window, the agent meets a policy for
> outcome quality, full economic cost, tail exposure, and value versus a named
> alternative.

## 1. Choose the unit of work

A `task_id` is the join key between execution and outcome data. It must represent a
business attempt—a support case, invoice, code change, investigation—not an
individual model call. Every retry, tool call, sub-agent handoff, and final response
for that attempt belongs to the same task.

The example trace contract is:

| Field | Meaning |
|---|---|
| `task_id` | Stable business-attempt identifier |
| `event_id` | Unique call/step identifier |
| `timestamp` | Event time used to define the observation window |
| `event_type` | `model`, `tool`, or another execution step |
| `name` | Model role or tool name |
| `model` | Rate-card key for a model event |
| `input_tokens`, `output_tokens` | Metered model usage |
| `direct_cost_usd` | Vendor charge when token pricing is not appropriate |
| `status` | Observed execution status |
| `arguments` | JSON used only for local diagnostic signatures in this lab |

If `direct_cost_usd` is present, the lab uses it. Otherwise, model cost is:

```text
event_cost = input_tokens × input_rate / 1,000,000
           + output_tokens × output_rate / 1,000,000
```

The task-level trace cost is the sum of **all** its events, including failed calls.

## 2. Define an acceptable outcome before looking at cost

Execution success is not outcome success. An `acceptable` label should represent a
business-relevant contract: a correctly resolved case, a merged change with passing
tests, a validated claim, or another externally observable result.

The outcome table adds:

- realized business value;
- human review minutes;
- remediation or rework cost; and
- incident/risk loss attributable to the attempt.

In the implementation, business value is counted only when the outcome is marked
acceptable. This conservative rule prevents a failed attempt from claiming the
value of the desired result.

## 3. Expand from trace spend to effective cost

For task *i*:

```text
human_cost_i = human_minutes_i × loaded_hourly_cost / 60

effective_cost_i = trace_cost_i
                 + human_cost_i
                 + remediation_cost_i
                 + incident_loss_i
```

This is still a model, not a general-ledger fact. The assurance case must record the
allocation source for shared infrastructure, labor, and risk costs.

## 4. Calculate unit economics at the outcome boundary

For *N* attempted tasks and *A* acceptable outcomes:

```text
acceptable_rate = A / N

cost_per_acceptable_outcome = Σ effective_cost_i / A

expected_net_value_per_attempt =
    (Σ realized_business_value_i - Σ effective_cost_i) / N
```

Failed attempts remain in the numerator. Removing them would reward a system for
making expensive errors.

Tail cost uses the nearest-rank percentile. On small samples this is intentionally
conservative: p95 of eight tasks is the maximum task. Production analyses should
include more observations, confidence intervals, and segmented tails.

## 5. Compare a named counterfactual

“The agent saved money” has no meaning without an alternative. The baseline can be
the existing human process, a simpler workflow, a retrieval-only system, or a
different agent configuration.

```text
baseline_cost_per_acceptable = baseline_cost_per_attempt
                             / baseline_acceptable_rate

baseline_expected_net_value = baseline_acceptable_rate
                            × value_per_acceptable_outcome
                            - baseline_cost_per_attempt

incremental_value = agent_expected_net_value - baseline_expected_net_value
```

Baseline quality and value assumptions should come from the same population and
time window when possible.

## 6. Apply policy and route the workload

The policy belongs in version control and should be approved before viewing a run.
This lab checks:

- minimum acceptable rate;
- maximum cost per acceptable outcome;
- maximum p95 effective task cost;
- minimum expected net value per attempt;
- minimum incremental net value versus the named baseline;
- maximum trace spend per task; and
- maximum calls per task.

Routing semantics:

| Decision | Meaning |
|---|---|
| `INCOMPLETE` | One or more required assurance dimensions were removed or not evaluated |
| `SCALE` | All economic checks pass and no deterministic control cap is breached |
| `ASSIST` | Value remains positive, but at least one policy/control boundary fails |
| `STOP` | A required value gate fails, including the counterfactual value floor |

The counterfactual is a gate, not merely a comparison table. The default policy
requires incremental net value versus the named baseline to be at least zero. An
agent that is profitable in isolation but worse than the available alternative
cannot receive `SCALE`.

Checks are explicitly composed and recorded by ID/version. Removing an optional
diagnostic changes only its findings. Removing a check that supplies required
coverage returns `INCOMPLETE` even if every remaining gate passes.

These defaults express one possible governance contract. Enterprises should add
domain-specific safety, compliance, fairness, authorization, and reliability gates
outside this lab.

## 7. Keep diagnostic and enforcement claims separate

`repeated_tool_shape` discards argument values and compares tool name, keys,
containers, and primitive types. It can cheaply flag a suspicious series. It cannot
determine whether successive calls are semantically equivalent.

`find_directed_cycles` identifies a cycle in a supplied dependency graph. A cycle
is necessary for some forms of deadlock but not sufficient: a real deadlock also
depends on waiting/resource semantics and the inability of any participant to
progress.

These are warnings. Call caps, spend caps, timeouts, authorization checks, and
human escalation are enforceable boundaries.

## 8. Make the claim reproducible

An assurance case should pin:

- traces and outcome-label revision;
- model/tool rate card date;
- labor and risk allocation assumptions;
- counterfactual definition;
- policy version;
- code commit; and
- observation window.

Re-run the case whenever any of these changes. Economic assurance is a renewable
claim, not a one-time certificate.
