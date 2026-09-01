# Claim ledger

Append-only. One file per issuance, named by the date and the revision
it was issued against, never rewritten. `make ledger` regenerates this
page and fails the build on anything false.

A claim that no longer reproduces because a gate was refactored is not
a claim that was wrong; it is one you check out a commit to test, and
the verdict names which commit. A claim the evidence contradicts is a
published falsehood and fails the build until it is retracted.

**14 claims on the record, 11 reproducing against the current tree.**

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
| 2026-08-31 | The same 20 SWE-bench Verified tasks run with claude-4.5-haiku-high as reference. 55%... | `STOP` | **UNVERIFIED** |
| 2026-08-31 | The claude-4.5-haiku-high reference arm over the same 20 tasks, with the same declare... | `STOP` | **SUPPORTED** |
| 2026-08-31 | On real SWE-bench trajectories, removing gate.acceptable-rate does not soften the ver... | `INCOMPLETE` | **UNVERIFIED** |
| 2026-08-31 | Real deployment, not a fixture: 20 mini-SWE-agent runs of claude-opus-4.6 on SWE-benc... | `STOP` | **UNVERIFIED** |
| 2026-08-31 | 20 mini-SWE-agent runs of claude-opus-4.6 on SWE-bench Verified, now declaring that t... | `STOP` | **SUPPORTED** |
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

### `2026-08-31-swebench-haiku-0b3c38bf.claim.json`

> The same 20 SWE-bench Verified tasks run with claude-4.5-haiku-high as reference. 55% resolved at $5.37. The shipped economic gates do not clear it either: STOP.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `STOP`
- Evidence: `(absent)`
- Issued against commit: `0b3c38bfe8a6a143ff46ce5250d30d7760fe504d`
- Against the current tree: **UNVERIFIED**
- the evidence this names is not shipped in this repository

### `2026-08-31-swebench-haiku-attributed-ae7527bc.claim.json`

> The claude-4.5-haiku-high reference arm over the same 20 tasks, with the same declared adjudicator: STOP.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `STOP`
- Evidence: `examples/public-swebench/arms/reference-haiku.json`
- Issued against commit: `ae7527bc3e9fad6e41110a53cb7ea607e9f41cfa`
- Against the current tree: **SUPPORTED**

### `2026-08-31-swebench-invariant-0b3c38bf.claim.json`

> On real SWE-bench trajectories, removing gate.acceptable-rate does not soften the verdict to a pass: the requirement remains and the run yields INCOMPLETE.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `INCOMPLETE`
- Evidence: `(absent)`
- Issued against commit: `0b3c38bfe8a6a143ff46ce5250d30d7760fe504d`
- Against the current tree: **UNVERIFIED**
- the evidence this names is not shipped in this repository

### `2026-08-31-swebench-opus-0b3c38bf.claim.json`

> Real deployment, not a fixture: 20 mini-SWE-agent runs of claude-opus-4.6 on SWE-bench Verified, outcomes adjudicated by the hidden tests rather than self-reported. 70% resolved at $8.44. The shipped economic gates do not clear it: STOP.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `STOP`
- Evidence: `(absent)`
- Issued against commit: `0b3c38bfe8a6a143ff46ce5250d30d7760fe504d`
- Against the current tree: **UNVERIFIED**
- the evidence this names is not shipped in this repository

### `2026-08-31-swebench-opus-attributed-ae7527bc.claim.json`

> 20 mini-SWE-agent runs of claude-opus-4.6 on SWE-bench Verified, now declaring that the SWE-bench hidden tests adjudicated the outcomes. The shipped gates still do not clear it: STOP, and the audit additionally withholds because nobody has attested that instrument.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `STOP`
- Evidence: `examples/public-swebench/arms/candidate-opus.json`
- Issued against commit: `ae7527bc3e9fad6e41110a53cb7ea607e9f41cfa`
- Against the current tree: **SUPPORTED**

### `2026-08-31-tree-baseline-7fc24c37.claim.json`

> The bundled Claude Code tree session clears every shipped gate: this evidence yields SCALE.

- Issued **2026-08-31** by agent-economics-lab
- Decision claimed: `SCALE`
- Evidence: `examples/claude-code-tree/bundle.json`
- Issued against commit: `7fc24c370aafc53cd459ae8ed0093d9564903688`
- Against the current tree: **SUPPORTED**

