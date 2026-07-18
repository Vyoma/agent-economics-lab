# Explicit composition and source adapters

The modularity claim is intentionally narrower than a plugin ecosystem:

> Normalize exported evidence into one stable bundle. Compose typed checks as an
> explicit ordered tuple. Record the source, digest, enabled checks, and missing
> coverage in every result.

There is no automatic discovery, entry-point execution, dependency-injection
container, live vendor authentication, or policy DSL.

## Architecture

```text
vendor or internal export
        |
        v
source adapter function ------ source ID + version
        |
        v
EvidenceBundle --------------- canonical SHA-256 digest
        |
        v
AssuranceEngine(checks) ------ ordered check IDs + versions
        |
        +---- gate results ---- PASS / FAIL + typed consequence
        |
        +---- diagnostics ----- warning evidence; never routing authority
        |
        v
AssuranceCase ---------------- INCOMPLETE / SCALE / ASSIST / STOP
        |
        +---- renderer.markdown@1
        +---- renderer.json@1
```

The approach complements existing platforms. Galileo already supports
[custom code-based metrics](https://docs.galileo.ai/concepts/metrics/custom-metrics/custom-metrics-ui-code),
LangSmith supports [trace export](https://docs.langchain.com/langsmith/export-traces)
and [OpenTelemetry routing](https://docs.langchain.com/langsmith/trace-with-opentelemetry),
and OpenTelemetry publishes evolving
[GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).
Those tools remain upstream evidence providers. This project owns the downstream
economic assurance manifest and decision boundary.

## Canonical evidence boundary

`EvidenceBundle` contains:

- normalized, deterministically ordered `TraceEvent` records;
- one `Outcome` per task;
- a model rate card;
- a named counterfactual baseline;
- versioned policy values;
- source adapter ID/version; and
- a content digest independent of source adapter and input row order.

The built-in adapters are:

```text
source.csv@1
source.normalized-json@1
```

The JSON adapter is the offline interchange seam for vendor mappers. It does not
claim that arbitrary Galileo, LangSmith, or OTLP files already match the canonical
schema. A vendor contribution should be a small, tested mapping into the bundle,
not a new economics engine.

Adapter equivalence is a required test:

```python
csv_case = evaluate_bundle(csv_bundle)
mapped_case = evaluate_bundle(vendor_export_bundle)

assert csv_bundle.digest == mapped_bundle.digest
assert csv_case.decision == mapped_case.decision
assert csv_case.breaches == mapped_case.breaches
```

Adapters must reject duplicate event IDs and outcome IDs. They should discard raw
prompt, response, and tool-argument values by default unless the assurance check
explicitly requires them and the data owner approves retention.

## Check contract

Each `CheckSpec` declares:

```python
CheckSpec(
    id="gate.example",
    version="1",
    mode=CheckMode.GATE,
    covers=frozenset({Coverage.OUTCOME_QUALITY}),
    run=check_function,
)
```

- `id` and `version` are recorded in the report.
- `mode=GATE` may return a typed `ASSIST` or `STOP` consequence on failure.
- `mode=DIAGNOSTIC` may add findings but is rejected if it attempts to route.
- `covers` declares which required assurance dimension the check supplies.
- `run` is an ordinary pure function over an immutable evaluation view.

Duplicate check IDs fail at engine construction. A check that emits results under
another ID fails evaluation. A diagnostic that tries to return `FAIL` or a routing
consequence also fails evaluation.

## Fail-safe deletion

The default engine requires six coverage dimensions:

```text
outcome_quality
unit_economics
tail_risk
business_value
counterfactual
runtime_caps
```

Deleting the structural repetition diagnostic is safe because it covers no required
dimension. Deleting the acceptable-rate gate removes `outcome_quality`, so the
engine returns:

```text
Decision: INCOMPLETE
Missing coverage: outcome_quality
```

This is the key enterprise guarantee: modularity cannot be used to manufacture a
green result by quietly deleting an inconvenient required check.

## Add a domain gate

A local gate needs no registry or core edit:

```python
def no_failed_events(view):
    failed = [event.event_id for event in view.events if event.status != "ok"]
    return CheckOutput(results=(CheckResult(
        check_id="gate.no-failed-events",
        status=CheckStatus.FAIL if failed else CheckStatus.PASS,
        message=f"failed events: {failed}",
        on_failure=Decision.STOP if failed else None,
    ),))

custom_gate = CheckSpec(
    id="gate.no-failed-events",
    version="1-local",
    mode=CheckMode.GATE,
    covers=frozenset(),
    run=no_failed_events,
)

case = evaluate_bundle(evidence, default_checks() + (custom_gate,))
```

Run the complete add/delete proof with `make modularity`.

For CI, request JSON and decision-specific exit codes:

```bash
python3 -m agent_economics evaluate ... --format json --ci
```

| Decision | Exit code |
|---|---:|
| `SCALE` | 0 |
| `INCOMPLETE` | 2 |
| `ASSIST` | 3 |
| `STOP` | 4 |

## What remains fixed in v0.1

The task/outcome join, complete effective-cost reconstruction, unit calculations,
decision reducer, and canonical evidence digest remain a small inspectable kernel.
They are not dynamically replaceable. Cost-source ledgers or generalized module
discovery should be added only when two independent integrations demonstrate a
real incompatibility with this boundary.
