# Pre-registered probe sites

Derived mechanically from the shapes of five defects that were live while the suite was green. Committed before any probe is written, so that the misses are counted with the hits.

## The shapes, and the defect each was abstracted from

### S1 — numeric default absorbing an absence  (36 sites)

- **Learned from:** D09
- **Why it hides:** `x or 0.0` and `d.get(k, 0)` cannot distinguish 'zero' from 'not established'. Where the result is summed or divided, an unknown becomes a confident zero and the total understates.

### S2 — formatted number with no check that it is known  (123 sites)

- **Learned from:** D08
- **Why it hides:** A format spec renders whatever it is handed. If the value can be absent, unestablished, or a placeholder, the renderer converts it into a figure with decimal places, which reads as a measurement.

### S3 — ratio whose denominator can be empty  (61 sites)

- **Learned from:** the vacuous closure line
- **Why it hides:** A ratio over nothing is 1.0 or a guarded constant. Printed as a percentage it reads as full marks for work that never happened.

### S4 — early return that answers before consulting its qualifier  (37 sites)

- **Learned from:** D11
- **Why it hides:** A branch that returns a value before reading the parameter that would qualify it is right in the configuration the tests build and unsupported in the one they do not.

### S5 — caller omitting an optional parameter it could supply  (32 sites)

- **Learned from:** D10
- **Why it hides:** A helper takes an optional input and a caller with that input in hand does not pass it. The helper then degrades, correctly, to a weaker answer nobody asked for.

## The 289 sites

### S1 (36)

```
agent_economics/claude_code.py:246  usage.get("input_tokens", 0), label=f"{label}.input_tokens"
agent_economics/claude_code.py:249  usage.get("output_tokens", 0), label=f"{label}.output_tokens"
agent_economics/claude_code.py:252  usage.get("cache_read_input_tokens", 0),
agent_economics/claude_code.py:256  usage.get("cache_creation_input_tokens", 0),
agent_economics/claude_code.py:355  variant["server_tool_use"].get(name, 0)
agent_economics/delegation.py:172  total = self.delegated_cost_usd or 0.0
agent_economics/delegation.py:175  return (total - (self.unaccounted_cost_usd or 0.0)) / total
agent_economics/delegation.py:282  counting it as zero. Reading `direct_cost_usd or 0.0` here instead of the
agent_economics/delegation.py:320  depth=depth.get(event.event_id, 0),
agent_economics/delegation.py:424  f"${report.unaccounted_cost_usd or 0.0:.4f} of "
agent_economics/delegation.py:425  f"${report.delegated_cost_usd or 0.0:.4f} delegated spend was "
agent_economics/delegation.py:435  f"${report.delegated_cost_usd or 0.0:.4f} delegated"
agent_economics/io.py:57  input_tokens=int(row.get("input_tokens") or 0),
agent_economics/io.py:58  output_tokens=int(row.get("output_tokens") or 0),
agent_economics/io.py:89  business_value_usd=float(row.get("business_value_usd") or 0),
agent_economics/io.py:90  human_minutes=float(row.get("human_minutes") or 0),
agent_economics/io.py:91  remediation_cost_usd=float(row.get("remediation_cost_usd") or 0),
agent_economics/io.py:92  incident_loss_usd=float(row.get("incident_loss_usd") or 0),
agent_economics/kimi_analyst.py:371  n = metrics.get("attempts", 0)
agent_economics/kimi_analyst.py:372  ar = metrics.get("acceptable_rate", 0.0)
agent_economics/kimi_analyst.py:392  f"  total_effective_cost:             ${metrics.get('total_effective_cost_usd', 0):.4f}"
agent_economics/kimi_analyst.py:394  f"  p95_task_cost:                    ${metrics.get('p95_task_cost_usd', 0):.4f}",
agent_economics/kimi_analyst.py:395  f"  max_task_cost:                    ${metrics.get('max_task_cost_usd', 0):.4f}",
agent_economics/kimi_analyst.py:396  f"  expected_net_per_attempt:         ${metrics.get('expected_net_value_per_attempt_usd'
agent_economics/kimi_analyst.py:397  f"  incremental_net_vs_baseline:      ${metrics.get('incremental_net_value_vs_baseline_u
agent_economics/kimi_analyst.py:405  f"  min_acceptable_rate:             {policy.get('min_acceptable_rate', 0):.1%}",
agent_economics/kimi_analyst.py:406  f"  max_cost_per_acceptable_outcome: ${policy.get('max_cost_per_acceptable_outcome_usd',
agent_economics/kimi_analyst.py:407  f"  max_p95_task_cost:               ${policy.get('max_p95_task_cost_usd', 0):.2f}",
agent_economics/kimi_analyst.py:408  f"  min_expected_net_per_attempt:    ${policy.get('min_expected_net_value_per_attempt_us
agent_economics/kimi_analyst.py:409  f"  min_incremental_net_vs_baseline: ${policy.get('min_incremental_net_value_vs_baseline
agent_economics/kimi_analyst.py:410  f"  human_hourly_cost:               ${policy.get('human_hourly_cost_usd', 0):.2f}",
agent_economics/kimi_analyst.py:417  f"  cost_per_attempt:   ${baseline.get('cost_per_attempt_usd', 0):.2f}",
agent_economics/kimi_analyst.py:418  f"  acceptable_rate:    {baseline.get('acceptable_rate', 0):.1%}",
agent_economics/kimi_analyst.py:419  f"  value_per_acceptable: ${baseline.get('value_per_acceptable_outcome_usd', 0):.2f}",
agent_economics/kimi_judge.py:303  incident_loss = float(rubric.get("incident_loss_usd_if_not_acceptable", 0.0))
agent_economics/kimi_judge.py:460  kimi_resp.get("overall_score", 0),
```

