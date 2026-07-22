# Architecture

Agent Economics Lab separates evidence normalization, single-arm assurance, and
paired experiment selection so each claim can be audited independently.

```text
offline platform exports
          |
          v
canonical EvidenceBundle per tested arm
  task fingerprints + rubric + traces + outcomes + rates + baseline + policy
          |
          +-------------------------------+
          |                               |
          v                               v
single-arm AssuranceEngine          paired FrontierEngine
typed gates and diagnostics         exact task alignment
coverage manifest                   exact breakage upper bound
INCOMPLETE/SCALE/ASSIST/STOP        paired cost lower bound
          |                               |
          +---------------+---------------+
                          v
             Markdown + JSON + SVG artifacts
             plan digest + evidence digests
```

## Evidence boundary

`EvidenceBundle` is the vendor-neutral offline boundary. Task input digests, rubric
versions, events, outcomes, rate cards, the baseline, and economic policy are
normalized and hashed deterministically.
Adapters are expected to remove raw prompts and responses unless a case explicitly
requires and permits them.

The source manifest identifies the adapter family. The evidence digest is
reproducibility metadata, not a signature or attestation.

## Single-arm engine

The assurance engine reconstructs task-level full cost, then evaluates an explicit
ordered tuple of typed checks. Diagnostics can emit findings but cannot route.
Gates can preserve or restrict a decision. Removing declared required coverage
returns `INCOMPLETE`.

## Paired frontier engine

The frontier manifest freezes the reference, complete candidate family, shared task
manifest path and digest, task-count minimum, breakage tolerance, cost target,
confidence, bootstrap samples, and seed.
Every arm is evaluated through the single-arm engine first.

The frontier then requires identical task IDs, input digests, and rubric versions
across arms. For each candidate it:

1. counts harmful paired regressions versus the reference;
2. computes an exact one-sided Clopper-Pearson upper bound;
3. reconstructs paired full effective costs;
4. computes a deterministic paired-bootstrap lower bound on cost reduction;
5. applies a Bonferroni-adjusted nominal alpha target across all planned quality and
   approximate bootstrap cost tests;
6. rejects any arm whose standard assurance decision is not `SCALE`; and
7. selects the lowest observed full-cost eligible tested candidate.

Incomplete candidate families, task-fingerprint drift, unknown costs, baseline or
policy drift, shared-model price drift, and under-resolved bootstrap tails fail closed.

## Dependency policy

The Python runtime uses only the standard library. This keeps offline reproduction
simple and makes the statistical and decision code inspectable. A new dependency
requires an issue showing why the claim cannot be implemented or tested without it.

## Extension boundaries

- Source adapters normalize pinned offline fixtures; they do not make live calls.
- Assurance checks declare whether they are gates or diagnostics.
- Frontier cases freeze experiment plans and matched evidence.
- Runtime authorization, sandboxing, durable state, and active enforcement remain
  outside this repository.
