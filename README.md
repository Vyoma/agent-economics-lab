# Agent Economics Lab

**Your agent passed every enabled check. Did every required check run?**

[![Tests](https://github.com/Vyoma/agent-economics-lab/actions/workflows/test.yml/badge.svg)](https://github.com/Vyoma/agent-economics-lab/actions/workflows/test.yml)

Most teams cannot answer the question finance, product, engineering, and risk all
share: *what did one acceptable outcome actually cost, and what should we do next?*

This repository turns traces, outcomes, downstream cost, and a named alternative
into one bounded decision:

`INCOMPLETE` / `SCALE` / `ASSIST` / `STOP`

The dangerous failure is a contract that changes with the checks that happen to be
enabled. One file reproduces the controlled failure mode:

```bash
python3 false_green.py
```

```text
98 scenarios x 6 required-gate disablements 588 comparisons
dynamic-coverage engine                       23 false SCALE transitions
fixed-contract engine                          0 false SCALE transitions
fixed-contract refusals                  588/588 INCOMPLETE

disabled requirement  false SCALE
outcome_quality      #####                2
unit_economics       ##                   1
tail_risk            #################### 8
business_value       ##                   1
counterfactual       ########             3
runtime_caps         #################### 8
```

> All enabled checks passed is not the same claim as all required checks passed.

![`make demo` returns ASSIST](assets/demo.gif)

The evidence does not change in this experiment. Each intervention disables one
sole-provider gate. A dynamic contract silently shrinks with that gate; the fixed
contract keeps all six requirements and refuses every reduced composition.

The 23 is a property of a synthetic fixture. The zero is an enforced invariant.
Neither is a production prevalence estimate. Read the
[protocol](research/FALSE_GREEN_PROTOCOL.md), inspect all
[588 rows](research/results/decision-coverage-drift/results.csv), or read the
[technical article](docs/article.md).

For a product-team version with a 30-minute operating exercise, read
[one-page decision contract](templates/agent-scale-decision-contract.md).

## Delete actual evidence

Gate disablement and evidence deletion are different experiments. The second
executable deletes real raw records and fields while keeping checks, coverage, and
the decision-contract digest fixed:

```bash
python3 evidence_ablation.py
```

```text
ablations                  9
operational refusals       4
ASSIST -> SCALE             5
INCOMPLETE case artifacts  0
```

The five transitions expose two concrete source-contract gaps: omitted cost fields
can become zero, and a deleted timed-out event is invisible without an independent
attempt manifest. They are boundary cases, not a failure rate.

[Read the evidence-ablation protocol](research/EVIDENCE_ABLATION_PROTOCOL.md) ·
[Inspect the generated rows](research/results/evidence-ablation/results.csv)

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

That is the assurance case: evidence, the fixed decision contract, and routing
semantics remain inspectable.

## Find the cheapest tested configuration that still clears policy

```bash
make frontier
```

The paired frontier runs four configurations on the same 180 synthetic task input
digests and frozen rubric:

```text
Decision                         ADOPT balanced-4-step

Candidate            Absolute UCB   Conditional H/R+   Cost LCB   Result
balanced-4-step             3.7%             1/171       32.0%   eligible
cheap-2-step               12.5%            12/171       29.9%   quality fails
premium-12-step             2.6%             0/171      -38.9%   cost fails
```

The absolute H/N upper bound governs v1 eligibility. The conditional H/R+ rate is
reported because a weak reference can hide breakage in the absolute denominator.
The selected arm's observed cost rank is post-selection exploratory and needs a
held-out or independently replicated confirmation before generalization.

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
     typed checks + fixed required coverage
                            |
       decision-contract digest + bounded decision
```

Delete an optional diagnostic and only its warning disappears. Disable a
sole-provider gate while the contract stays fixed and the decision becomes
`INCOMPLETE`. Add a local gate and it can restrict the result without editing the
core.

```bash
make modularity
```

[Methodology](docs/methodology.md) ·
[Modularity contract](docs/modularity.md) ·
[Architecture](ARCHITECTURE.md) ·
[Limitations](docs/limitations.md)

## Convert a Claude Code session without inventing its economics

Claude Code JSONL contains execution facts, not acceptable-outcome labels, a
counterfactual baseline, or a complete price contract. The converter therefore has
two explicit phases:

```bash
agent-economics convert \
  --from claude-code \
  --in session.jsonl \
  --template conversion-contract.json

# Complete the labels, rate tiers, tool costs, baseline, and policy.

agent-economics convert \
  --from claude-code \
  --in session.jsonl \
  --contract conversion-contract.json \
  --out bundle.json

agent-economics evaluate --bundle bundle.json
```

The adapter deduplicates streamed assistant fragments into model calls, prices
base/cache/server-tool usage from the supplied contract, discards prompt and
response content, preserves only content-free tool-argument type shape, and refuses unresolved
delegation or incomplete tool-call inventories.

[Read the adapter contract](docs/claude-code-adapter.md) ·
[Review the implemented PRD](docs/adapter-extension-prd.md) ·
[Inspect the complete fixture](examples/claude-code/)

## Reproduce everything

```bash
make coverage-drift
make evidence-ablation
make demo
make frontier
make reproduce
```

`make reproduce` runs the full test suite, the module-deletion proof, five
executable lessons, both ablation benchmarks, the Claude Code conversion, and
byte-for-byte frontier and adapter artifact verification.

## Contribute evidence, not integrations on a slide

- Map one pinned offline export into the canonical evidence bundle with a fixture.
- Add one typed gate or diagnostic with explicit failure semantics.
- Contribute one permissioned paired experiment with a frozen task manifest,
  candidate family, rubric, and full-cost boundary.
- Test one real workflow with the
  [blank decision contract](templates/agent-scale-decision-contract.md).
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
