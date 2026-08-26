# Gate Removal Conformance

- Baseline decision: **ASSIST**
- Gate removals injected: **6**
- Fail-closed conformance: **held** (6 / 6 removals refused)
- Pivotal for this bundle under dynamic coverage: **1**

Conformance is an invariant, not a score: a fixed contract refuses every
removal by construction, so this line is a regression test and reads `held`
for any harness. The pivotal count is a sensitivity analysis of *this bundle
under this policy*, not a property of the check set: loosen the thresholds
until nothing fails and every dimension becomes non-pivotal.

| Removed coverage | Checks removed | Fixed contract | Dynamic coverage |
|---|---|---|---|
| `business_value` | `gate.net-value` | INCOMPLETE | ASSIST |
| `counterfactual` | `gate.counterfactual` | INCOMPLETE | ASSIST |
| `outcome_quality` | `gate.acceptable-rate` | INCOMPLETE | SCALE  ← survives |
| `runtime_caps` | `gate.runtime-caps` | INCOMPLETE | ASSIST |
| `tail_risk` | `gate.tail-cost` | INCOMPLETE | ASSIST |
| `unit_economics` | `gate.unit-economics` | INCOMPLETE | ASSIST |

The actionable line is unprovided coverage, if any: a required dimension no
enabled check supplies is a contract that cannot be met, and it is the one
result here that is a property of the harness rather than of this bundle.
