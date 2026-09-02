# Product requirements

What this package must do, for whom, and — with equal force — what it must
refuse to do. Requirements here are testable statements; each names the
surface that enforces it. A change that breaks one of these is a product
regression even if every test still passes, and a feature that serves none
of them is scope creep even if it is well built.

## Who it is for

**The operator deciding whether an agent earns more autonomy.** They have
traces, some outcome labels, a rate card, and pressure to answer "should we
scale this?" Their failure mode is answering from a success-rate screenshot
whose instrument nobody has validated. They need a bounded decision that
refuses when the evidence cannot support one.

**The reviewer who was handed someone else's green.** A PR comment, a slide,
a leaderboard row. They cannot re-run the harness and should not have to
trust its author. They need a portable claim that verifies — or refutes —
offline against the evidence's digest.

**The auditor of public agent data.** Datasets ship with outcome fields that
read as adjudicated and sometimes are not. They need a discipline that
freezes content-free evidence at a pinned revision, kills suspicions at base
rate before publication, and records clean bills with the same care as
defects.

Explicitly not a target: leaderboard building, model comparison, or any use
where an arm name is read as a measurement of a vendor's model.

## The jobs, and the surface that does each

1. **Turn traces + outcomes + rates + policy into one bounded decision**
   (`INCOMPLETE` / `SCALE` / `ASSIST` / `STOP`), with `SCALE` the only exit
   0, issued through one act that the audit can veto. Surface: `evaluate
   --ci`, the GitHub Action, `decide()`.
2. **Refuse green on evidence nobody collected.** Disabling a sole-provider
   gate, omitting an outcome instrument's attestation, or leaving delegated
   spend unaccounted yields `INCOMPLETE` with the grounds named. Surface:
   the fixed decision contract plus the audit; the mutation self-test proves
   the refusal on every run.
3. **Make the decision portable.** A claim file that anyone can verify
   against a bundle, yielding exactly SUPPORTED, REFUTED, or UNVERIFIED —
   never a crash and never silence. Surface: `claim` / `verify`, the ledger.
4. **Audit third-party data without inventing anything.** Content-free
   freezes, censuses, cross-checks, verification passes; findings that
   reproduce from upstream in one command. Surface: `research/corpus`,
   `make verify-upstream`.
5. **Hold its own numbers to the same bar.** Every published figure
   recomputes from frozen evidence; generated pages byte-compare in CI; a
   refuted claim fails the build until retracted. Surface: `make reproduce`,
   `make ledger`.

## Non-goals, stated as refusals

- No inference of missing economics. A blank cost is a refusal, never $0.00.
- No outcome labels invented from success heuristics; an unlabelled task is
  unlabelled.
- No dynamic coverage on shipped surfaces: requirements never shrink to
  whatever the enabled checks happen to cover.
- No streaming/online decisions: the unit of decision is a frozen bundle.
  Past memory, the answer is sharding, not incremental state.
- No network at decision time, ever. The verdict path is offline; only
  dataset freezing and upstream spot-checks touch the network, and they say
  so.

## Success, measured

- A reader reaches the strongest finding without scrolling
  (`test_the_readme_leads_with_the_finding`).
- One command from clean clone to green on stock Python 3.10+, no
  third-party runtime dependencies (`make reproduce` in CI on 3.10–3.13).
- The decision path is linear to a million events and says what happens
  after ([the measured envelope](at-scale.md), CI ratio guard).
- The corpus grows: entries are addable by third parties under a written
  contract ([contributing an audit](contributing-an-audit.md)) without the
  author in the loop.
- Every accusatory number in the repository can be recomputed by a hostile
  reader from frozen evidence, or it does not ship.
