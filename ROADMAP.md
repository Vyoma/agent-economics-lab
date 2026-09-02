# Roadmap: proof-of-concept to production

Maturity stated per layer, because "is it production-ready" has a different
honest answer for each. A stage claim below is backed by a named surface you
can run; where the next stage's gate is not yet met, the gap is stated
rather than rounded up.

## Layer maturity today (0.9.0)

| layer | stage | evidence | gap to next stage |
|---|---|---|---|
| Decision engine + contract | **Production-candidate** | 670 tests, mutation self-test on every run, measured linear to 10⁶ events, byte-stable digests across 3.10–3.13 in CI | no external production deployment has run it in anger; no semver stability promise yet |
| Claim / verify / ledger | **Production-candidate** | totality contract (SUPPORTED/REFUTED/UNVERIFIED, never a crash), ledger gates CI, refuted claims fail the build | claim schema not yet frozen as `1.0`; needs a written compatibility promise |
| Adapters (CSV, Claude Code, session-tree, OTel GenAI) | **Beta** | pinned conversion contracts, byte-compared example cases | field coverage tracks specific emitter versions; drift is caught, not absorbed |
| Corpus + audit discipline | **Operational** | four audited datasets, findings reproducible from upstream, contribution contract written | zero third-party entries so far; the contract is untested by a stranger |
| Distribution | **PoC** | public repo, one-command reproduce | not on PyPI (name unclaimed — deliberate, owner's call); no versioned releases/tags |

## Stage gates to production

Each is a checkbox with a concrete artifact, not a vibe:

1. **Freeze the public contract.** Publish `SPEC.md` as normative, tag its
   version, and promise: within a major version, decisions, exit codes,
   digests, and claim verdicts do not change meaning. Gate: a conformance
   test file that walks the spec clause by clause.
2. **Release discipline.** Tagged releases matching `CHANGELOG.md`; a
   release is `make reproduce` green from the tag's tarball on a clean
   machine. Gate: a release checklist in CI.
3. **PyPI publication.** Blocked on the owner's explicit decision (claims a
   name permanently). Everything else in packaging is ready: wheel builds,
   no runtime dependencies, 3.10–3.13.
4. **A stranger's corpus entry.** The contribution contract is only proven
   when someone we have never spoken to lands entry N under it unchanged.
   Gate: one merged third-party audit.
5. **A production consumer.** One team gating a real agent rollout on
   `evaluate --ci`, with the INCOMPLETE-on-missing-coverage behavior
   surviving contact with their evidence pipeline. Gate: a written case
   study, defects found included.

## What will not be on any roadmap

The non-goals in [docs/prd.md](docs/prd.md) are load-bearing: no invented
economics, no dynamic coverage on shipped surfaces, no network at decision
time, no leaderboard framing. A roadmap item that requires breaking one of
those is a fork's roadmap, not this repository's.