### S2 (123)

```
agent_economics/audit.py:255  lines += ["", f"${report.delegated_spend_unassessed:.4f} of delegated "
agent_economics/audit.py:256  f"spend is unassessed; closure {report.closure:.0%}."]
agent_economics/audit.py:262  lines += ["", f"Closure {report.closure:.0%}. The unassessed spend "
agent_economics/audit.py:283  f"(closure {report.closure:.0%}, measured {basis})."
agent_economics/checks.py:51  f"acceptable_rate {view.acceptable_rate:.1%} "
agent_economics/checks.py:52  f"{'<' if failed else '>='} {threshold:.1%}"
agent_economics/checks.py:64  f"cost_per_acceptable_outcome ${observed:.2f} "
agent_economics/checks.py:65  f"{'>' if failed else '<='} ${threshold:.2f}"
agent_economics/checks.py:76  f"p95_task_cost ${view.p95_task_cost_usd:.2f} "
agent_economics/checks.py:77  f"{'>' if failed else '<='} ${threshold:.2f}"
agent_economics/checks.py:89  f"${view.expected_net_value_per_attempt_usd:.2f} "
agent_economics/checks.py:90  f"{'<' if failed else '>='} ${threshold:.2f}"
agent_economics/checks.py:102  f"${view.incremental_net_value_vs_baseline_usd:.2f} "
agent_economics/checks.py:103  f"{'<' if failed else '>='} ${threshold:.2f}"
agent_economics/checks.py:135  f"{task_id}: ${trace_cost:.4f} trace cost > cap of "
agent_economics/checks.py:136  f"${view.policy.max_trace_cost_per_task_usd:.4f}"
agent_economics/delegation.py:414  f"measured by count ({report.closure:.1%}), not by spend. "
agent_economics/delegation.py:415  f"The required {minimum_closure:.1%} is a share of spend and "
agent_economics/delegation.py:424  f"${report.unaccounted_cost_usd or 0.0:.4f} of "
agent_economics/delegation.py:425  f"${report.delegated_cost_usd or 0.0:.4f} delegated spend was "
agent_economics/delegation.py:426  f"never undertaken for assessment; closure {report.closure:.1%} "
agent_economics/delegation.py:427  f"below the required {minimum_closure:.1%}"
agent_economics/delegation.py:435  f"${report.delegated_cost_usd or 0.0:.4f} delegated"
agent_economics/frontier.py:786  f"breakage upper bound {breakage_upper:.3%} exceeds "
agent_economics/frontier.py:787  f"{plan.max_breakage_rate:.3%}"
agent_economics/frontier.py:791  f"cost-reduction lower bound {cost_lower:.3%} is below "
agent_economics/frontier.py:792  f"{plan.min_cost_reduction_rate:.3%}"
agent_economics/frontier_report.py:23  return f"${amount:.2f}"
agent_economics/frontier_report.py:79  f"- Maximum harmful-regression risk: {case.plan.max_breakage_rate:.1%}",
agent_economics/frontier_report.py:80  f"- Minimum full-cost reduction: {case.plan.min_cost_reduction_rate:.1%}",
agent_economics/frontier_report.py:81  f"- Target nominal familywise confidence: {case.plan.confidence_level:.1%}",
agent_economics/frontier_report.py:85  f"{tail_draws:.1f}" if tail_draws is not None else "- Expected adjusted-tail draws: N/A"
agent_economics/frontier_report.py:105  f"{arm.acceptable_rate:.1%} | {_money(arm.mean_effective_cost_usd)} | "
agent_economics/frontier_report.py:128  f"({comparison.conditional_breakage_rate:.1%})"
agent_economics/frontier_report.py:135  f"({comparison.breakage_rate:.1%}) | "
agent_economics/frontier_report.py:136  f"{comparison.breakage_rate_upper:.1%} | "
agent_economics/frontier_report.py:138  f"{comparison.acceptable_rate_delta:+.1%} | "
agent_economics/frontier_report.py:139  f"{comparison.mean_cost_reduction_rate:.1%} | "
agent_economics/frontier_report.py:140  f"{comparison.cost_reduction_rate_lower:.1%} | "
agent_economics/frontier_report.py:265  f'<text x="{left + plot_width / 2:.1f}" y="{height - 22}" text-anchor="middle" fill="#c9
agent_economics/frontier_report.py:266  f'<text x="20" y="{top + plot_height / 2:.1f}" transform="rotate(-90 20 {top + plot_heig
agent_economics/frontier_report.py:274  f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#21262d"/>
agent_economics/frontier_report.py:275  f'<text x="{x:.1f}" y="{top + plot_height + 22}" text-anchor="middle" fill="#8b949e" fon
agent_economics/frontier_report.py:282  f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#21262d"/
agent_economics/frontier_report.py:283  f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" fill="#8b949e" font-family="ui
agent_economics/frontier_report.py:297  f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" stroke="#f0f6fc" stroke-
agent_economics/frontier_report.py:298  f'<text x="{label_x:.1f}" y="{y - 10:.1f}" text-anchor="{label_anchor}" fill="#f0f6fc" f
agent_economics/kimi_analyst.py:225  f"Tasks: {n} attempts, {accepted} acceptable ({case.acceptable_rate:.1%}), "
agent_economics/kimi_analyst.py:238  return f"{diff:+.1f}pp", status == "FAIL"
agent_economics/kimi_analyst.py:241  return f"{diff:+.4f}", status == "FAIL"
agent_economics/kimi_analyst.py:247  f"  gate.acceptable-rate:  {case.acceptable_rate:.1%} vs {policy.min_acceptable_rate:.1%
agent_economics/kimi_analyst.py:248  f"  | gap: {ar_diff:+.1f}pp  | {'FAIL → ASSIST' if ar_fail else 'PASS'}"
agent_economics/kimi_analyst.py:256  f"  gate.unit-economics:   ${case.cost_per_acceptable_outcome_usd:.4f} vs ${policy.max_c
agent_economics/kimi_analyst.py:257  f"  | gap: ${ue_diff:+.4f}  | {'FAIL → ASSIST' if ue_fail else 'PASS'}"
agent_economics/kimi_analyst.py:266  f"  gate.tail-cost:        ${case.p95_task_cost_usd:.4f} vs ${policy.max_p95_task_cost_u
agent_economics/kimi_analyst.py:267  f"  | gap: ${tc_diff:+.4f}  | {'FAIL → ASSIST' if tc_fail else 'PASS'}"
agent_economics/kimi_analyst.py:274  f"  gate.net-value:        ${case.expected_net_value_per_attempt_usd:.4f} vs ${policy.mi
agent_economics/kimi_analyst.py:275  f"  | gap: ${nv_diff:+.4f}  | {'FAIL → STOP' if nv_fail else 'PASS'}"
agent_economics/kimi_analyst.py:282  f"  gate.counterfactual:   ${case.incremental_net_value_vs_baseline_usd:.4f} vs ${policy
agent_economics/kimi_analyst.py:283  f"  | gap: ${cf_diff:+.4f}  | {'FAIL → STOP' if cf_fail else 'PASS'}"
agent_economics/kimi_analyst.py:290  f"  min_acceptable_rate:             {policy.min_acceptable_rate:.1%}",
agent_economics/kimi_analyst.py:291  f"  max_cost_per_acceptable_outcome: ${policy.max_cost_per_acceptable_outcome_usd:.2f}",
agent_economics/kimi_analyst.py:292  f"  max_p95_task_cost:               ${policy.max_p95_task_cost_usd:.2f}",
agent_economics/kimi_analyst.py:293  f"  max_trace_cost_per_task:         ${policy.max_trace_cost_per_task_usd:.4f}",
agent_economics/kimi_analyst.py:295  f"  min_expected_net_per_attempt:    ${policy.min_expected_net_value_per_attempt_usd:.2f
agent_economics/kimi_analyst.py:296  f"  min_incremental_net_vs_baseline: ${policy.min_incremental_net_value_vs_baseline_usd:
agent_economics/kimi_analyst.py:297  f"  human_hourly_cost:               ${policy.human_hourly_cost_usd:.2f}",
agent_economics/kimi_analyst.py:309  f"  total_effective_cost:             ${case.total_effective_cost_usd:.4f}",
agent_economics/kimi_analyst.py:312  lines.append(f"  cost_per_acceptable_outcome:      ${case.cost_per_acceptable_outcome_us
agent_economics/kimi_analyst.py:316  f"  p95_task_cost:                    ${case.p95_task_cost_usd:.4f}",
agent_economics/kimi_analyst.py:317  f"  max_task_cost:                    ${case.max_task_cost_usd:.4f}",
agent_economics/kimi_analyst.py:318  f"  expected_net_per_attempt:         ${case.expected_net_value_per_attempt_usd:.4f}",
agent_economics/kimi_analyst.py:319  f"  incremental_net_vs_baseline:      ${case.incremental_net_value_vs_baseline_usd:.4f}"
agent_economics/kimi_analyst.py:328  f"  cost_per_acceptable:        ${case.cost_per_acceptable_outcome_usd:.2f}     ${baseli
agent_economics/kimi_analyst.py:329  f"  expected_net_per_attempt:   ${case.expected_net_value_per_attempt_usd:.2f}      ${ba
agent_economics/kimi_analyst.py:330  f"  incremental_net:            ${case.incremental_net_value_vs_baseline_usd:.2f}      N
agent_economics/kimi_analyst.py:353  f"  {t.task_id}: effective_cost=${t.effective_cost_usd:.4f}"
agent_economics/kimi_analyst.py:354  f"  (trace=${t.trace_cost_usd:.4f}, human=${t.human_cost_usd:.4f},"
agent_economics/kimi_analyst.py:355  f"  remediation=${t.remediation_cost_usd:.4f}, incident=${t.incident_loss_usd:.4f})"
agent_economics/kimi_analyst.py:379  f"Tasks: {n} attempts, {accepted} acceptable ({ar:.1%}), {n - accepted} not-acceptable",
agent_economics/kimi_analyst.py:392  f"  total_effective_cost:             ${metrics.get('total_effective_cost_usd', 0):.4f}"
agent_economics/kimi_analyst.py:393  f"  cost_per_acceptable_outcome:      ${metrics.get('cost_per_acceptable_outcome_usd') o
agent_economics/kimi_analyst.py:394  f"  p95_task_cost:                    ${metrics.get('p95_task_cost_usd', 0):.4f}",
agent_economics/kimi_analyst.py:395  f"  max_task_cost:                    ${metrics.get('max_task_cost_usd', 0):.4f}",
agent_economics/kimi_analyst.py:396  f"  expected_net_per_attempt:         ${metrics.get('expected_net_value_per_attempt_usd'
agent_economics/kimi_analyst.py:397  f"  incremental_net_vs_baseline:      ${metrics.get('incremental_net_value_vs_baseline_u
agent_economics/kimi_analyst.py:405  f"  min_acceptable_rate:             {policy.get('min_acceptable_rate', 0):.1%}",
agent_economics/kimi_analyst.py:406  f"  max_cost_per_acceptable_outcome: ${policy.get('max_cost_per_acceptable_outcome_usd',
agent_economics/kimi_analyst.py:407  f"  max_p95_task_cost:               ${policy.get('max_p95_task_cost_usd', 0):.2f}",
agent_economics/kimi_analyst.py:408  f"  min_expected_net_per_attempt:    ${policy.get('min_expected_net_value_per_attempt_us
agent_economics/kimi_analyst.py:409  f"  min_incremental_net_vs_baseline: ${policy.get('min_incremental_net_value_vs_baseline
agent_economics/kimi_analyst.py:410  f"  human_hourly_cost:               ${policy.get('human_hourly_cost_usd', 0):.2f}",
agent_economics/kimi_analyst.py:417  f"  cost_per_attempt:   ${baseline.get('cost_per_attempt_usd', 0):.2f}",
agent_economics/kimi_analyst.py:418  f"  acceptable_rate:    {baseline.get('acceptable_rate', 0):.1%}",
agent_economics/kimi_analyst.py:419  f"  value_per_acceptable: ${baseline.get('value_per_acceptable_outcome_usd', 0):.2f}",
agent_economics/kimi_judge.py:108  f"criterion weights must sum to 1.0 (got {total_weight:.3f})"
agent_economics/kimi_judge.py:511  f"Rate: {n_acceptable / n_judged:.0%}" if n_judged else
agent_economics/label_error.py:223  print(f"  success rate r        {r:>8.2%}")
agent_economics/label_error.py:224  print(f"  slack s               {s:>8.2%}")
agent_economics/label_error.py:226  print(f"  tolerable net bias    {e:>8.2%}   |false accepts - false rejects| / n")
agent_economics/label_error.py:227  print(f"  sufficient agreement  {1 - e:>8.2%}   worst case, if all error is one-directio
agent_economics/label_error.py:267  print(f"  P1  ratio distortion u_hat/u = a/(a+D)      max error {p1:.2e}  "
agent_economics/label_error.py:271  print(f"  P2  amplification eps/(r-eps) is exact      max error {p2:.2e}  "
agent_economics/label_error.py:277  print(f"      {r:>6.2f} {eps:>7.2%} {exact:>9.2%} {pred:>9.2%} "
agent_economics/label_error.py:278  f"{exact/pred:>7.2f}")
agent_economics/label_error.py:286  f"excess over 1-task quantisation {p4:.4f}  "
agent_economics/label_error.py:300  print(f"  {fp:>14} {fn:>14} {1 - (fp + fn) / n:>10.0%} "
agent_economics/label_error.py:301  f"{abs(a / (a + d) - 1):>11.2%}")
agent_economics/label_error.py:324  print(f"  {r:>12.0%} {s:>7.0%} {e:>8.2%} {1 - e:>9.1%}  {verdict:>12}")
agent_economics/label_error.py:332  print(f"    slack up to {s:>5.0%}:  {running[0]:>2} of {running[1]:>2} sufficient")
agent_economics/provenance.py:275  f"{record.method} {record.agreement:.2f} below {floor:.2f}"
agent_economics/provenance.py:334  else f"{s.instrument} at {s.agreement:.2f} on "
agent_economics/report.py:62  f"| Acceptable outcomes | {accepted} ({case.acceptable_rate:.1%}) |",
agent_economics/report.py:63  f"| Total effective cost | ${case.total_effective_cost_usd:.2f} |",
agent_economics/report.py:66  f"${case.cost_per_acceptable_outcome_usd:.2f} |"
agent_economics/report.py:68  f"| p95 effective task cost | ${case.p95_task_cost_usd:.2f} |",
agent_economics/report.py:69  f"| Maximum effective task cost | ${case.max_task_cost_usd:.2f} |",
agent_economics/report.py:72  f"${case.expected_net_value_per_attempt_usd:.2f} |"
agent_economics/report.py:85  f"${case.cost_per_acceptable_outcome_usd:.2f} | "
agent_economics/report.py:86  f"${case.baseline.cost_per_acceptable_outcome_usd:.2f} |"
agent_economics/report.py:90  f"${case.expected_net_value_per_attempt_usd:.2f} | "
agent_economics/report.py:91  f"${case.baseline.expected_net_value_per_attempt_usd:.2f} |"
agent_economics/report.py:95  f"${case.incremental_net_value_vs_baseline_usd:.2f} | N/A |"
```

