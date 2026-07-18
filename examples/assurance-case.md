# Agent Economic Assurance Case

**Decision: ASSIST**

This is an evidence-based routing decision: SCALE autonomously, ASSIST with human/control coverage, or STOP until the economics change.

## Assurance manifest

- Source adapter: `source.csv@1`
- Evidence digest: `485f97ae54ca71c84116036e1d987fd249a3e5c4e10f734b2fcf9c4878428fc4`
- Report renderer: `renderer.markdown@1`
- Enabled checks:
  - `gate.acceptable-rate@1`
  - `gate.unit-economics@1`
  - `gate.tail-cost@1`
  - `gate.net-value@1`
  - `gate.counterfactual@1`
  - `gate.runtime-caps@1`
  - `diagnostic.repeated-tool-shape@1`
- Required coverage:
  - `business_value`
  - `counterfactual`
  - `outcome_quality`
  - `runtime_caps`
  - `tail_risk`
  - `unit_economics`

## Observed evidence

| Measure | Result |
|---|---:|
| Attempts | 8 |
| Acceptable outcomes | 6 (75.0%) |
| Total effective cost | $21.02 |
| Cost per acceptable outcome | $3.50 |
| p95 effective task cost | $14.25 |
| Maximum effective task cost | $14.25 |
| Expected net value per attempt | $3.37 |

Effective cost = model/tool spend + human review + remediation + incident loss.

## Counterfactual

Baseline: **human-only support queue**

| Measure | Agent | Baseline |
|---|---:|---:|
| Cost per acceptable outcome | $3.50 | $7.14 |
| Expected net value per attempt | $3.37 | $0.60 |
| Incremental net value per attempt | $2.77 | — |

## Gate results

- **FAIL · gate.acceptable-rate:** acceptable_rate 75.0% < 80.0%
- **FAIL · gate.unit-economics:** cost_per_acceptable_outcome $3.50 > $2.00
- **FAIL · gate.tail-cost:** p95_task_cost $14.25 > $8.00
- **PASS · gate.net-value:** expected_net_value_per_attempt $3.37 >= $0.00
- **PASS · gate.counterfactual:** incremental_net_value_vs_baseline $2.77 >= $0.00
- **FAIL · gate.runtime-caps:** t-005: 12 calls > cap of 8
- **FAIL · gate.runtime-caps:** t-005: $0.2454 trace cost > cap of $0.1500

## Policy breaches

- acceptable_rate 75.0% < 80.0%
- cost_per_acceptable_outcome $3.50 > $2.00
- p95_task_cost $14.25 > $8.00
- t-005: 12 calls > cap of 8
- t-005: $0.2454 trace cost > cap of $0.1500

## Diagnostic findings

- **WARNING · t-005 · repeated_tool_shape:** 'search' repeated 3 times with the same argument shape (e-016..e-020). Possible loop. This is a structural heuristic, not proof that the calls have the same meaning.

## Claim boundary

The result is only as reliable as the trace coverage, outcome labels, cost allocation, counterfactual, enabled checks, and observation window. Removing required coverage returns INCOMPLETE. A repeated tool shape or graph cycle is a diagnostic warning—not semantic proof of a loop or deadlock.
