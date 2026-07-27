# Data Card: Raw Evidence-Ablation Boundary Fixtures v1

## Purpose

Characterize how the current single-arm economic assurance path responds when
actual raw evidence is removed. The fixture is designed to distinguish schema
rejection, semantic evidence rejection, evaluation failure, and an emitted
decision.

## Composition

- 9 deterministic single-deletion cases.
- 6 fixture variants built from one two-task base fixture.
- 2 task identities per fixture.
- 2 or 3 trace events before ablation.
- 2 outcomes before ablation.
- 1 fixed baseline and 1 fixed policy.
- 1 fixed decision contract with 6 required coverage dimensions.

The data is generated. It contains no prompts, model responses, production
traces, personal data, customer identifiers, or secrets.

## Evidence represented

The cases cover:

- one outcome record;
- the complete baseline object;
- incident loss;
- remediation cost;
- human review time;
- directly allocated trace cost;
- one task-manifest row;
- one required policy threshold;
- one timed-out attempt event.

## Generation

`evidence_ablation.py` constructs raw normalized-JSON dictionaries in memory.
Every complete fixture is evaluated before a deep copy receives exactly one
deletion. Complete and ablated inputs use the same adapter, checks, required
coverage, and engine implementation.

The boundary values are deliberately selected so that a nonzero cost or extra
attempt is decision-material while unrelated gates pass.

## Labels

`library_outcome` is one of:

```text
SCHEMA_ERROR
EVIDENCE_ERROR
EVALUATION_ERROR
DECISION
```

`operational_outcome` records the public behavior:

```text
INCOMPLETE
SCALE
ASSIST
STOP
ERROR
```

`false_scale=true` means that the complete fixture did not return `SCALE`, the
ablated input emitted an assurance case, and that case returned `SCALE`.

An operational `INCOMPLETE` does not imply that an `INCOMPLETE` assurance case
was emitted. For schema and evidence errors, the CLI refuses the input with exit
code 2.

## Current v1 result

- 9 ablations.
- 2 raw schema errors.
- 2 semantic evidence errors.
- 4 operational refusals.
- 5 `ASSIST` to `SCALE` transitions.
- 0 `INCOMPLETE` assurance-case artifacts.
- 0 unexpected evaluation errors.

## Known limitations

- Values are hand-selected boundary conditions.
- The counts are not prevalence estimates.
- Ablations are one at a time and do not measure interacting omissions.
- The fixture assumes the complete member of each pair is authoritative.
- The benchmark does not establish how an adapter should prove source
  completeness.
- A missing timed-out event is undetectable without an external attempt ledger or
  completeness manifest.
- Outcome labels are deterministic and have no annotator disagreement.
- Cost values are exact and have no allocation uncertainty.

## Intended uses

- Regression testing current raw-evidence semantics.
- Teaching the difference between absence and explicit zero.
- Identifying where rejection occurs in the public evaluation path.
- Providing a concrete contract for future adapter hardening.

## Out-of-scope uses

- Estimating enterprise dashboard error rates.
- Certifying that the six coverage dimensions are sufficient.
- Ranking agent platforms, models, or observability vendors.
- Treating five transitions as an empirical failure probability.
- Claiming that operational refusal always produces an assurance artifact.
