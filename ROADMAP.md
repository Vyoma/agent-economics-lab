# Roadmap: proof-of-concept to production

Maturity stated per layer, because "is it production-ready" has a different
honest answer for each. A stage claim below is backed by a named surface you
can run; where the next stage's gate is not yet met, the gap is stated
rather than rounded up.

## Layer maturity today (0.10.0)

| layer | stage | evidence | gap to next stage |
|---|---|---|---|
| Decision engine + contract | **Production-candidate** | over 830 tests, mutation self-test on every run, measured linear to 10⁶ events, byte-stable digests across 3.10–3.13 in CI | no external production deployment has run it in anger; the package remains pre-1.0 |
| Claim / verify / ledger | **Production-candidate** | totality contract (SUPPORTED/REFUTED/UNVERIFIED, never a crash), ledger gates CI, refuted claims fail the build | claim schema remains `assurance.claim@1`; a semantic change requires a new schema id |
| Adapters (CSV, Claude Code, session-tree, OTel GenAI) | **Beta** | pinned conversion contracts, byte-compared example cases | field coverage tracks specific emitter versions; drift is caught, not absorbed |
| Corpus + audit discipline | **Operational** | 10 audited datasets across two domains, findings reproducible from upstream, contribution contract written | zero third-party entries so far; the contract is untested by a stranger |
| Distribution | **Beta** | self-contained wheel tested outside the checkout; tag/version/changelog binding; tagged-source reproduction; source-archive rebuild; checksummed GitHub release artifacts | not published to PyPI; no external consumer has exercised the release path |

## Stage gates to production

Each is a checkbox with a concrete artifact, not a vibe:

1. **Public contract: met for schema versions 1 and 2.** `SPEC.md` is
   normative, `tests/test_conformance.py` walks its clauses, and a semantic
   change requires a new schema id. The package is still pre-1.0; this is a
   schema compatibility promise, not a promise that every Python API is frozen.
2. **Release discipline: automated.** A tag must match both the package
   version and one dated changelog entry. Release CI runs `make reproduce`
   from the full tagged checkout, then rebuilds and exercises both the wheel
   and source archive outside that checkout before publishing checksums. The
   full-history step cannot honestly run from an archive because historical
   defect replay is part of the evidence; the workflow states and tests that
   boundary instead of quietly skipping it.
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
