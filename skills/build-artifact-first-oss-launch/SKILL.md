---
name: build-artifact-first-oss-launch
description: Validate whether an AI or developer-tool idea represents a real market gap, choose a defensible open-source wedge, audit and improve the repository, define falsifiable claims and modularity guarantees, and produce coherent GitHub-profile and launch materials. Use for idea validation, competitive-gap analysis, OSS strategy, repo audits, research-shaped benchmarks, agent-economics or multi-agent tooling, founder/researcher positioning, GitHub discoverability, and requests for multiple independent reviewer agents.
---

# Build an Artifact-First OSS Launch

Turn a broad idea into one credible category, a runnable artifact, a bounded claim,
and a launch surface that technical users can verify without trusting credentials.

## Non-negotiable operating rules

1. Inspect supplied research, code, repository state, and public surfaces before
   proposing positioning.
2. Verify unstable market, product, and competitor facts with current primary
   sources. Separate evidence from inference. If browsing is unavailable or
   prohibited, mark the market verdict unresolved rather than guessing.
3. Produce a decision record, evidence ledger, and rejected-alternatives log. Never
   claim to provide private hidden reasoning or chain-of-thought.
4. Prefer one falsifiable wedge over a broad platform or resource collection.
5. Treat existing tools as evidence sources or enforcement layers when appropriate;
   do not require replacement merely to make the new project look differentiated.
6. Never claim an integration until a fixture-backed adapter or end-to-end test
   ships.
7. Never generalize synthetic or controlled results into production prevalence or
   effectiveness.
8. When a user names living-person personas, translate them into explicit review
   lenses. Do not impersonate the people.
9. Preserve user work and avoid public publishing, profile edits, commits, or other
   external side effects without the authority required by the active environment.

## Load the right supporting material

- Always read [references/operating-model.md](references/operating-model.md).
- Read [references/audit-rubric.md](references/audit-rubric.md) before scoring an
  idea, repository, benchmark, profile, or launch package.
- Read [references/case-study-agent-economics.md](references/case-study-agent-economics.md)
  when the task concerns agent economics, modular assurance, observability gaps,
  semantic circuit breakers, or this project's history.
- Read [references/portability.md](references/portability.md) when packaging or
  handing the skill to Codex, Claude Code, or a generic agent.
- Copy and complete only the needed files from `assets/`; do not load every template
  by default.

## Workflow

### 1. Establish the evidence inventory

Collect:

- the user's desired outcome and target audience;
- supplied research, scripts, repositories, lessons, and profile copy;
- existing claims and proposed category language;
- actual runnable commands and checked-in results;
- current competitors and adjacent categories; and
- constraints on publishing, privacy, employer disclosure, and external actions.

Create a claim ledger using `assets/claim-ledger.md`. Label each statement:
`VERIFIED`, `INFERENCE`, `HYPOTHESIS`, `PLANNED`, or `REJECTED`.

### 2. Test whether the gap is real

Build a gap map using `assets/gap-map.md`:

1. Name the concrete decision the audience cannot make confidently.
2. Map which existing products already observe, evaluate, govern, or enforce it.
3. Identify what remains fragmented, non-portable, unauditable, or silently absent.
4. Check whether the proposed project closes that gap or merely renames an existing
   feature.
5. State the gap without “first,” “only,” or vague platform language.

Use this form:

> For **[specific audience]**, existing **[tools/evidence]** do not provide a
> portable, inspectable answer to **[decision]** because **[missing boundary or
> invariant]**.

Reject the idea as a gap when existing tools already provide the same decision,
interface, evidence contract, and safety property with comparable portability.

### 3. Select one wedge and one safety property

Choose the smallest artifact that proves the category:

- one input boundary;
- one visible decision or output;
- one explicit invariant;
- one controlled benchmark or counterexample set;
- one reproduction command; and
- one honest limitation.