### S3 (61)

```
agent_economics/assurance.py:210  human_cost = outcome.human_minutes * policy.human_hourly_cost_usd / 60
agent_economics/assurance.py:320  acceptable_rate = sum(t.acceptable for t in tasks) / len(tasks)
agent_economics/assurance.py:335  acceptable_rate = accepted / len(tasks)
agent_economics/assurance.py:345  expected_net = (realized_value - total_cost) / len(tasks)
agent_economics/assurance.py:339  cost_per_acceptable = total_cost / accepted if accepted else math.inf
agent_economics/claude_code.py:1360  token_cost = (
agent_economics/claude_code_tree.py:452  subagent_dir = parent_path.with_suffix("") / "subagents"
agent_economics/cli.py:418  subagent_dir = source_path.with_suffix("") / "subagents"
agent_economics/cli.py:518  (output_dir / name).write_text(content, encoding="utf-8")
agent_economics/cli.py:510  if not (verify_dir / name).exists()
agent_economics/cli.py:511  or (verify_dir / name).read_text(encoding="utf-8") != content
agent_economics/delegation.py:175  return (total - (self.unaccounted_cost_usd or 0.0)) / total
agent_economics/delegation.py:171  return (self.total - len(self.unaccounted)) / self.total
agent_economics/frontier.py:200  adjusted_alpha = (1 - confidence) / (2 * (len(arms) - 1))
agent_economics/frontier.py:502  low = observed / trials
agent_economics/frontier.py:724  adjusted_alpha = (1 - plan.confidence_level) / (2 * candidate_count)
agent_economics/frontier.py:293  adjusted_alpha = (1 - confidence) / (2 * valid_candidate_count)
agent_economics/frontier.py:505  midpoint = (low + high) / 2
agent_economics/frontier.py:529  (reference_total - math.fsum(candidate_costs)) / reference_total
agent_economics/frontier.py:576  cost = case.total_effective_cost_usd / len(case.tasks)
agent_economics/frontier.py:406  task_manifest_path = (plan_file.parent / plan.task_manifest_path).resolve()
agent_economics/frontier.py:581  other_cost = other.total_effective_cost_usd / len(other.tasks)
agent_economics/frontier.py:750  sum(
agent_economics/frontier.py:447  bundle_path = (plan_file.parent / relative_path).resolve()
agent_economics/frontier.py:541  (sampled_reference - sampled_candidate) / sampled_reference
agent_economics/frontier.py:559  case.total_effective_cost_usd / len(case.tasks)
agent_economics/frontier.py:771  canonical_float(harmful / reference_acceptable_tasks)
agent_economics/frontier.py:870  case.plan.bootstrap_samples
agent_economics/frontier.py:802  breakage_rate=canonical_float(harmful / len(ordered_tasks)),
agent_economics/frontier.py:822  cases[arm_id].total_effective_cost_usd / len(cases[arm_id].tasks),
agent_economics/frontier_report.py:29  case.plan.bootstrap_samples
agent_economics/frontier_report.py:269  fraction = step / 4
agent_economics/frontier_report.py:251  return left + (value - min_cost) / cost_span * plot_width
agent_economics/frontier_report.py:254  return top + (max_quality - value) / quality_span * plot_height
agent_economics/frontier_report.py:265  f'<text x="{left + plot_width / 2:.1f}" y="{height - 22}" text-anchor="middle" fill="#c9
agent_economics/frontier_report.py:266  f'<text x="20" y="{top + plot_height / 2:.1f}" transform="rotate(-90 20 {top + plot_heig
agent_economics/frontier_report.py:266  f'<text x="20" y="{top + plot_height / 2:.1f}" transform="rotate(-90 20 {top + plot_heig
agent_economics/github_action.py:165  bundle_path = Path(directory) / "converted-bundle.json"
agent_economics/kimi_judge.py:431  sleep_s = (1.0 / rate_limit) if rate_limit > 0 else 0.0
agent_economics/kimi_judge.py:511  f"Rate: {n_acceptable / n_judged:.0%}" if n_judged else
agent_economics/label_error.py:191  return r * s / (1.0 + s)
agent_economics/label_error.py:47  return self.a / self.n
agent_economics/label_error.py:63  return (realized - self.C) / self.n
agent_economics/label_error.py:98  predicted = w.a / (w.a + delta)
agent_economics/label_error.py:99  observed = w.unit_cost(judged) / w.unit_cost()
agent_economics/label_error.py:113  exact = epsilon / (r - epsilon) if r > epsilon else math.inf
agent_economics/label_error.py:114  return exact, epsilon / r
agent_economics/label_error.py:148  epsilon = k / n
agent_economics/label_error.py:149  observed = abs(w.unit_cost(tuple(judged)) - w.unit_cost()) / w.unit_cost()
agent_economics/label_error.py:170  epsilon = (fp + fn) / n
agent_economics/label_error.py:57  return self.C / judged if judged else math.inf
agent_economics/label_error.py:199  r = a / n
agent_economics/label_error.py:201  u = C / a
agent_economics/label_error.py:212  empirical = flips / n           # the true epsilon at which it flips
agent_economics/label_error.py:207  if C / (a - k) > tau:
agent_economics/label_error.py:216  worst = max(worst, abs(empirical - predicted) - 1.0 / n)
agent_economics/label_error.py:278  f"{exact/pred:>7.2f}")
agent_economics/label_error.py:300  print(f"  {fp:>14} {fn:>14} {1 - (fp + fn) / n:>10.0%} "
agent_economics/label_error.py:301  f"{abs(a / (a + d) - 1):>11.2%}")
agent_economics/models.py:109  return (
agent_economics/models.py:141  return self.cost_per_attempt_usd / self.acceptable_rate
```

