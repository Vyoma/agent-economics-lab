# Vyoma Gajjar

Applied AI research engineer building **economic assurance for AI agents**.

## Your agent passed its evals. Can you prove it should scale?

I built Agent Economics Lab to connect normalized agent traces with outcome
quality, human work, remediation and incident cost, a named counterfactual, and
versioned policy, then issue an auditable `INCOMPLETE`, `SCALE`, `ASSIST`, or `STOP`
decision.

## Current open-source work

### [Agent Economics Lab](https://github.com/Vyoma/agent-economics-lab)

Python 3.10+. No cloud account. No third-party runtime packages.

**Question:** Can deleting a required check silently manufacture `SCALE`?

**Test:** 98 deterministic synthetic scenarios × 6 single-module evidence
ablations.

| Deterministic synthetic stress test | Result |
|---|---:|
| Scenarios | 98 |
| Single-module ablations | 588 |
| Complete non-`SCALE` comparisons | 510 |
| Unsafe comparator: false `SCALE` | 23 / 510 (4.5%) |
| Fail-safe engine: false `SCALE` | 0 |

**Result:** the fail-safe engine returned `INCOMPLETE` whenever required coverage
was missing. This validates a routing invariant under controlled perturbations. It
does not estimate production prevalence or validate enterprise policy thresholds.

```bash
make demo
make modularity
make reproduce
```

[Run the lab](https://github.com/Vyoma/agent-economics-lab)
· [Read the research note](https://github.com/Vyoma/agent-economics-lab/blob/main/research/NOTE.md)
· [Inspect the protocol](https://github.com/Vyoma/agent-economics-lab/blob/main/research/PROTOCOL.md)
· [Review the limitations](https://github.com/Vyoma/agent-economics-lab/blob/main/docs/limitations.md)

## What I am investigating

- agent evaluation tied to observable task outcomes;
- cost per acceptable outcome and named counterfactuals;
- assurance systems that make missing evidence visibly incomplete;
- the boundary between diagnostic signals and enforceable controls; and
- next: authority, provenance, and handoff failures in multi-agent systems.

## Learn it from first principles

The repository includes five executable lessons that reconstruct full task cost,
gate on outcomes, compare a counterfactual, bound runaway tasks, and issue an
assurance decision.

[Start with the lessons](https://github.com/Vyoma/agent-economics-lab/tree/main/lessons)

## Make the claim harder to fake

The most useful contributions to Agent Economics Lab are:

1. fixture-backed offline adapters for real observability and evaluation exports;
2. versioned domain assurance checks with declared coverage; and
3. redacted real-world cases that define the task, acceptable outcome, full cost,
   counterfactual, and pre-committed policy.

[Open a case-study issue](https://github.com/Vyoma/agent-economics-lab/issues)

I welcome agent-evaluation research, architecture collaborations, and technically
serious advisory conversations. I am also interested in counterexamples that
narrow or falsify the method.
