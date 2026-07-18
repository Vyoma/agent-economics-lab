# Fail-Safe Modularity for Agent Economic Assurance

## Abstract

Modular assurance systems create a specific failure mode: removing an inconvenient
check can make a deployment decision look safer without improving the underlying
agent. We test whether explicit required-coverage semantics prevent this
“false-green” behavior in Agent Economics Lab.

Across 98 deterministic synthetic scenarios and 588 single-module ablations, an
unsafe reducer that silently treated the remaining checks as complete produced 23
`SCALE` decisions where the complete case was `ASSIST` or `STOP`. This was 4.5% of
the 510 ablation comparisons whose complete result was not `SCALE`. The fail-safe
engine returned `INCOMPLETE` for every required-coverage ablation and produced zero
false-green `SCALE` decisions.

The experiment validates a software invariant under controlled perturbations. It
does not estimate the prevalence of incomplete evidence or false-green decisions in
production organizations.

## 1. Research question

Can a modular agent-assurance system allow required evidence to be deleted without
making the resulting decision visibly incomplete?

This matters because “add or remove any module” sounds flexible but is unsafe when
module removal changes the meaning of a green decision. A missing quality gate is
not equivalent to passing a quality gate.

## 2. System under test

The assurance engine normalizes traces, outcomes, costs, a named counterfactual,
and policy into one evidence bundle. Six coverage dimensions are required:

1. outcome quality;
2. unit economics;
3. tail risk;
4. absolute business value;
5. value versus the counterfactual; and
6. runtime call/spend caps.

Optional diagnostics can add findings but have no routing authority. Removing a
required check should return `INCOMPLETE`; removing an optional diagnostic should
leave the routing decision unchanged.

## 3. Method

The benchmark generates a 96-scenario factorial matrix over acceptance rate, trace
cost, failure-related human effort, tail loss, and baseline strength. Two additional
boundary cases isolate unit economics and absolute business value. Every scenario
contains ten tasks.

For each scenario, we compute:

- the complete assurance decision;
- the decision after removing one required gate while preserving fail-safe coverage;
  and
- an unsafe comparator that silently redefines required coverage to match whichever
  checks remain.

The primary outcome is a false green:

```text
complete decision != SCALE
and
unsafe available-only decision == SCALE
```

The release-blocking invariant is:

```text
count(complete != SCALE and fail_safe == SCALE) == 0
```

The full protocol is in [`PROTOCOL.md`](PROTOCOL.md), and the generated data is
described in [`DATA_CARD.md`](DATA_CARD.md).

## 4. Results

| Measure | Result |
|---|---:|
| Synthetic scenarios | 98 |
| Single-module ablations | 588 |
| Complete non-SCALE comparisons | 510 |
| Unsafe false-green SCALE decisions | 23 |
| Unsafe false-green rate | 4.5% |
| Fail-safe false-green SCALE decisions | 0 |

False-green counts by removed dimension:

| Removed dimension | Count |
|---|---:|
| Outcome quality | 2 |
| Unit economics | 1 |
| Tail risk | 8 |
| Business value | 1 |
| Counterfactual | 3 |
| Runtime caps | 8 |

Tail-risk and runtime-cap removals have more reversals in this matrix because the
factorial design includes repeated boundary conditions for large single-task loss
and trace cost. The counts do not imply that those omissions are more common in
production.

## 5. Interpretation

The result supports two narrow claims:

1. In this controlled matrix, every required dimension has at least one scenario
   where silently removing it creates a false-green decision.
2. Explicit coverage accounting prevents those omissions from being represented as
   `SCALE`.

This is a useful design property for modular systems. It does not validate the
chosen economic thresholds, outcome labels, cost allocations, or six-dimension
coverage model for a particular enterprise.

## 6. Threats to validity

- The scenario distribution is hand-constructed rather than empirically sampled.
- Tasks have one trace event, so multi-call topology and partial traces are absent.
- Costs and outcomes are exact; billing gaps and label disagreement are not modeled.
- Only single-dimension ablations are tested.
- The unsafe comparator is a deliberately weak design, not a named commercial tool.
- No claim is made about Galileo, LangSmith, OpenTelemetry, or another vendor’s
  decision semantics.

## 7. Next empirical step

Run the same ablation protocol on permissioned, redacted workload cases supplied by
independent users. Pre-register the assurance dimensions and thresholds for each
case before calculating reversals. Report cases where missing data changes a
decision as well as cases where it does not.

Until that evidence exists, the project should describe the result as a synthetic
software stress test—not proof of enterprise impact.