### S4 (37)

```
agent_economics/cli.py:615  in main(): return 2
agent_economics/cli.py:296  in main(): return 0
agent_economics/cli.py:366  in main(): return 0
agent_economics/cli.py:405  in main(): return 0
agent_economics/cli.py:487  in main(): return 0
agent_economics/cli.py:581  in main(): return 0
agent_economics/cli.py:614  in main(): return 0
agent_economics/cli.py:365  in main(): return 1
agent_economics/cli.py:435  in main(): return 2
agent_economics/cli.py:495  in main(): return 2
agent_economics/cli.py:591  in main(): return 0
agent_economics/cli.py:275  in main(): return 2
agent_economics/cli.py:284  in main(): return 2
agent_economics/cli.py:305  in main(): return 2
agent_economics/cli.py:319  in main(): return 2
agent_economics/cli.py:325  in main(): return 2
agent_economics/cli.py:346  in main(): return 2
agent_economics/cli.py:485  in main(): return 2
agent_economics/cli.py:500  in main(): return 2
agent_economics/cli.py:515  in main(): return 1
agent_economics/cli.py:557  in main(): return 2
agent_economics/cli.py:570  in main(): return 2
agent_economics/cli.py:594  in main(): return 2
agent_economics/cli.py:605  in main(): return 2
agent_economics/delegation.py:228  in _event_cost(): return 0.0
agent_economics/delegation.py:169  in closure(): return 1.0
agent_economics/frontier.py:472  in _binomial_cdf(): return 1.0
agent_economics/frontier.py:501  in clopper_pearson_upper(): return 1.0
agent_economics/github_action.py:313  in main(): return 0
agent_economics/kimi_analyst.py:565  in _main(): return 0
agent_economics/kimi_analyst.py:559  in _main(): return 2
agent_economics/kimi_judge.py:544  in _main(): return 0
agent_economics/kimi_judge.py:547  in _main(): return 2
agent_economics/label_error.py:190  in epsilon_star(): return 0.0
agent_economics/label_error.py:233  in _one_answer(): return 0
agent_economics/label_error.py:333  in main(): return 0
agent_economics/models.py:102  in cost(): return 0.0
```

