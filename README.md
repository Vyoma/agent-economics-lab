# Agent Economics Lab

**Your agent passed its evals. Can you prove it should scale?**

[![Tests](https://github.com/Vyoma/agent-economics-lab/actions/workflows/test.yml/badge.svg)](https://github.com/Vyoma/agent-economics-lab/actions/workflows/test.yml)

Most teams cannot answer the question finance, product, engineering, and risk all
share: *what did one acceptable outcome actually cost, and what should we do next?*

This repository turns traces, outcomes, downstream cost, and a named alternative
into one bounded decision:

`INCOMPLETE` / `SCALE` / `ASSIST` / `STOP`

The dangerous failure is not difficult math. It is averaging whatever evidence
happens to be present and blessing what the system cannot see. One file reproduces
the controlled failure mode:

```bash
python3 false_green.py
```

```text
98 scenarios x 6 evidence deletions       588 comparisons
unsafe available-evidence reducer          23 false SCALE decisions
fail-safe engine                            0 false SCALE decisions

removed evidence       false SCALE
outcome_quality      #####                2
unit_economics       ##                   1
tail_risk            #################### 8
business_value       ##                   1
counterfactual       ########             3
runtime_caps         #################### 8
```

> A dashboard that averages only what it has can bless what it cannot see.

![`make demo` returns ASSIST](assets/demo.gif)

The matrix is synthetic. It tests software semantics, not how often production
systems fail. The complete rows, denominator, protocol, and limitations are checked
in under [`research/`](research/).

## Run the full decision

Python 3.10+. No cloud account. No third-party runtime packages.

```bash
make demo
```

The included support workload creates positive value versus its human-only
alternative, but the result is still `ASSIST`: outcome quality, unit cost, tail cost,
and runtime caps fail policy. A profitable agent is not automatically a scalable
agent.

```text
Decision                         ASSIST
Acceptable outcomes              6 / 8
Cost / acceptable outcome        $3.50
Incremental value / attempt      $2.77
Why not SCALE                    quality, unit cost, tail cost, runtime caps
```

That is the assurance case: all required evidence stays visible, warnings explain,
and typed gates route.

## Find the cheapest tested configuration that still clears policy

```bash
make frontier
```

The paired frontier runs four configurations on the same 180 synthetic task input
digests and frozen rubric:

```text
Decision                         ADOPT balanced-4-step

Candidate            Breakage UCB   Cost reduction LCB   Result
balanced-4-step             3.7%                32.0%   eligible
cheap-2-step               12.5%                29.9%   quality fails
premium-12-step             2.6%               -38.9%   cost fails
```

The cheapest point estimate does not win. The selected arm must clear the frozen
quality bound, full-cost bound, evidence checks, and normal deployment policy.

[Read the method](docs/frontier.md) ·
[Inspect the decision](research/results/frontier/frontier.md) ·
[See the protocol](research/FRONTIER_PROTOCOL.md) ·
[Review the data card](research/FRONTIER_DATA_CARD.md)

## The kernel

Keep the observability, evaluation, and runtime-control tools you already use.
Normalize their offline exports, then issue an inspectable decision artifact.

```text
traces + outcomes + labor/risk cost + baseline + policy
                            |
                canonical evidence + digest
                            |
          typed checks with required coverage
                            |
       Markdown / JSON + a bounded decision
```

Delete an optional diagnostic and only its warning disappears. Delete required
coverage and the decision becomes `INCOMPLETE`, never a false `SCALE`. Add a local
gate and it can restrict the result without editing the core.

```bash
make modularity
```

[Methodology](docs/methodology.md) ·
[Modularity contract](docs/modularity.md) ·
[Architecture](ARCHITECTURE.md) ·
[Limitations](docs/limitations.md)

## Reproduce everything

```bash
make falsegreen
make demo
make frontier
make reproduce
```

`make reproduce` runs 49 tests, the module-deletion proof, five executable lessons,
the 588-comparison false-green benchmark, and byte-for-byte frontier artifact
verification.

## Contribute evidence, not integrations on a slide

- Map one pinned offline export into the canonical evidence bundle with a fixture.
- Add one typed gate or diagnostic with explicit failure semantics.
- Contribute one permissioned paired experiment with a frozen task manifest,
  candidate family, rubric, and full-cost boundary.
- Submit one counterexample that narrows or falsifies a claim.

Start with [CONTRIBUTING.md](CONTRIBUTING.md) or the issue templates. Do not submit
customer data, secrets, proprietary prompts, or contract pricing.

## Claim boundary

This is a teaching, conformance, and controlled-research lab. It is not a production
authorization layer, accounting system, or prevalence study. The checked-in cases
are synthetic. Production use requires representative tasks, label validation,
assignment controls, subgroup analysis, complete cost attribution, policy ownership,
and ongoing monitoring.

Apache-2.0 licensed.
