# Decision-Coverage Drift Conformance Results

- Synthetic scenarios: **98**
- Single required-gate disablements: **588**
- Disablements whose complete result was not SCALE: **510**
- False SCALE transitions under dynamic coverage: **23**
- Dynamic-coverage transition rate among non-SCALE comparisons: **4.5%**
- Dynamic-coverage transition rate across all disablements: **3.9%**
- Fixed-contract decisions returning INCOMPLETE: **588 / 588**
- False SCALE transitions under the fixed contract: **0**

| Disabled gate coverage | Dynamic-coverage false SCALE transitions |
|---|---:|
| `outcome_quality` | 2 |
| `unit_economics` | 1 |
| `tail_risk` | 8 |
| `business_value` | 1 |
| `counterfactual` | 3 |
| `runtime_caps` | 8 |

```text
disabled gate          false SCALE
outcome_quality      #####                2
unit_economics       ##                   1
tail_risk            #################### 8
business_value       ##                   1
counterfactual       ########             3
runtime_caps         #################### 8
```

The evidence bundle is unchanged in every comparison. The intervention
disables one required gate. The dynamic-coverage engine silently shrinks
its completeness contract; the fixed-contract engine does not.

This is a deterministic synthetic conformance test, not an estimate of
how often production systems experience decision-coverage drift.

All enabled checks passed is not the same claim as all required checks passed.
