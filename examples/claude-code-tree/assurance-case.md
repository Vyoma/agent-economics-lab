# Agent Economic Assurance Case

**Decision: SCALE**

This is an evidence-based routing decision: SCALE autonomously, ASSIST with human/control coverage, or STOP until the economics change.

## Assurance manifest

- Source adapter: `source.claude-code-session-tree@1`
- Evidence digest: `1629688354167486ffc7657e778311f0c1916d112e9db6d547655daa228fd6bc`
- Decision-contract digest: `f30996d535c1722fddb2e767bc830c9d2cb34054b864481e1220d459121e3e1a`
- Report renderer: `renderer.markdown@1`
- Enabled checks:
  - `gate.acceptable-rate@1`
  - `gate.unit-economics@1`
  - `gate.tail-cost@1`
  - `gate.net-value@1`
  - `gate.counterfactual@1`
  - `gate.runtime-caps@1`
  - `diagnostic.repeated-tool-shape@1`
  - `diagnostic.directed-cycle@1`
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
| Attempts | 1 |
| Acceptable outcomes | 1 (100.0%) |
| Total effective cost | $0.50 |
| Cost per acceptable outcome | $0.50 |
| p95 effective task cost | $0.50 |
| Maximum effective task cost | $0.50 |
| Expected net value per attempt | $9.50 |

Effective cost = model/tool spend + human review + remediation + incident loss.

## Counterfactual

Baseline: **fixture human-only workflow**

| Measure | Agent | Baseline |
|---|---:|---:|
| Cost per acceptable outcome | $0.50 | $6.00 |
| Expected net value per attempt | $9.50 | $4.00 |
| Incremental net value per attempt | $5.50 | N/A |

## Gate results

- **PASS · gate.acceptable-rate:** acceptable_rate 100.0% >= 100.0%
- **PASS · gate.unit-economics:** cost_per_acceptable_outcome $0.50 <= $1.00
- **PASS · gate.tail-cost:** p95_task_cost $0.50 <= $1.00
- **PASS · gate.net-value:** expected_net_value_per_attempt $9.50 >= $5.00
- **PASS · gate.counterfactual:** incremental_net_value_vs_baseline $5.50 >= $1.00
- **PASS · gate.runtime-caps:** all tasks remain within call and trace-cost caps

## Policy breaches

- None

## Diagnostic findings

- None

## Claim boundary

The result is only as reliable as the trace coverage, outcome labels, cost allocation, counterfactual, enabled checks, and observation window. When enabled gates do not supply the fixed required coverage, the engine returns INCOMPLETE. A repeated tool shape or graph cycle is a diagnostic warning, not semantic proof of a loop or deadlock.
