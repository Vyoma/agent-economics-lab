# Decision-Coverage Drift in Agent Economic Assurance

## Abstract

Modular assurance systems create a specific failure mode: disabling an inconvenient
gate can make a decision look safer without improving the underlying agent. I use
**decision-coverage drift** for the case where a system silently redefines sufficient
coverage to match whichever gates remain enabled.

Across 98 deterministic synthetic scenarios and 588 single-gate disablements, a
dynamic-coverage engine produced 23 `SCALE` decisions where the complete case was
`ASSIST` or `STOP`. This was 4.5% of the 510 intervention comparisons whose complete
result was not `SCALE`, and 3.9% of all 588 comparisons. The fixed-contract engine
returned `INCOMPLETE` for all 588 disablements and produced zero false `SCALE`
transitions.

The evidence bundle was unchanged in every comparison. The experiment validates an
engine invariant under controlled configuration changes. It does not test ordinary
missing data or estimate production prevalence.

## 1. Research question

Can a modular decision engine produce `SCALE` after a required gate is disabled if
the engine silently shrinks its definition of complete coverage?

This matters because “add or remove any module” is unsafe when module removal changes
the meaning of approval. All enabled checks passing is not equivalent to all
required checks passing.

## 2. System under test

The assurance engine normalizes traces, outcomes, costs, a named counterfactual, and
policy into one evidence bundle. Six coverage dimensions are required:

1. outcome quality;
2. unit economics;
3. tail risk;
4. absolute business value;
5. value versus the counterfactual; and
6. runtime call and spend caps.

Optional diagnostics can add findings but have no routing authority. If an enabled
gate set does not supply the fixed required coverage, a successful evaluation should
return `INCOMPLETE`.

## 3. Method

The benchmark generates a 96-scenario factorial matrix over acceptance rate, trace
cost, failure-related human effort, tail loss, and baseline strength. Two additional
boundary cases isolate unit economics and absolute business value. Every scenario
contains ten tasks.

For each scenario, the benchmark computes:

- the complete decision under all default gates and the fixed six-dimension contract;
- the decision after disabling one required gate while preserving that contract; and
- the decision after disabling the same gate and redefining required coverage to
  match whichever gates remain.

The primary outcome is a false `SCALE` transition:

```text
complete decision != SCALE
and
dynamic-coverage decision == SCALE
```

The conformance invariant is stronger:

```text
missing fixed required coverage
implies
fixed-contract decision == INCOMPLETE
```

The full protocol is in
[`FALSE_GREEN_PROTOCOL.md`](FALSE_GREEN_PROTOCOL.md), and the generated data is
described in [`FALSE_GREEN_DATA_CARD.md`](FALSE_GREEN_DATA_CARD.md).

## 4. Results

| Measure | Result |
|---|---:|
| Synthetic scenarios | 98 |
| Single required-gate disablements | 588 |
| Complete-case non-`SCALE` comparisons | 510 |
| Dynamic-coverage false `SCALE` transitions | 23 |
| Rate among complete-case non-`SCALE` comparisons | 4.5% |
| Rate among all disablements | 3.9% |
| Fixed-contract `INCOMPLETE` decisions | 588 |
| Fixed-contract false `SCALE` transitions | 0 |

Transitions by disabled gate coverage:

| Disabled gate coverage | Count |
|---|---:|
| Outcome quality | 2 |
| Unit economics | 1 |
| Tail risk | 8 |
| Business value | 1 |
| Counterfactual | 3 |
| Runtime caps | 8 |

Tail-risk and runtime-cap disablements produce more transitions in this matrix
because its constructed factor levels repeat large single-task loss and trace-cost
conditions. The counts do not imply that these gates are disabled more often in
production.

## 5. Interpretation

The result supports two narrow claims:

1. In this frozen matrix, dynamically shrinking required coverage creates at least
   one false `SCALE` transition for each default required gate.
2. The implementation enforces a fixed-contract invariant: when enabled gates do not
   supply the fixed required coverage, successful evaluation returns `INCOMPLETE`.

The second result is a designed software property, not a discovered method for
eliminating false approvals. The experiment does not validate the chosen thresholds,
labels, cost allocations, or six-dimension model for a particular enterprise.

## 6. Threats to validity

- The scenario distribution is hand-constructed rather than empirically sampled.
- Tasks have one trace event, so multi-call topology and partial traces are absent.
- Costs and outcomes are exact; billing gaps and label disagreement are not modeled.
- Only single-gate disablements are tested.
- The dynamic-coverage comparator is a deliberately weak design, not a named
  commercial tool.
- No claim is made about Galileo, LangSmith, OpenTelemetry, or another vendor’s
  decision semantics.

## 7. Next empirical steps

An actual evidence-ablation study must separately remove outcome records, baseline
data, labor and incident costs, trace costs, failed runs, task-manifest entries, and
policy fields, then record whether each mutation fails validation, produces a
structured `INCOMPLETE` artifact, or incorrectly yields a substantive decision.

After that conformance work, run a preregistered protocol on permissioned, redacted
workloads supplied by independent users. Until such evidence exists, describe this
result as a synthetic software conformance test, not proof of enterprise impact.