### S5 (32)

```
agent_economics/assurance.py:524  make_evidence_bundle(...) omits declared_delegations, dependency_edges, label_source, source_version, task_manifest  [evidence = make_evidence_bundle(]
agent_economics/assurance.py:300  validate_evidence_bundle(...) omits label, require_explicit_costs, require_task_manifest  [evidence_problems = validate_evidence_bu]
agent_economics/audit.py:136  assess_bundle_closure(...) omits declared, delegation_tools  [closure = assess_bundle_closure(bundle)]
agent_economics/checks.py:144  _result(...) omits task_id  [_result(]
agent_economics/checks.py:55  _result(...) omits task_id  [results=(_result("gate.acceptable-rate",]
agent_economics/checks.py:68  _result(...) omits task_id  [results=(_result("gate.unit-economics", ]
agent_economics/checks.py:80  _result(...) omits task_id  [results=(_result("gate.tail-cost", faile]
agent_economics/checks.py:93  _result(...) omits task_id  [results=(_result("gate.net-value", faile]
agent_economics/checks.py:106  _result(...) omits task_id  [results=(_result("gate.counterfactual", ]
agent_economics/claude_code.py:768  _inspect_claude_code_jsonl_bytes(...) omits allow_empty_tasks  [return _inspect_claude_code_jsonl_bytes(]
agent_economics/claude_code.py:520  _normalize_usage(...) omits allow_zero  [usage = _normalize_usage(]
agent_economics/claude_code_tree.py:494  _inspect_claude_code_jsonl_bytes(...) omits allow_empty_tasks  [parent = _inspect_claude_code_jsonl_byte]
agent_economics/cli.py:326  audit(...) omits policy  [report = audit(]
agent_economics/cli.py:349  assess_bundle_closure(...) omits delegation_tools  [report = assess_bundle_closure(bundle, d]
agent_economics/cli.py:545  load_csv_bundle(...) omits label_source  [else load_csv_bundle(**csv_paths)]
agent_economics/evidence.py:451  validate_evidence_bundle(...) omits label, require_explicit_costs, require_task_manifest  [problems = validate_evidence_bundle(bund]
agent_economics/evidence.py:86  _numeric_issue(...) omits maximum  [issue = _numeric_issue(]
agent_economics/evidence.py:120  _numeric_issue(...) omits integer, maximum, minimum  [issue = _numeric_issue(]
agent_economics/evidence.py:180  _numeric_issue(...) omits integer, maximum, minimum  [issue = _numeric_issue(f"{label}: rate {]
agent_economics/evidence.py:201  _numeric_issue(...) omits integer, maximum, minimum  [issue = _numeric_issue(f"{outcome_label}]
agent_economics/evidence.py:266  _numeric_issue(...) omits integer  [issue = _numeric_issue(]
agent_economics/evidence.py:305  _numeric_issue(...) omits integer  [issue = _numeric_issue(]
agent_economics/evidence.py:263  _numeric_issue(...) omits integer, maximum, minimum  [issue = _numeric_issue(f"{label}: baseli]
agent_economics/evidence.py:291  _numeric_issue(...) omits integer, maximum, minimum  [issue = _numeric_issue(]
agent_economics/evidence.py:300  _numeric_issue(...) omits integer, maximum  [issue = _numeric_issue(]
agent_economics/evidence.py:314  _numeric_issue(...) omits maximum  [issue = _numeric_issue(]
agent_economics/io.py:140  make_evidence_bundle(...) omits declared_delegations, task_manifest  [return make_evidence_bundle(]
agent_economics/kimi_analyst.py:507  _call_kimi_analyst(...) omits reasoning_effort  [kimi_resp = _call_kimi_analyst(context, ]
agent_economics/kimi_analyst.py:529  _call_kimi_analyst(...) omits reasoning_effort  [kimi_resp = _call_kimi_analyst(context, ]
agent_economics/kimi_client.py:398  assert_mfjs_compatible(...) omits path  [assert_mfjs_compatible(response_format)]
agent_economics/kimi_judge.py:541  judge(...) omits allow_unjudged  [judge(args.task_results, args.rubric, ar]
agent_economics/otel_genai.py:808  make_evidence_bundle(...) omits declared_delegations  [bundle = make_evidence_bundle(]
```

