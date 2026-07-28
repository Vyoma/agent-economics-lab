# Agent Economic Assurance Case

**Decision: ASSIST**

This is an evidence-based routing decision: SCALE autonomously, ASSIST with human/control coverage, or STOP until the economics change.

## Assurance manifest

- Source adapter: `source.claude-code-jsonl@1`
- Evidence digest: `89816dd5af84f7348bd2be8c619124637ab3146332c8ff565af3378103072980`
- Decision-contract digest: `dc7704f81861ba246016e78f077fd5b38238be846a9e95db7a13118a655d5983`
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
| Attempts | 2 |
| Acceptable outcomes | 1 (50.0%) |
| Total effective cost | $3.01 |
| Cost per acceptable outcome | $3.01 |
| p95 effective task cost | $2.51 |
| Maximum effective task cost | $2.51 |
| Expected net value per attempt | $3.49 |

Effective cost = model/tool spend + human review + remediation + incident loss.

## Counterfactual

Baseline: **illustrative human-only workflow**

| Measure | Agent | Baseline |
|---|---:|---:|
| Cost per acceptable outcome | $3.01 | $12.00 |
| Expected net value per attempt | $3.49 | $-1.00 |
| Incremental net value per attempt | $4.49 | N/A |

## Gate results

- **FAIL · gate.acceptable-rate:** acceptable_rate 50.0% < 75.0%
- **PASS · gate.unit-economics:** cost_per_acceptable_outcome $3.01 <= $4.00
- **PASS · gate.tail-cost:** p95_task_cost $2.51 <= $6.00
- **PASS · gate.net-value:** expected_net_value_per_attempt $3.49 >= $0.00
- **PASS · gate.counterfactual:** incremental_net_value_vs_baseline $4.49 >= $0.00
- **PASS · gate.runtime-caps:** all tasks remain within call and trace-cost caps

## Policy breaches

- acceptable_rate 50.0% < 75.0%

## Diagnostic findings

- None

## Claim boundary

The result is only as reliable as the trace coverage, outcome labels, cost allocation, counterfactual, enabled checks, and observation window. When enabled gates do not supply the fixed required coverage, the engine returns INCOMPLETE. A repeated tool shape or graph cycle is a diagnostic warning, not semantic proof of a loop or deadlock.
