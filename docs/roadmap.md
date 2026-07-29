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

Status: shipped on `main`.

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

Status: shipped on `main`.

### Goal

Map a pinned OpenTelemetry GenAI semantic-convention export into the canonical
evidence bundle so multiple platforms can share one adapter instead of receiving
vendor-specific economics engines.

### Implemented contract

- `agent_economics/otel_genai.py` maps pinned offline OTLP JSON.
- The mapper freezes Semantic Conventions `1.43.0` and GenAI commit
  `799e014b68f0e786dc44d9117c30758c5f864510`.
- A shared conversion-contract module owns strict JSON loading, outcome identity,
  baseline, and policy parsing for both adapters.
- Outcomes, task mapping, prices, baseline, and policy remain explicit contract
  claims. They are not inferred from span presence.
- Unresolved models, operations, usage, tool prices, parentage, task identity, and
  outcome identity fail closed.
- `otel-genai` is the second explicit `convert --from` value and is supported by
  the composite GitHub Action.

### Proof of genericity

Pinned, content-safe fixtures derived from Langfuse and Arize OpenInference run
through the same mapper. Each fixture records upstream repository, commit, path,
digest, and transformation. This proves two-platform conformance, not universal
export compatibility.

### Registry trigger

Two adapters do not automatically require plugin discovery. Reconsider a registry
only after Claude Code and OpenTelemetry expose a concrete incompatibility that an
explicit mapping cannot handle cleanly.

## P3a: directed-cycle diagnostic

Status: shipped on `main`.

`EvidenceBundle` now has an optional typed
`dependency_edges: tuple[tuple[str, str], ...]` field. Its endpoints must be known
events from the same task, and present edges are covered by the evidence digest.

Claude Code populates the field from `parentUuid` joins. OpenTelemetry populates it
from resolved `parentSpanId` joins. The default diagnostic emits warnings for
cycles but cannot route a decision. Missing structural evidence is never
fabricated.

## P3b: documentation consolidation

Status: shipped on `main`.

Writing and launch material now lives under `docs/writing/`:

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

Technical references remain at stable locations. The writing index and repository
links are checked with the rest of the documentation.

## P4: supported Python matrix validation

Status: shipped on `main`.

The declared Python 3.10 through 3.13 support range is now exercised at three
distribution boundaries:

- `make reproduce` validates the source checkout on every supported version;
- the package job builds, installs, and evaluates a real bundle through the wheel
  from outside the source checkout on every supported version; and
- the composite Action runs CSV `ASSIST` and OpenTelemetry `SCALE` paths on every
  supported version while preserving the full five-scenario dogfood suite on
  Python 3.12.

The installed-wheel smoke test asserts the expected `ASSIST` exit code and
byte-identical report rather than treating the intentional non-zero CI result as a
workflow failure. Package metadata publishes explicit Python 3.10, 3.11, 3.12,
and 3.13 classifiers.

## P5: delegated Claude Code session-tree accounting

Status: shipped on `main`.

`source.claude-code-session-tree@1` is an additive adapter over the unchanged
single-file and normalized evidence boundaries.

It discovers the documented adjacent subagent transcript layout, requires a
paired metadata record for every child, and binds all source files into one frozen
manifest. Root prompts remain economic tasks. Child model and tool calls inherit
the spawning task, including recursively nested children.

The adapter verifies and removes duplicated fork bootstrap envelopes before
accounting, retains the parent delegation event, and adds cross-file dependency
edges. Missing files, unknown delegation tools, duplicate identities, spawn
cycles, incorrect depth, and remaining unexpanded delegation fail closed.

The conformance case is synthetic and content-marked. It proves complete
parent-child accounting, privacy filtering, source drift detection, legacy and
current bootstrap shapes, nested attribution, CLI conversion, Action execution,
and byte-reproducible artifacts. It does not claim enterprise ROI.

## Priority

| Rank | Item | Status | Effort | Dependency | Why now |
|---:|---|---|---|---|---|
| 0 | P0: Claude Code + public case | shipped | complete | none | Proven foundation |
| 1 | P1: GitHub Action | shipped | complete | none | Distribution layer over fixed semantics |
| 2 | P2: OpenTelemetry GenAI adapter | shipped | complete | P1 dogfood | Cross-platform source contract |
| 3 | P3a: cycle diagnostic | shipped | complete | typed parentage | Structural warning without routing |
| 3 | P3b: documentation consolidation | shipped | complete | none | Stable technical navigation |
| 4 | P4: supported Python matrix | shipped | complete | P0 through P3b | Distribution validation |
| 5 | P5: delegated session tree | shipped | complete | P0 adapter contract | Include nested agent spend without weakening v1 |

Marketplace tags remain separate from implementation and cross-version
validation.