## Why the coarse shapes are not the method

289 sites in a package this size is a detector with no specificity. Probing them one at a time would be a worse use of attention than reading the code. Reported here rather than quietly dropped, because a search that only shows its narrowed form is hiding how it was narrowed.

## The narrowing that has support

All five known defects share a sharper form than any shape above: the same quantity computed two ways, with one way wrong. That is why each read fine in isolation and why a test exercising either path alone passed. Divergence is enumerable, and there are far fewer of them.

**17 divergences**, against 289 coarse sites.

### `_inspect_claude_code_jsonl_bytes(..., allow_empty_tasks=)`  (inconsistent-caller)

- passes / resolves (1): `agent_economics/claude_code_tree.py:538`
- omits / reads raw (2): `agent_economics/claude_code.py:768`, `agent_economics/claude_code_tree.py:494`

### `_normalize_usage(..., allow_zero=)`  (inconsistent-caller)

- passes / resolves (1): `agent_economics/claude_code.py:480`
- omits / reads raw (1): `agent_economics/claude_code.py:520`

### `_numeric_issue(..., integer=)`  (inconsistent-caller)

- passes / resolves (2): `agent_economics/evidence.py:86`, `agent_economics/evidence.py:314`
- omits / reads raw (8): `agent_economics/evidence.py:120`, `agent_economics/evidence.py:180`, `agent_economics/evidence.py:201`, `agent_economics/evidence.py:266`, `agent_economics/evidence.py:305`, `agent_economics/evidence.py:263`

