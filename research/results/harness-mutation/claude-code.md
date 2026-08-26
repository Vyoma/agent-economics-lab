# Harness Mutation Score

- Baseline decision: **ASSIST**
- Gate removals injected: **6**
- Killed by the fixed contract: **6 / 6** (100.0%)
- Survived under dynamic coverage: **1**
- False SCALE transitions: **1**

The kill rate is the score for *this* harness. The dynamic-coverage column
shows what an engine that derives its requirements from whichever checks
happen to be enabled would have returned instead.

| Removed coverage | Checks removed | Fixed contract | Dynamic coverage |
|---|---|---|---|
| `business_value` | `gate.net-value` | INCOMPLETE | ASSIST |
| `counterfactual` | `gate.counterfactual` | INCOMPLETE | ASSIST |
| `outcome_quality` | `gate.acceptable-rate` | INCOMPLETE | SCALE  ← survives |
| `runtime_caps` | `gate.runtime-caps` | INCOMPLETE | ASSIST |
| `tail_risk` | `gate.tail-cost` | INCOMPLETE | ASSIST |
| `unit_economics` | `gate.unit-economics` | INCOMPLETE | ASSIST |

A gate whose removal still yields SCALE is not load-bearing: the harness
cannot tell whether that evidence was ever collected. A missing gate is not
a passing gate.
