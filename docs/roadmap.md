# Scope and priority

This document separates shipped evidence from planned work. It is a delivery
sequence, not a claim that every item is required by the one before it.

## Grounding

P0 shipped at commit `f0e003a` with:

- a contract-first Claude Code adapter;
- a non-synthetic public SWE-bench case;
- 97 passing tests at the P0 boundary;
- byte-reproducible Claude Code and public-case artifacts; and
- an honest `STOP` assurance result and `HOLD` frontier result for the public
  comparison.

The CLI surface at that boundary was:

```text
agent-economics evaluate  --bundle | (--traces --outcomes --rates --baseline --policy)
                          [--format markdown|json] [--ci] [--output PATH]
agent-economics frontier  PLAN --output-dir DIR [--verify-dir DIR]
agent-economics convert   --from claude-code --in PATH
                          (--template PATH | --contract PATH --out PATH)
agent-economics capabilities
```

The CI exit contract is fixed:

| Decision | Exit code | GitHub check |
|---|---:|---|
| `SCALE` | 0 | pass |
| `INCOMPLETE` | 2 | fail |
| `ASSIST` | 3 | fail |
| `STOP` | 4 | fail |

## P1: GitHub Action

Status: implemented and entering repository dogfood.

### Goal

Let a team add the existing economic decision contract to a pull request without
manually installing the package. This is a distribution layer over the existing
CLI, not a second decision engine.

### Design

- Use a composite action. The project is Python 3.10+ with no third-party runtime
  dependencies, so a container would add distribution latency without adding an
  isolation requirement.
- Mirror the three CLI-relevant input modes:
  - one normalized JSON bundle;
  - all five CSV/JSON evidence inputs; or
  - adapter + session + completed conversion contract.
- Reject partial or conflicting modes as `INCOMPLETE`.
- Run the exact `evaluate --ci` path and preserve its exit code.
- Upsert one Markdown assurance report on a pull request when the caller provides
  a token with comment permission.
- Fail the action for `INCOMPLETE`, `ASSIST`, and `STOP`. Only `SCALE` is green.
- Expose `decision`, `exit-code`, and `report` outputs for downstream workflow
  policy.

### Acceptance

- The repository workflow exercises CSV, normalized-bundle, and Claude Code
  conversion modes.
- The Claude Code fixture produces the same byte-for-byte report as the direct
  CLI.
- The public SWE-bench bundle remains `STOP`.
- Tests prove that only `SCALE` returns zero and malformed action configuration
  fails closed.

### Release boundary

Dogfood the action from this repository before creating stable `v1` and `v1.0.0`
tags or listing it in the GitHub Marketplace. During dogfood, consumers should pin
an exact commit SHA. A mutable branch reference is for evaluation only.

## P2: generic OpenTelemetry GenAI adapter

Status: scoped, not started.

### Goal

Map a pinned OpenTelemetry GenAI semantic-convention export into the canonical
evidence bundle so multiple platforms can share one adapter instead of receiving
vendor-specific economics engines.

### Design constraints

- Add `agent_economics/otel_genai.py` with a pure
  `otel_genai_bundle_from_spans(spans, contract)` boundary.
- Pin the exact semantic-convention version used by the mapper. The specification
  is evolving, so attribute names must be verified against that version during
  implementation.
- Reuse the contract-first pattern for outcomes, rates, baseline, and policy. Do
  not infer acceptable outcomes or prices from span presence.
- Fail closed on unresolved models, usage buckets, tool charges, parentage, task
  identity, or outcome identity.
- Add `otel-genai` as the second explicit `convert --from` value.
- Factor a shared conversion-contract loader only where the second implementation
  demonstrates identical behavior.

### Proof of genericity

Use pinned, content-safe fixtures from at least two independent platforms that
export OpenTelemetry GenAI spans. One vendor fixture does not support a generic
adapter claim.

### Registry trigger

Two adapters do not automatically require plugin discovery. Reconsider a registry
only after Claude Code and OpenTelemetry expose a concrete incompatibility that an
explicit mapping cannot handle cleanly.

## P3a: directed-cycle diagnostic

Status: scoped, not started.

`find_directed_cycles` exists, but the canonical evidence bundle does not yet
contain typed dependency edges. Reading a reserved key from an untyped arguments
dictionary would create an implicit schema.

The recommended design is an optional typed
`dependency_edges: tuple[tuple[str, str], ...]` field on `EvidenceBundle`.
Adapters with real parentage may populate it. A diagnostic can run cycle detection
when edges are present and do nothing when they are absent. Missing structural
evidence must not be fabricated.

The Claude Code parent-UUID graph is the first real source. A later OpenTelemetry
adapter can provide a second source through span parent IDs.

## P3b: documentation consolidation

Status: scoped, not started.

Move writing and launch material under `docs/writing/`:

- `article.md`
- `substack-article.md`
- `substack-publishing-kit.md`
- `launch.md`
- `public-profile.md`
- `research-agenda.md`

Keep load-bearing technical references at their stable locations:

- `ARCHITECTURE.md`
- `docs/methodology.md`
- `docs/modularity.md`
- `docs/limitations.md`
- `docs/frontier.md`
- `docs/adapter-extension-prd.md`
- `docs/claude-code-adapter.md`

Links must move atomically with files so cleanup cannot create stale navigation.

## Priority

| Rank | Item | Status | Effort | Dependency | Why now |
|---:|---|---|---|---|---|
| 0 | P0: Claude Code + public case | shipped | complete | none | Proven foundation |
| 1 | P1: GitHub Action | dogfood | S-M | none | Smallest distribution step using existing semantics |
| 2 | P2: OpenTelemetry GenAI adapter | scoped | M-L | benefits from P1 | First genuinely cross-platform source adapter |
| 3 | P3a: cycle diagnostic | scoped | S | none | Small typed improvement with existing algorithm |
| 3 | P3b: documentation consolidation | scoped | S | none | Low-risk cleanup with no runtime impact |

The sequence is P1, then P2, with P3a and P3b placed between them when convenient.
P3 work is independent and must not delay validation of P1 or source research for
P2.