### `_numeric_issue(..., maximum=)`  (inconsistent-caller)

- passes / resolves (2): `agent_economics/evidence.py:266`, `agent_economics/evidence.py:305`
- omits / reads raw (8): `agent_economics/evidence.py:86`, `agent_economics/evidence.py:120`, `agent_economics/evidence.py:180`, `agent_economics/evidence.py:201`, `agent_economics/evidence.py:263`, `agent_economics/evidence.py:291`

### `_numeric_issue(..., minimum=)`  (inconsistent-caller)

- passes / resolves (5): `agent_economics/evidence.py:86`, `agent_economics/evidence.py:266`, `agent_economics/evidence.py:305`, `agent_economics/evidence.py:300`, `agent_economics/evidence.py:314`
- omits / reads raw (5): `agent_economics/evidence.py:120`, `agent_economics/evidence.py:180`, `agent_economics/evidence.py:201`, `agent_economics/evidence.py:263`, `agent_economics/evidence.py:291`

### `_result(..., task_id=)`  (inconsistent-caller)

- passes / resolves (2): `agent_economics/checks.py:121`, `agent_economics/checks.py:131`
- omits / reads raw (6): `agent_economics/checks.py:144`, `agent_economics/checks.py:55`, `agent_economics/checks.py:68`, `agent_economics/checks.py:80`, `agent_economics/checks.py:93`, `agent_economics/checks.py:106`

