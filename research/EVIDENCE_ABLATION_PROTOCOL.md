# Protocol: Raw Evidence Ablation

## Research question

When one piece of raw evidence is removed, does the current evaluation path:

1. reject the raw schema;
2. reject the normalized evidence;
3. fail during evaluation; or
4. emit an assurance decision?

This protocol characterizes current behavior. It does not change the evidence
adapter or propose that every rejection must be represented by an
`AssuranceCase`.

## Separation from the gate-ablation experiment

`false_green.py` disables a required assurance gate. This protocol does not.
Every case uses the same ordered default checks and the same six required
coverage dimensions:

```text
outcome_quality
unit_economics
tail_risk
business_value
counterfactual
runtime_caps
```

The benchmark records a digest of that fixed decision contract on every row.
Any contract change invalidates the frozen result.

## Fixed evaluation path

Each case executes:

```text
raw normalized JSON
  -> normalized_json_bundle()
  -> AssuranceEngine(fixed checks, fixed coverage)
  -> evaluation result
```

The complete fixture is evaluated first. A deep copy is then changed by exactly
one deletion and evaluated through the identical path.

## Frozen fixtures

All fixtures contain two acceptable tasks, an explicit baseline, an explicit
policy, and a two-row task manifest. The common values are:

```text
trace cost per task                 $0.10
business value per acceptable task $20.00
baseline cost per attempt           $10.00
baseline acceptable rate            50%
baseline value per acceptable task $20.00
minimum acceptable rate            100%
maximum cost per acceptable          $5.00
maximum p95 task cost                $5.00
maximum trace cost per task          $5.00
maximum calls per task                    3
```

Boundary fixtures change one value or threshold:

- Incident: `$3.00` incident loss on `task-a`; p95 threshold `$1.00`.
- Remediation: `$3.00` remediation cost on `task-a`; unit-cost threshold `$1.00`.
- Human review: 3 minutes at `$60/hour`; unit-cost threshold `$1.00`.
- Trace cost: `$2.00` directly priced tool event; unit-cost threshold `$1.00`.
- Timed-out event: a second event on `task-a`; call cap `1`.

## Ablations

| Case | Single deletion | Complete decision | Current result |
|---|---|---:|---|
| `drop_outcome_record` | `/outcomes/0` | SCALE | semantic evidence error |
| `drop_baseline_object` | `/baseline` | SCALE | raw schema error |
| `drop_incident_loss` | `/outcomes/0/incident_loss_usd` | ASSIST | SCALE |
| `drop_remediation_cost` | `/outcomes/0/remediation_cost_usd` | ASSIST | SCALE |
| `drop_human_review_time` | `/outcomes/0/human_minutes` | ASSIST | SCALE |
| `drop_trace_cost` | `/events/0/direct_cost_usd` | ASSIST | SCALE |
| `drop_manifest_task` | `/task_manifest/0` | SCALE | semantic evidence error |
| `drop_policy_threshold` | `/policy/max_cost_per_acceptable_outcome_usd` | SCALE | raw schema error |
| `drop_timed_out_event` | `/events/1` | ASSIST | SCALE |

No row or case is discarded.

## Outcome taxonomy

The library outcome and operational outcome are separate fields.

### Library outcome

- `SCHEMA_ERROR`: a required raw object or constructor field is absent.
- `EVIDENCE_ERROR`: normalization reaches semantic evidence validation and is
  rejected.
- `EVALUATION_ERROR`: normalization succeeds but evaluation raises unexpectedly.
- `DECISION`: an `AssuranceCase` is emitted.

### Operational outcome

The public CLI catches the schema and evidence errors in this protocol, prints
`INCOMPLETE: invalid evidence`, and returns exit code 2. Therefore those rows
have operational outcome `INCOMPLETE`, even though no
`AssuranceCase(decision=INCOMPLETE)` exists.

Decision rows use the emitted `SCALE`, `ASSIST`, `STOP`, or `INCOMPLETE` value.
An unexpected evaluation exception uses operational outcome `ERROR`.

## Primary conformance result

The frozen current behavior is:

```text
9 raw evidence ablations
2 schema errors
2 semantic evidence errors
4 operational refusals
5 ASSIST -> SCALE transitions
0 INCOMPLETE assurance-case artifacts
0 unexpected evaluation errors
```

The result is falsified if a clean fixture changes decision, an outcome class
changes, the decision contract changes, or the aggregate counts differ.

## False-SCALE label

```text
false_scale =
  complete decision != SCALE
  and ablated library outcome == DECISION
  and ablated decision == SCALE
```

This label describes a paired boundary fixture. Five is not an estimate of a
production error rate.

## Interpretation

The four rejected inputs demonstrate two different fail-closed boundaries:

- missing top-level baseline or required policy threshold fails raw construction;
- missing outcome or task-manifest rows fails semantic evidence validation.

The five decision-producing omissions expose two current source-contract limits:

- omitted outcome cost fields and non-model direct cost default to zero;
- a deleted timed-out event cannot be detected without an attempt-completeness
  contract.

The benchmark documents those limits. Hardening the adapter or adding an attempt
manifest is separate work and requires a protocol-version change.

## Reproducibility

- Python 3.10 or newer.
- No runtime dependencies.
- No randomness.
- Stable fixture and ablation order.
- Stable error codes rather than exception prose.
- Checked-in CSV and JSON artifacts.
- Verification is completed before any output artifact is written.
