# Agent Scale Decision Contract

Use this one-page contract for one named agent workload. Complete it before
reviewing candidate results. A blank field is not approval.

## Decision header

| Field | Value |
|---|---|
| Workload and unit of work | |
| Decision owner | |
| Population and observation window | |
| Requested operating mode | `SCALE / ASSIST / STOP` |
| Named counterfactual | |
| Policy ID and version | |
| Contract digest | |
| Review or expiry date | |

## Required claims

Replace the example thresholds with workload-specific values. Add domain-specific
claims when needed.

| Required claim | Threshold or acceptance rule | Evidence source | Check ID and version | Sole provider? | If absent | Owner |
|---|---|---|---|---|---|---|
| Outcome quality | | | | | `INCOMPLETE` | |
| Cost per acceptable outcome | | | | | `INCOMPLETE` | |
| Tail cost | | | | | `INCOMPLETE` | |
| Absolute business value | | | | | `INCOMPLETE` | |
| Value versus counterfactual | | | | | `INCOMPLETE` | |
| Runtime calls and spend | | | | | `INCOMPLETE` | |

## Source-completeness contract

For each source, distinguish an explicit zero from an absent value and reconcile
observed attempts against an independent run ledger.

Omitted, null, or blank cost fields must be rejected before defaults are applied.
An explicit `0.0` must retain source provenance.

| Source or field | Can zero be valid? | How absence is represented | Completeness test | Failure route |
|---|---|---|---|---|
| Outcome label | | | | `INCOMPLETE` |
| Trace and tool cost | | | | `INCOMPLETE` |
| Human review time | | | | `INCOMPLETE` |
| Remediation cost | | | | `INCOMPLETE` |
| Incident loss | | | | `INCOMPLETE` |
| Task manifest | No | Missing expected task ID | Exact observed task IDs equal frozen expected task IDs | `INCOMPLETE` |
| Attempt or run ledger | No | Missing expected attempt ID or terminal status | Exact observed attempt IDs equal frozen expected attempt IDs, including failed and timed-out terminal statuses | `INCOMPLETE` |
| Counterfactual evidence | | | | `INCOMPLETE` |

## Routing semantics

| Condition | Decision |
|---|---|
| Missing required coverage or source evidence | `INCOMPLETE` |
| Failed gate with declared `ASSIST` route | `ASSIST` |
| Failed gate with declared `STOP` route | `STOP` |
| Complete evidence and every scale gate passes | `SCALE` |

`INCOMPLETE` means the declared claim cannot be evaluated. It is not a weaker
`STOP`, and it must not be converted to `SCALE` by dropping the missing
requirement.

## Adversarial pre-launch checks

- [ ] Disable each sole-provider required check. The result never improves.
- [ ] Delete one outcome record. The result is rejected or becomes `INCOMPLETE`.
- [ ] Delete one failed or timed-out execution event. Attempt or run reconciliation detects it.
- [ ] Remove each cost field. Absence never becomes an implicit zero.
- [ ] Supply an explicit `0.0` cost. The value retains source provenance.
- [ ] Change check order. The decision remains identical.
- [ ] Add an optional diagnostic. The bounded decision remains identical.
- [ ] Change the contract. The contract version and digest change.
- [ ] Reproduce the decision from frozen evidence and policy inputs.

## Decision record

| Field | Value |
|---|---|
| Evidence digest | |
| Decision-contract digest | |
| Decision | `INCOMPLETE / SCALE / ASSIST / STOP` |
| Failed or missing claims | |
| Required controls | |
| Rollback trigger | |
| Signed owners | |

## Three operating rules

No outcome label, no scale.

No named counterfactual, no ROI.

No required coverage, no green.
