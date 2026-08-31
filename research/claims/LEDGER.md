# Claim ledger

Append-only. One file per issuance, named by the date and the revision
it was issued against, never rewritten. `make ledger` regenerates this
page and fails the build on anything false.

A claim that no longer reproduces because a gate was refactored is not
a claim that was wrong; it is one you check out a commit to test, and
the verdict names which commit. A claim the evidence contradicts is a
published falsehood and fails the build until it is retracted.

**2 claims on the record, 2 reproducing against the current tree.**

| issued | claim | decision | against today's code |
|---|---|---|---|
| 2026-08-31 | The checks-only conversion of the same session withholds a verdict: it has no economi... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | The bundled Claude Code session does not clear the shipped gates; this evidence route... | `ASSIST` | **SUPPORTED** |

## Each claim in full

### `2026-08-31-checks-only-4768c6df.claim.json`

> The checks-only conversion of the same session withholds a verdict: it has no economics and no attested instrument.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/checks-only/bundle.json`
- Issued against commit: `1d96bcdf034ff13e21662879b36df3ce3f6411a6`
- Against the current tree: **SUPPORTED**

### `2026-08-31-claude-code-4768c6df.claim.json`

> The bundled Claude Code session does not clear the shipped gates; this evidence routes to ASSIST.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `ASSIST`
- Evidence: `examples/claude-code/bundle.json`
- Issued against commit: `1d96bcdf034ff13e21662879b36df3ce3f6411a6`
- Against the current tree: **SUPPORTED**

