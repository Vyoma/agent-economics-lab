# Artifact-First Operating Model

## Contents

1. Objective
2. Evidence hierarchy
3. Gap validation
4. Wedge selection
5. Claim architecture
6. Modularity as a safety property
7. Repository design
8. Profile and launch design
9. Multi-reviewer synthesis
10. Decision record format

## 1. Objective

Optimize for durable technical trust and qualified inbound interest, not raw
impressions. The strongest public identity is a repeated loop:

```text
hard deployment question
        ↓
runnable artifact
        ↓
controlled falsification attempt
        ↓
bounded result + limitation
        ↓
specific contribution request
```

Credentials can lower initial uncertainty, but they cannot substitute for the loop.

## 2. Evidence hierarchy

Rank public claims by the strongest available support:

| Level | Evidence | Permitted language |
|---|---|---|
| 0 | Idea only | “I am exploring…” |
| 1 | Executable example | “The included example demonstrates…” |
| 2 | Unit/integration tests | “The implementation enforces…” |
| 3 | Fixed synthetic benchmark | “In this controlled benchmark…” |
| 4 | External redacted cases | “Across these contributed cases…” |
| 5 | Prospective production study | Narrow production finding with protocol and uncertainty |

Never borrow language from a higher level. In particular, zero failures in a fixed
synthetic benchmark support a tested invariant under those perturbations; they do
not prove real-world safety or effectiveness.

## 3. Gap validation

Separate five layers that are often conflated:

1. **Observation:** traces, spans, tokens, latency, tool calls.
2. **Evaluation:** task outcomes, quality labels, graders, benchmarks.
3. **Economics:** labor, remediation, incident loss, counterfactual value.
4. **Decision:** scale, assist, stop, or incomplete.
5. **Enforcement:** budgets, permissions, timeouts, routing, escalation.

A real gap often sits at a boundary between mature layers. Example: observability
and eval products may supply evidence while finance, risk, and engineering still
lack one portable assurance case for a deployment decision.

Ask:

- What exact decision is still made in spreadsheets, meetings, or intuition?
- Which inputs exist but are not joined?
- What happens when a required input disappears?
- Is the output portable across vendors?
- Can a reviewer reconstruct the decision later?
- Does the proposal complement or unnecessarily replace installed tools?

## 4. Wedge selection

Score candidate wedges on:

- decision importance;
- evidence availability;
- falsifiability;
- implementation size;
- vendor independence;
- contribution surface; and
- credibility of negative scope.

Prefer the wedge with the shortest path from raw evidence to a consequential,
auditable output. Avoid leading with a protocol name, UI, agent framework, MCP
transport, or resource wiki unless that element is itself the unsolved decision.

## 5. Claim architecture

Maintain a claim ledger with five states:

- `VERIFIED`: directly supported by inspected artifacts or primary sources.
- `INFERENCE`: reasoned from verified facts; label it explicitly.
- `HYPOTHESIS`: testable but not yet supported.
- `PLANNED`: roadmap item, contribution lane, or intended integration.
- `REJECTED`: examined and deliberately not claimed.

Every major statement should identify:

- subject and scope;
- denominator;
- observation window;
- source or reproduction command;
- known confounders; and
- expiration condition.

## 6. Modularity as a safety property

“Modular” is not proven by a plugin directory. It is proven by composition
semantics.

Define:

- a canonical evidence bundle;
- typed, versioned modules;
- diagnostic modules that cannot alter routing;
- gate modules that may preserve or restrict routing;
- required coverage independent of installed modules; and
- an explicit incomplete result.

Test:

| Operation | Expected behavior |
|---|---|
| Remove optional diagnostic | Finding disappears; routing is unchanged |
| Remove required gate | Missing dimension is named; result is incomplete |
| Add restrictive gate | Result may become more restrictive; core is unchanged |
| Change source adapter | Equivalent evidence yields the same canonical digest |

The central invariant is monotonic safety: removing an inconvenient requirement
must not manufacture a greener decision.

## 7. Repository design

One flagship repository should contain the whole inspectable claim:

- code and CLI;
- synthetic example and blank template;
- benchmark generator and checked-in rows;
- protocol, data card, result card, and note;
- methodology and limitations;
- CI, security policy, contribution guide, and license;
- issue templates for adapters, checks, cases, and claim challenges; and
- a two-minute modularity demo.

Use “no third-party runtime dependencies” only when build tooling still has
dependencies. Use “normalized CSV/JSON boundary” until vendor-specific export
mappers have pinned fixtures and tests.

## 8. Profile and launch design

The public profile should answer in under one minute:

1. What category does this person build in?
2. What hard question does the artifact answer?
3. What was tested?
4. What happened?
5. What is the limitation?
6. How do I reproduce it?
7. What contribution or collaboration is wanted?

Do not foreground logo walls, skill-icon grids, audience counts, trophy widgets, or
six weak pins. One coherent artifact is more credible than a crowded profile.

## 9. Multi-reviewer synthesis

Review lenses are constraints, not theater:

- OSS/DX asks whether a stranger can run, extend, and trust it.
- Enterprise/category asks whether a decision owner will recognize the pain and
  preserve existing investments.
- Research/education asks whether a skeptical reader can falsify and reproduce it.

Force cross-critique. Common productive tensions:

- memorable category language versus claim precision;
- small dependency surface versus realistic integrations;
- one flagship repository versus discoverable subprojects;
- commercial inbound versus privacy and employer constraints; and
- broad research agenda versus shipped capability.

Resolve tension by letting the artifact set the upper bound on public language.

## 10. Decision record format

Record each material decision as:

```text
Decision:
Status: accepted | rejected | deferred
Evidence:
Alternatives considered:
Why this choice fits the current evidence:
Claim boundary:
Revisit when:
```

This is the portable substitute for a hidden reasoning dump: it exposes inputs,
tradeoffs, rejected paths, and verification without requiring private internal
chain-of-thought.
