# Specification: the decision contract

Normative for `assurance.decision-contract@2` and `assurance.claim@1`, as
shipped in agent-economics 0.9.0. This document is written so a second
implementation could be built against it and produce byte-identical digests
and identical decisions; where behavior is deliberately surprising, the
reason is stated inline. Clause numbers are stable; the conformance tests in
[tests/](tests/) cite them. MUST/MUST NOT are used in the RFC sense.

## 1. Decisions and exit codes

**1.1** A decision is exactly one of `INCOMPLETE`, `SCALE`, `ASSIST`,
`STOP` (string-valued, name equals value).

**1.2** In CI mode (`evaluate --ci`, the GitHub Action), the exit code
mapping is `SCALE: 0`, `INCOMPLETE: 2`, `ASSIST: 3`, `STOP: 4`. **Exit 0
MUST be reachable only by `SCALE`.** Operational failures (unreadable
evidence, invalid attestations, unknown checks) exit 2 — indistinguishable
from `INCOMPLETE` by design: a decision that could not be computed is an
incomplete decision, not a new success code.

**1.3** Exit code 1 is not in the decision set. The GitHub Action maps any
exit code outside {0,2,3,4} to (`INCOMPLETE`, 2).

## 2. Coverage

**2.1** The six core dimensions: `outcome_quality`, `unit_economics`,
`tail_risk`, `business_value`, `counterfactual`, `runtime_caps`. All six
form the default required coverage.

**2.2** Two opt-in dimensions exist outside the default set:
`delegation_closure` and `evidence_provenance`. Dimensions are compared by
normalized name; a plain string and the enum member with that value are the
same dimension.

**2.3** Only checks in `gate` mode supply coverage. A diagnostic MUST
declare empty coverage and MUST NOT carry a failure route.

## 3. Routing

**3.1** Precedence is fixed: `missing-coverage > stop > assist > scale`
(constant `routing_semantics` in the contract manifest).

**3.2** `missing_coverage = required − enabled` (gate-mode checks only).
When non-empty, the answer is `INCOMPLETE` and **no check runs at all** —
running checks under an unmet contract would manufacture partial confidence.

**3.3** A gate that raises is converted to a synthetic `FAIL` routed to its
declared failure route, defaulting to `STOP`. A required dimension all of
whose providers crashed is unmet coverage → `INCOMPLETE`. A diagnostic that
raises becomes an error-severity finding and MUST NOT move the decision.

**3.4** A failed gate routes to its declared route; any `STOP` route
outranks any `ASSIST`. No failures and no missing coverage → `SCALE`.

## 4. The one act (`decide`)

**4.1** Every surface that can issue a green decision routes through one
function that evaluates and audits as one act. A `SCALE` the audit refuses
is returned as `INCOMPLETE` with each audit ground appended to
`missing_coverage` as `"audit: <ground>"`. All other fields of the case are
unchanged, so a demoted case still shows its all-PASS check results — the
refusal is about admissibility, not about the checks.

**4.2** `ASSIST`, `STOP`, and `INCOMPLETE` pass through untouched: they are
already refusals to scale, and demoting them would hide why the evidence
failed behind why it was inadmissible.