Prefer deletion tests over architecture diagrams. If modularity is a differentiator,
prove all three operations:

1. delete an optional module and observe only its diagnostic disappear;
2. delete required coverage and produce an explicit incomplete state; and
3. add a restrictive local module without editing the core.

### 4. Design the compatibility boundary

Keep source-specific ingestion outside the canonical evidence model. Record source
adapter, schema version, enabled checks, required coverage, missing coverage, and an
evidence digest in every output.

Distinguish:

- evidence sources from decision logic;
- diagnostics from routing gates;
- routing decisions from runtime enforcement; and
- supported adapters from future contribution lanes.

### 5. Build or audit the repository

Run:

```bash
python3 <skill-dir>/scripts/audit_repo.py <repository>
```

Replace `<skill-dir>` with this skill's directory. Address high-confidence findings
that fall within the user's requested scope. At minimum, inspect:

- README quick start and clean-run commands;
- tests and deterministic reproduction;
- LICENSE, CONTRIBUTING, SECURITY, CI, and status label;
- examples labeled synthetic when applicable;
- data/protocol/limitations for research-shaped claims;
- extension interfaces and add/delete behavior;
- contribution lanes that produce real evidence; and
- claims that exceed shipped code.

Do not manufacture six repositories to fill a GitHub profile. Keep a benchmark,
protocol, data card, note, and methodology together when they support one claim.

### 6. Run independent reviewer passes

When subagents are available and the user requests delegation, run three bounded
reviews in parallel:

- **OSS/DX reviewer:** installation, code quality, extension friction, maintenance,
  and developer trust.
- **Enterprise/category reviewer:** decision owner, economic value, compatibility,
  procurement reality, and category clarity.
- **Research/education reviewer:** falsifiability, denominator, protocol, negative
  scope, and reproducibility.

Give reviewers raw artifacts and minimal task context. Require each reviewer to
send one critique to another reviewer before finalizing. Synthesize disagreements;
do not average incompatible recommendations. If subagents are unavailable, write
three independent memos sequentially and cross-critique them explicitly.

Use `assets/reviewer-briefs.md` for the prompts.

### 7. Validate before positioning

Require evidence proportional to each claim:

- run unit and integration tests;
- regenerate checked-in benchmark results;
- verify the primary demo and reproduction commands;
- verify module deletion/addition semantics;
- inspect a clean checkout when repository state permits;
- scan for unsupported compatibility or production claims; and
- state what was not tested.

For audit-only or no-modification tasks, redirect caches and generated output to a
writable temporary directory when the command supports it. Do not let validation
rewrite tracked artifacts. Skip a mutating command and record why when isolation is
not possible.

The profile and launch copy must be downstream of these results, never the source
of them.

### 8. Build the public surface

Use `assets/profile-readme.md` and `assets/launch-plan.md`.

Order the profile README:

1. category;
2. enterprise or practitioner question;
3. input → mechanism → output;
4. Question / Test / Result;
5. reproduction command;
6. limitation;
7. contribution request; and
8. verified biography and contact links.

Keep the short GitHub bio human, searchable, and evidence-safe. Put numbers beside
their definitions and denominators, not in the bio. Pin quality, not quantity.

### 9. Deliver a complete handoff

Return:

- gap verdict and exact gap statement;
- claim ledger and rejected alternatives;
- repository changes or prioritized findings;
- tests and reproduction evidence;
- category statement, repository description, topics, and profile copy;
- launch sequence and contribution lanes;
- unresolved facts requiring user confirmation; and
- exact next external action, if any.

## Stop conditions

Do not publish or describe the project as ready when:

- the primary command does not run from a clean environment;
- benchmark rows cannot be regenerated;
- required evidence can be deleted without a visible incomplete state;
- claimed vendor integrations lack fixtures and tests;
- synthetic results are presented as production evidence;
- contact, employer, location, or availability details are unconfirmed; or
- the repository has no defensible distinction from an existing product.
