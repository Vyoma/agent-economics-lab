# Agent Economics Lab

**Your agent passed its evals. Can you prove it should scale?**

[![Tests](https://github.com/Vyoma/agent-economics-lab/actions/workflows/test.yml/badge.svg)](https://github.com/Vyoma/agent-economics-lab/actions/workflows/test.yml)

> **Status: alpha.** This is a research, teaching, and conformance lab—not a
> production authorization layer.

Agent Economics Lab is an executable assurance case for evaluating deployment
decisions about AI-agent workloads. It joins call-level traces to outcome labels,
human work, remediation, incident loss, and a counterfactual baseline—then issues
one bounded decision:

- `INCOMPLETE`: required assurance coverage was removed or never evaluated.
- `SCALE`: the observed system meets its economic and quality policy.
- `ASSIST`: value is positive, but human or deterministic control coverage is needed.
- `STOP`: a required value gate fails, including value versus the named baseline.

This is not another token dashboard. It is the smallest complete system we could
build for answering the question finance, product, risk, and engineering share:
**what did one acceptable outcome actually cost, and what should we do next?**

**Keep your existing observability and evaluation stack. Normalize its offline
exports to the included CSV or JSON boundary, then issue a composable,
vendor-neutral economic assurance case. Fixture-backed vendor-specific mappers are
a contribution lane, not a shipped integration.**

## Run the evidence case

Requires Python 3.10+ and no third-party runtime packages.

```bash
make demo
```

The included eight-task synthetic support scenario produces:

```text
Decision                         ASSIST
Acceptable outcomes              6 / 8 (75.0%)
Total effective cost             $21.02
Cost / acceptable outcome        $3.50
Expected net value / attempt     $3.37
Human-only baseline              $0.60
```

The agent creates more expected value than the baseline, but it is not ready for
unattended scale. Its acceptable rate misses policy, its tail cost is too high, and
one task crosses both the call and trace-cost caps.

Generate a portable Markdown assurance case:

```bash
python3 -m agent_economics evaluate \
  --traces examples/support_trace.csv \
  --outcomes examples/outcomes.csv \
  --rates examples/rates.json \
  --baseline examples/baseline.json \
  --policy examples/policy.json \
  --output assurance-case.md
```

## Research-shaped, not demo-shaped

The repository includes a deterministic benchmark for the central modularity
claim: can deleting required evidence silently manufacture a green decision?

```bash
make benchmark
make reproduce
```

Across 98 synthetic scenarios and 588 single-module ablations:

```text
Unsafe reducer: 23 false SCALE decisions
                4.5% of complete non-SCALE comparisons

Fail-safe engine: 0 false SCALE decisions
                  missing required evidence -> INCOMPLETE
```

This is a controlled software stress test, not an estimate of production
prevalence. The repository ships the complete research package:

- [research question and hypotheses](research/README.md);
- [fixed benchmark protocol](research/PROTOCOL.md);
- [data card](research/DATA_CARD.md);
- [generated result rows](research/results/false_green_results.csv);
- [benchmark card](research/results/SUMMARY.md); and
- [paper-style note](research/NOTE.md).

The longer [research agenda](docs/research-agenda.md) explains how this artifact,
external evidence cases, and the proposed HandoffLab extension remain one coherent
program rather than five disconnected demos.

## Build it from first principles

The five lessons expose the complete calculation in a sequence small enough to
audit in one sitting:

```bash
make lessons
```

| Lesson | Question answered |
|---|---|
| [`00_reconstruct_task_cost.py`](lessons/00_reconstruct_task_cost.py) | What did the whole multi-call task cost? |
| [`01_gate_on_outcomes.py`](lessons/01_gate_on_outcomes.py) | What did one acceptable outcome cost? |
| [`02_compare_counterfactual.py`](lessons/02_compare_counterfactual.py) | Did the agent beat the real alternative? |
| [`03_bound_runaway_tasks.py`](lessons/03_bound_runaway_tasks.py) | Which warnings and hard caps should fire? |
| [`04_issue_assurance_case.py`](lessons/04_issue_assurance_case.py) | Should this workload scale, assist, or stop? |

Read [`docs/methodology.md`](docs/methodology.md) for the formulas and data contract.

## Modular where it should be

Agent Economics Lab does not replace an observability, eval, or runtime-control
platform. Those systems supply evidence or enforce the resulting decision.

```text
observability/eval exports · CSV · normalized JSON · internal ledger
                            |
                    plain source adapter
                            |
              canonical evidence bundle + digest
                            |
               explicit ordered assurance checks
                            |
       Markdown / JSON + INCOMPLETE / SCALE / ASSIST / STOP
```

See exactly what is installed:

```bash
python3 -m agent_economics capabilities
```

Checks are frozen, typed specifications around ordinary Python functions. There is
no plugin manager, package discovery, or arbitrary code loading. Add or remove a
check by changing one tuple:

```python
checks = tuple(
    check
    for check in default_checks()
    if check.id != "diagnostic.repeated-tool-shape"
) + (my_domain_gate,)
```

The distinction is fail-safe:

- Delete an optional diagnostic: its finding disappears; the decision is unchanged.
- Delete required coverage: the result becomes `INCOMPLETE`, never a false `SCALE`.
- Add a domain gate: it can preserve or restrict the decision without editing core code.
- Replace CSV with normalized JSON: the same canonical evidence produces the same digest.

Run all four operations in the two-minute proof:

```bash
make modularity
```

Read [`docs/modularity.md`](docs/modularity.md) for the contracts and adapter rules.

## What is deliberately different

Agent traces and model cost fields already belong in observability products. Cost
caps and cycle detectors already belong in runtime guardrails. This project gives
their exported evidence an independent, inspectable decision artifact:

```text
source adapter + traces + outcomes + risk/labor cost + counterfactual + policy
                                  |
                                  v
             versioned checks + assurance manifest
                                  |
                INCOMPLETE / SCALE / ASSIST / STOP
```

The included repetition detector is intentionally called a warning. Three tool
calls with the same name and argument *shape* can be suspicious, but that does not
prove equal intent. A directed dependency cycle can be healthy coordination; it
does not prove deadlock. Definitive enforcement comes from explicit budgets,
timeouts, call caps, authorization, and human escalation.

## Who this is for

| Audience | What they can take from the repo |
|---|---|
| Agent engineers | A vendor-neutral trace/outcome schema, deterministic caps, and tests |
| Enterprise architects | A reviewable incomplete/scale/assist/stop gate for production readiness |
| FinOps and finance | Cost per acceptable outcome and a named counterfactual |
| Product and risk leaders | Visible labor, remediation, incident, and tail-risk assumptions |
| Educators | A runnable case that can be changed live without cloud credentials |

## Repository map

```text
agent_economics/   evidence adapters, typed checks, engine, controls, and renderers
examples/          synthetic evidence plus the add/delete modularity demo
lessons/           five executable steps
research/          hypothesis, protocol, generator, data card, results, and note
templates/         assurance-case worksheet for an enterprise review
docs/              method, limitations, landscape, and launch copy
tests/             unit tests for the math, controls, and claim boundaries
```

## Three contribution lanes

1. **Source adapters:** map a pinned offline vendor or internal export fixture into
   the canonical bundle without adding a live vendor dependency.
2. **Assurance checks:** add domain policy while declaring its mode, version, and
   coverage. Diagnostics cannot change routing; gates can only preserve or restrict it.
3. **Evidence cases:** contribute a redacted scenario with:

   - a stable task ID across trace and outcome data;
   - an explicit definition of “acceptable” agreed before analysis;
   - all downstream human, remediation, and incident costs;
   - the named process the agent is being compared against; and
   - the policy that would have existed before seeing the result.

Use [`templates/agent-economic-assurance-case.md`](templates/agent-economic-assurance-case.md)
or open a case-study issue. Synthetic and fully anonymized cases are welcome.

## Scope and claim boundary

This is a teaching, conformance, and controlled-research lab—not a production
authorization layer, accounting system, or prevalence study. The demo has eight
synthetic tasks and the benchmark has 98 generated scenarios. Before a production
decision, test representativeness, label agreement, attribution, confidence
intervals, policy ownership, and observation-window effects. See
[`docs/limitations.md`](docs/limitations.md).

Apache-2.0 licensed. Contributions that make the assurance claim more falsifiable
are especially welcome.