### `assert_mfjs_compatible(..., path=)`  (inconsistent-caller)

- passes / resolves (3): `agent_economics/kimi_client.py:193`, `agent_economics/kimi_client.py:196`, `agent_economics/kimi_client.py:191`
- omits / reads raw (1): `agent_economics/kimi_client.py:398`

### `assess_bundle_closure(..., declared=)`  (inconsistent-caller)

- passes / resolves (1): `agent_economics/cli.py:349`
- omits / reads raw (1): `agent_economics/audit.py:136`

### `make_evidence_bundle(..., declared_delegations=)`  (inconsistent-caller)

- passes / resolves (3): `agent_economics/adapters.py:76`, `agent_economics/claude_code.py:1415`, `agent_economics/unsupplied.py:75`
- omits / reads raw (3): `agent_economics/assurance.py:524`, `agent_economics/io.py:140`, `agent_economics/otel_genai.py:808`

### `make_evidence_bundle(..., dependency_edges=)`  (inconsistent-caller)

- passes / resolves (5): `agent_economics/adapters.py:76`, `agent_economics/claude_code.py:1415`, `agent_economics/io.py:140`, `agent_economics/otel_genai.py:808`, `agent_economics/unsupplied.py:75`
- omits / reads raw (1): `agent_economics/assurance.py:524`

### `make_evidence_bundle(..., label_source=)`  (inconsistent-caller)

- passes / resolves (5): `agent_economics/adapters.py:76`, `agent_economics/claude_code.py:1415`, `agent_economics/io.py:140`, `agent_economics/otel_genai.py:808`, `agent_economics/unsupplied.py:75`
- omits / reads raw (1): `agent_economics/assurance.py:524`

### `make_evidence_bundle(..., source_version=)`  (inconsistent-caller)

- passes / resolves (5): `agent_economics/adapters.py:76`, `agent_economics/claude_code.py:1415`, `agent_economics/io.py:140`, `agent_economics/otel_genai.py:808`, `agent_economics/unsupplied.py:75`
- omits / reads raw (1): `agent_economics/assurance.py:524`

### `make_evidence_bundle(..., task_manifest=)`  (inconsistent-caller)

- passes / resolves (4): `agent_economics/adapters.py:76`, `agent_economics/claude_code.py:1415`, `agent_economics/otel_genai.py:808`, `agent_economics/unsupplied.py:75`
- omits / reads raw (2): `agent_economics/assurance.py:524`, `agent_economics/io.py:140`

### `validate_evidence_bundle(..., label=)`  (inconsistent-caller)

- passes / resolves (3): `agent_economics/claude_code.py:1428`, `agent_economics/frontier.py:621`, `agent_economics/otel_genai.py:820`
- omits / reads raw (2): `agent_economics/assurance.py:300`, `agent_economics/evidence.py:451`

### `validate_evidence_bundle(..., require_explicit_costs=)`  (inconsistent-caller)

- passes / resolves (3): `agent_economics/claude_code.py:1428`, `agent_economics/frontier.py:621`, `agent_economics/otel_genai.py:820`
- omits / reads raw (2): `agent_economics/assurance.py:300`, `agent_economics/evidence.py:451`

### `validate_evidence_bundle(..., require_task_manifest=)`  (inconsistent-caller)

- passes / resolves (3): `agent_economics/claude_code.py:1428`, `agent_economics/frontier.py:621`, `agent_economics/otel_genai.py:820`
- omits / reads raw (2): `agent_economics/assurance.py:300`, `agent_economics/evidence.py:451`

### `direct_cost_usd / .cost()`  (raw-field-vs-resolver)

- passes / resolves (3): `agent_economics/assurance.py:207`, `agent_economics/checks.py:118`, `agent_economics/delegation.py:229`
- omits / reads raw (6): `agent_economics/delegation.py:223`, `agent_economics/delegation.py:224`, `agent_economics/evidence.py:91`, `agent_economics/evidence.py:121`, `agent_economics/models.py:99`, `agent_economics/models.py:100`

## What this list is not

A divergence is not a defect. Two callers may differ for good reason, and a raw read may be correct where no resolution is wanted. This is a pre-registration: the next step is a probe per divergence and an honest count of how many found nothing.

