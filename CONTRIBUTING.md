# Contributing

The project optimizes for auditable claims over feature breadth.

## Orientation, if you are new here

Read these three, in order, before writing anything:

1. **[SPEC.md](SPEC.md)** - the normative contract. Decisions and exit codes,
   coverage, routing precedence, both digest recipes, attestation floors,
   claim verdicts. If a change alters behaviour described there, it is a
   contract change and needs the spec updated in the same pull request.
2. **[docs/prd.md](docs/prd.md)** - who this is for and, more usefully, the
   things it refuses to do. Several plausible features are non-goals on
   purpose; the refusals are load-bearing.
3. **[research/EVALS.md](research/EVALS.md)** - how good the instrument is,
   including the capabilities nothing yet measures. It is the fastest way to
   see what is solid and what is not.

The repository is roughly four things. `agent_economics/` is the library and
CLI, dependency-free. `tests/` holds the suite, including a conformance file
that cites spec clauses by number. `research/` holds the experiments and the
audit corpus, where every published figure is regenerated from frozen
evidence rather than typed. `docs/` is the prose, most of it rendered from
code.

Two habits carry most of the quality here. **A guard is not finished until
you have watched it fail** - break the thing it protects, confirm it goes
red, put it back. This project has shipped guards that passed with the
defect restored, and the practice exists because of them. And **when a
comment explains a hole, fix every instance of the hole**, not the one in
front of you; the recurring defect in this codebase has been a diagnosis
written down and applied once.

## Everything here is published

This is a public repository. Commits, commit messages, pull request bodies,
issue threads, and branch names are all permanently visible, including to
people who are not looking for them and including after deletion.

Keep out of all of them: material internal to an employer or client,
customer or account identifiers, unreleased plans, credentials, and personal
information about anyone. If a sentence would need a caveat before you said
it in a public talk, it does not belong in a commit message either. This
holds regardless of how sensitive the material feels; the judgement people
get wrong is usually about mundane internal context, not obvious secrets.

Working notes about how a change was made belong in your own scratch files,
which is why `tasks/` is git-ignored. Published self-analysis in the
project's voice - [docs/novelty.md](docs/novelty.md),
[docs/limitations.md](docs/limitations.md), the scar comments in the source -
is deliberate and welcome.

## Best first contributions

- An offline source adapter that maps a documented export to `EvidenceBundle` and
  proves digest/result equivalence against a canonical fixture.
- A typed assurance gate or diagnostic with declared coverage and failure semantics.
- A synthetic or fully anonymized assurance case from a real workload pattern.
- A permissioned paired frontier case with a frozen candidate family, identical task
  IDs, SHA-256 input digests, rubric versions, explicit full costs, and a predeclared
  decision rule.
- A counterexample that falsifies or narrows a benchmark hypothesis.
- A clearer outcome contract or counterfactual.
- A failure case that exposes incorrect math or a hidden assumption.
- A statistically sound uncertainty or segmentation method with no heavy runtime.

Please open an issue before adding a hosted service, dashboard, runtime proxy,
framework abstraction, or generalized policy language.

## Local verification

One command gates a push, and it is the one CI actually fails on:

```bash
make PYTHON=python3.12 gate
```

It regenerates every derived document, fails if that changed the tree, runs
the suite, and verifies the claim ledger. Wire it to `git push` once:

```bash
make hooks
```

Generated pages are the usual surprise. `research/CORPUS.md`,
`research/FINDINGS.md`, `research/EVALS.md`, `research/PROBE_SITES.md`,
`docs/at-scale.md` and the test count in `docs/index.md` are all rendered
from code and byte-compared, so editing one by hand fails the build. Change
the renderer, then commit what it produces.

`make reproduce` is the fuller run, including the pinned-commit defect
replays and the network-free research targets. `make verify-upstream` is the
only target that needs the network; it spot-checks frozen corpus rows
against the upstream datasets.

The project supports Python 3.10+ and keeps the core dependency-free. New runtime
dependencies require an issue explaining why the assurance claim cannot be made
without them.

## Claim discipline

Use precise language in code, docs, and issues:

- say **structural repetition warning**, not semantic-loop proof;
- say **dependency cycle**, not deadlock, unless wait/progress semantics are present;
- say **no additional model inference**, not zero compute;
- say **observed association**, not causal savings, without a valid design; and
- name the population, observation window, and counterfactual.

Tests should cover important non-claims as well as happy paths.

## Case-study safety

Do not submit customer data, secrets, personal information, proprietary prompts,
real customer identifiers, internal model names, or contract pricing. Aggregate,
redact, or synthesize evidence before opening an issue or pull request. Contributors
are responsible for having permission to share their material.

## Adding an audit to the corpus

The corpus is open to third parties under one written contract:
[docs/contributing-an-audit.md](docs/contributing-an-audit.md). It specifies
what a freeze must contain, why a suspicion has to survive its base rate
before it becomes a finding, and the rule that a published finding is never
edited in place. An entry that meets it is merged whoever submits it, and an
entry that does not is returned whoever submits it, including us.

## Licensing and attribution

By contributing you agree that your contribution is licensed under Apache-2.0, the
same licence as the project.

If your contribution derives from third-party data, code, or a specification, add
it to [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) in the same pull request,
naming the source, its licence, its pinned revision, and the extent of use. A
fixture without provenance cannot be merged.

Do not submit customer data, secrets, proprietary prompts, or contract pricing.

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
