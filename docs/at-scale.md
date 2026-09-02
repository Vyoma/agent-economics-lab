# At scale

The first question a fleet engineer asks is what happens at a
million events. This page is the measured answer, reproducible with
`make bench`, and it states what stays expensive as plainly as what
got fast.

Every number is the **full shipped decision path** — engine
evaluation, the audit's fourteen-variation mutation self-test,
delegation closure, cycle detection, and instrument attestation —
not a stripped-down core. The workload is synthetic *load*, never
synthetic *evidence*: deterministic, clock-free, digest-pinned, and
nothing it produces is presented as a finding about any agent.

| events | decide | throughput | peak engine memory | one digest |
|---:|---:|---:|---:|---:|
| 10,000 | 0.891s | 11,223/s | 10.2 MiB | 0.017s |
| 100,000 | 10.172s | 9,831/s | 99.1 MiB | 0.171s |
| 1,000,000 | 104.678s | 9,553/s | 978.7 MiB | 1.912s |

Scaling is linear: 100x the events costs 117.5x the time. A ratio guard runs in CI (`make bench-smoke`) and fails
the build if the engine ever goes superlinear on the realistic
shape.

Measured on macOS-26.6.2-arm64-arm-64bit, Python 3.12.13, process peak RSS 2,004.7 MiB at 1,000,000 events. One process, one core, no
dependencies. The bundle digests in
[RESULTS.json](../bench/RESULTS.json) let another machine confirm
it measured the same workload.

## What the scale pass found and fixed

Profiling `decide()` before this page existed found the engine
itself was a rounding error; the cost lived elsewhere, and one item
was a correctness bug, not a slowdown:

- **Cycle detection died at depth and the death was reported as a
  finding.** The detector was recursive, so a dependency chain
  about a thousand events deep raised `RecursionError` — which the
  diagnostic guard converted into a "could not run" control
  finding. Cycle detection silently stopped existing exactly when
  traces got big. It is iterative now and proven on a 50,000-deep
  chain, back edge and all.
- **The evidence was hashed fifteen times per decision.** The
  audit's mutation self-test re-evaluates one unchanged bundle
  under fourteen contract variations, and every evaluation
  recomputed the bundle's SHA-256. The digest is computed once per
  decision now and handed to the self-test; `verify` likewise
  reuses the digest it just recomputed and proved equal to the
  claim's. Tamper evidence is unchanged: the digest is still
  derived from content on every decision, never read from a stored
  field.
- **Generic serialization was two thirds of runtime.**
  `dataclasses.asdict` recursed through every event; the digest now
  serializes by direct field access, and a test holds the payload
  byte-identical to the generic form, because every frozen claim
  digest depends on that identity.
- **Validation paid ABC dispatch per field.** Plain int/float now
  short-circuit before the `numbers` machinery.

## What stays expensive, and why that is honest

Delegation closure stores each delegation's full spawned-event set,
because the report and its serialization promise that detail. On a
pathological trace where *every* event is a delegating tool call in
one nested chain, the total size of those sets is quadratic in the
chain length — that is the size of the *output*, and no traversal
can beat the size of its own answer. Real traces keep delegation
events sparse; measured at one delegator per fifty events, closure
over 400,000 events costs about a fifth of a second. The honest
envelope: linear in events, plus the sum of delegation subtree
sizes, which the depth cap in the default policy already bounds.

Peak memory is the harder wall than time. Evidence bundles are
in-memory Python objects, so ten million events costs tens of
gigabytes before a digest is taken. The supported answer at that
scale is sharding by window or by task cohort — decide per shard,
issue a claim per shard — not a bigger machine.
