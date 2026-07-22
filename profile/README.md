# Vyoma Gajjar

Applied AI research engineer building **economic assurance for AI agents**.

## Where does saving money start breaking the agent?

I built Agent Economics Lab to compare tested agent configurations on identical
task input fingerprints and rubric versions, join outcomes to model, tool, labor,
remediation, and incident cost, and
refuse to select a cheaper route when its uncertainty-bounded breakage risk is too
high.

## Current open-source work

### [Agent Economics Lab](https://github.com/Vyoma/agent-economics-lab)

Python 3.10+. No cloud account. No third-party runtime packages.

**Question:** Which tested agent configuration is the lowest-cost one whose upper
confidence bound on harmful paired transitions stays within policy?

**Test:** a frozen four-arm, 180-task paired experiment with exact harmful-regression
bounds, deterministic paired cost intervals, and a multiplicity-adjusted nominal
confidence target.

| Candidate | Breakage UCB | Cost reduction LCB | Result |
|---|---:|---:|---|
| `balanced-4-step` | 3.7% | 32.0% | eligible |
| `cheap-2-step` | 12.5% | 29.9% | quality fails |
| `premium-12-step` | 2.6% | -38.9% | cost fails |

**Result:** `ADOPT balanced-4-step`. It was the lowest-cost tested arm that cleared
the frozen 5% breakage-risk and 25% full-cost-reduction rules. The study is synthetic
and validates the method, not production impact.

```bash
make frontier
make reproduce
```

[Run the lab](https://github.com/Vyoma/agent-economics-lab)
· [Inspect the result](https://github.com/Vyoma/agent-economics-lab/blob/main/research/results/frontier/frontier.md)
· [Inspect the protocol](https://github.com/Vyoma/agent-economics-lab/blob/main/research/FRONTIER_PROTOCOL.md)
· [Review the limitations](https://github.com/Vyoma/agent-economics-lab/blob/main/docs/limitations.md)

## What I am investigating

- paired cost-quality experiments for agent configurations;
- exact breakage-risk bounds and simultaneous decision rules;
- full downstream cost per acceptable outcome;
- assurance systems that make missing tasks and cost evidence visibly incomplete;
- next: one pinned OpenTelemetry GenAI adapter and a permissioned real frontier case.

## Learn it from first principles

The repository includes five executable lessons that reconstruct full task cost,
gate on outcomes, compare a counterfactual, bound runaway tasks, and issue an
assurance decision.

[Start with the lessons](https://github.com/Vyoma/agent-economics-lab/tree/main/lessons)

## Make the claim harder to fake

The most useful contributions to Agent Economics Lab are:

1. permissioned matched-task experiments with a frozen candidate family and rubric;
2. fixture-backed adapters for real observability and evaluation exports;
3. critical subgroup and label-reliability tests; and
4. counterexamples that make the selection rule narrower or falsify it.

[Open a case-study issue](https://github.com/Vyoma/agent-economics-lab/issues)

I welcome agent-evaluation research, architecture collaborations, and technically
serious advisory conversations. I am also interested in counterexamples that
narrow or falsify the method.