**4.3** The audit's grounds, in fixed order: unprovided coverage (a required
dimension no enabled check supplies); unaccounted delegation (a delegating
event absent from the declared manifest); unattested instruments (§7);
no evidence instrument recorded (an empty `label_source` is a ground, not a
note, so deleting the field is never the cheap way to pass); delegation
whose extent was never recorded (a known delegation tool with no children in
the dependency graph); delegated spend never established (closure measured
by count because a delegated event's cost could not be resolved);
fail-closed invariant broken (a gate removal that did not yield
`INCOMPLETE` under the fixed contract, checked by mutation on every run).

## 5. The decision contract digest

**5.1** The digest is SHA-256 over the UTF-8 encoding of
`json.dumps(manifest, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)`.

**5.2** The manifest carries: the schema constant
(`assurance.decision-contract@2`), the engine implementation constant, the
routing-semantics constant, the sorted required-coverage names, and one
entry per check **in evaluation order** — reordering checks changes the
digest, and claims deliberately record evaluation order. Each entry:
`manifest_id` (`id@version`), `mode`, `covers` (sorted names),
`failure_route` (the route's value; the literal `"dynamic"` for a gate with
no declared route; `null` for diagnostics), `implementation_digest`, and
`config` **only when non-empty** — an absent key and an empty mapping are
the same contract, so old digests survive the field's introduction.

**5.3** `implementation_digest` is SHA-256 of the check's `run` source:
`inspect.getsource`, dedented, per-line right-stripped, joined with `"\n"`,
stripped. It is **non-transitive** — helpers and closure state are not
captured, and this limit is documented rather than papered over. A check
whose source cannot be retrieved MUST be refused, not admitted unbound.

## 6. The evidence digest

**6.1** SHA-256 over the same JSON serialization flags as §5.1, of a payload
with keys: `events` (list, bundle order, each event a mapping of exactly
`task_id, event_id, timestamp, event_type, name, model, input_tokens,
output_tokens, direct_cost_usd, status, arguments`), `outcomes` (sorted by
task), `rates`/`baseline`/`policy` (each replaced by `{"unsupplied": <name>}`
when explicitly declared absent), and, **only when truthy**:
`declared_delegations`, `label_source`, `task_manifest`,
`dependency_edges`.

**6.2** The digest MUST be recomputed from contents on every read and MUST
NOT be stored: the bundle's mappings are mutable, and a stored digest made
"tamper-evident" false in this project's own history.

**6.3** Normalization precedes digesting: duplicate event ids rejected;
events sorted by `(task_id, timestamp, event_id)`; mappings key-sorted;
dependency edges and declared delegations sorted.

## 7. Attestation

**7.1** An outcome instrument is named by the bundle (`label_source`), never
invoked; the verdict path is inference-free and offline.

**7.2** An instrument is accepted iff it is independently verified
(recorded as such, no agreement figure claimed), or a single attestation
record exists whose method is known, whose agreement meets that method's
floor (`agreement-vs-human-adjudication` 0.80, `raw-agreement` 0.80,
`cohens-kappa` 0.60, `fleiss-kappa` 0.60, `krippendorff-alpha` 0.667,
`held-out-accuracy` 0.80), whose sample size meets the policy minimum
(default 100), and whose age at the supplied `as_of` date is within the
policy window (default 180 days) and not negative — a future-dated
calibration is not a calibration that has happened.

**7.3** `test-retest-agreement` carries a floor (0.80) but is
**reliability-only**: it can never make an instrument assessable, because an
instrument that repeats itself can be systematically wrong about everything.
Recording the figure is encouraged; clearing the gate with it is forbidden.

**7.4** `as_of` is required, never defaulted to the wall clock: a verdict
MUST NOT change because time passed between two runs of the same evidence.

## 8. Claims

**8.1** Schema `assurance.claim@1`. A claim records: the assertion, the
decision, the evidence digest, the decision-contract digest, the check
bindings (`id`, `version`, `implementation_digest`) **in evaluation order**,
the required coverage, `issued_at`, optional issuer and source commit.

**8.2** Verification is **total**: it returns exactly `SUPPORTED`,
`REFUTED`, or `UNVERIFIED` and MUST NOT raise. The verdict semantics:

- `REFUTED` — the evidence digest does not recompute; or the contract
  digest does not recompute; or re-evaluation yields a different decision.
- `UNVERIFIED` — a bound check is unknown, version-mismatched, or
  source-substituted; the claim ships a gate covering a dimension it does
  not require (a requirement does not depart with the gate that served it);
  a shipped-contract claim requires less than the shipped coverage; the
  policy or baseline is inert (thresholds no evidence could fail); or
  verification could not complete for any other reason.
- `SUPPORTED` — everything above passed. Caveats may attach; they never
  upgrade or downgrade the verdict.

**8.3** A refuted published claim MUST fail the build until retracted, never
quietly regenerated.

## 9. Non-inference invariants

**9.1** A blank cost is a refusal, never $0.00. A model event with no
explicit cost, no rate-card entry, or zero token usage under a rate card is
invalid evidence, not free work.

**9.2** Delegated work is accounted cost-weighted where costs resolve;
where any delegated cost cannot be established, closure MUST fall back to
counting and MUST say so (`basis`), because a weaker measurement named as
such beats a confident zero.

**9.3** Nothing on the verdict path touches the network.

## 10. Conformance

A build conforms when `make reproduce` is green from a clean clone: the full
suite, every generated artifact byte-compared, every published claim
verifying, the mutation self-test's fail-closed invariant holding, and the
ledger free of refuted claims. The measured envelope for the reference
implementation is stated in [docs/at-scale.md](docs/at-scale.md); the
envelope is descriptive, not normative.
