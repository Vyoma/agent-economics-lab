# Claim ledger

Append-only. One file per issuance, named by the date and the revision
it was issued against, never rewritten. `make ledger` regenerates this
page and fails the build on anything false.

A claim that no longer reproduces because a gate was refactored is not
a claim that was wrong; it is one you check out a commit to test, and
the verdict names which commit. A claim the evidence contradicts is a
published falsehood and fails the build until it is retracted.

**9 claims on the record, 9 reproducing against the current tree.**

| issued | claim | decision | against today's code |
|---|---|---|---|
| 2026-08-31 | The checks-only conversion of the same session withholds a verdict: it has no economi... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | The bundled Claude Code session does not clear the shipped gates; this evidence route... | `ASSIST` | **SUPPORTED** |
| 2026-08-31 | Remove gate.acceptable-rate and this otherwise-passing evidence yields INCOMPLETE, no... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | Remove gate.counterfactual and this otherwise-passing evidence yields INCOMPLETE, not... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | Remove gate.net-value and this otherwise-passing evidence yields INCOMPLETE, not SCAL... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | Remove gate.runtime-caps and this otherwise-passing evidence yields INCOMPLETE, not S... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | Remove gate.tail-cost and this otherwise-passing evidence yields INCOMPLETE, not SCAL... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | Remove gate.unit-economics and this otherwise-passing evidence yields INCOMPLETE, not... | `INCOMPLETE` | **SUPPORTED** |
| 2026-08-31 | The bundled Claude Code tree session clears every shipped gate: this evidence yields ... | `SCALE` | **SUPPORTED** |

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

### `2026-08-31-invariant-acceptable-rate-7fc24c37.claim.json`

> Remove gate.acceptable-rate and this otherwise-passing evidence yields INCOMPLETE, not SCALE: the requirement does not depart with the gate that served it.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

### `2026-08-31-invariant-counterfactual-7fc24c37.claim.json`

> Remove gate.counterfactual and this otherwise-passing evidence yields INCOMPLETE, not SCALE: the requirement does not depart with the gate that served it.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

### `2026-08-31-invariant-net-value-7fc24c37.claim.json`

> Remove gate.net-value and this otherwise-passing evidence yields INCOMPLETE, not SCALE: the requirement does not depart with the gate that served it.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

### `2026-08-31-invariant-runtime-caps-7fc24c37.claim.json`

> Remove gate.runtime-caps and this otherwise-passing evidence yields INCOMPLETE, not SCALE: the requirement does not depart with the gate that served it.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

### `2026-08-31-invariant-tail-cost-7fc24c37.claim.json`

> Remove gate.tail-cost and this otherwise-passing evidence yields INCOMPLETE, not SCALE: the requirement does not depart with the gate that served it.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

### `2026-08-31-invariant-unit-economics-7fc24c37.claim.json`

> Remove gate.unit-economics and this otherwise-passing evidence yields INCOMPLETE, not SCALE: the requirement does not depart with the gate that served it.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

### `2026-08-31-tree-baseline-7fc24c37.claim.json`

> The bundled Claude Code tree session clears every shipped gate: this evidence yields SCALE.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `SCALE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

