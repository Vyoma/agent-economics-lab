# Agent Economic Assurance Case

**Decision: STOP**

This is an evidence-based routing decision: SCALE autonomously, ASSIST with human/control coverage, or STOP until the economics change.

## Assurance manifest

- Source adapter: `source.public-swebench-mini-agent@1`
- Evidence digest: `2d063279479ebeff05654482a77ad53eb6076441315e462b1881e0c56e5a4394`
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
| Attempts | 20 |
| Acceptable outcomes | 14 (70.0%) |
| Total effective cost | $8.44 |
| Cost per acceptable outcome | $0.60 |
| p95 effective task cost | $1.36 |
| Maximum effective task cost | $1.42 |
| Expected net value per attempt | $-0.42 |

Effective cost = model/tool spend + human review + remediation + incident loss.

## Counterfactual

Baseline: **mini-swe-agent + claude-4.5-haiku-high on the same 20 tasks**

| Measure | Agent | Baseline |
|---|---:|---:|
| Cost per acceptable outcome | $0.60 | $0.49 |
| Expected net value per attempt | $-0.42 | $-0.27 |
| Incremental net value per attempt | $-0.15 | N/A |

## Gate results

- **PASS · gate.acceptable-rate:** acceptable_rate 70.0% >= 55.0%
- **FAIL · gate.unit-economics:** cost_per_acceptable_outcome $0.60 > $0.49
- **FAIL · gate.tail-cost:** p95_task_cost $1.36 > $0.52
- **FAIL · gate.net-value:** expected_net_value_per_attempt $-0.42 < $0.00
- **FAIL · gate.counterfactual:** incremental_net_value_vs_baseline $-0.15 < $0.00
- **FAIL · gate.runtime-caps:** django__django-15128: $0.6546 trace cost > cap of $0.6172
- **FAIL · gate.runtime-caps:** matplotlib__matplotlib-25775: $1.3607 trace cost > cap of $0.6172
- **FAIL · gate.runtime-caps:** pylint-dev__pylint-4551: $1.4207 trace cost > cap of $0.6172

## Policy breaches

- cost_per_acceptable_outcome $0.60 > $0.49
- p95_task_cost $1.36 > $0.52
- expected_net_value_per_attempt $-0.42 < $0.00
- incremental_net_value_vs_baseline $-0.15 < $0.00
- django__django-15128: $0.6546 trace cost > cap of $0.6172
- matplotlib__matplotlib-25775: $1.3607 trace cost > cap of $0.6172
- pylint-dev__pylint-4551: $1.4207 trace cost > cap of $0.6172

## Diagnostic findings

- None

## Claim boundary

The result is only as reliable as the trace coverage, outcome labels, cost allocation, counterfactual, enabled checks, and observation window. When enabled gates do not supply the fixed required coverage, the engine returns INCOMPLETE. A repeated tool shape or graph cycle is a diagnostic warning, not semantic proof of a loop or deadlock.
