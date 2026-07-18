# False-Green Benchmark Results

- Synthetic scenarios: **98**
- Single-module ablation comparisons: **588**
- Comparisons whose complete result was not SCALE: **510**
- False SCALE results when missing coverage was silently ignored: **23**
- Unsafe false-green rate among non-SCALE comparisons: **4.5%**
- False SCALE results with fail-safe coverage enabled: **0**

| Removed assurance dimension | Unsafe false-green decisions |
|---|---:|
| `outcome_quality` | 2 |
| `unit_economics` | 1 |
| `tail_risk` | 8 |
| `business_value` | 1 |
| `counterfactual` | 3 |
| `runtime_caps` | 8 |

This is a deterministic synthetic stress test of routing semantics, not an
estimate of how often production systems make false-green decisions.
