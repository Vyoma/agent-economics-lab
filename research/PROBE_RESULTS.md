# Results of the pre-registered search

The site list in [PROBE_SITES.md](PROBE_SITES.md) was committed in `552323b`,
before any probe was written. This is what probing it found, including what it
did not.

## Headline

**18 divergences probed. 3 real defects, at 3 distinct sites.**

That count went 3, then 2, then 3 again, and the movement is the point. It was
first published as 3 by counting a crash the detector never pointed at. An
adversarial review removed that one, correctly, leaving 2. A second review then
found a real fail-open at site #16 -- a site this file had published as
*probed and correct*. The probe was run and got the wrong answer, which is
worse than not probing.

2/18 of the pre-registered entries, or 2/13 counted as distinct sites, since
divergences #10-14 name one site and #3-5 are three parameters of one call.

A previous version of this file said three defects and "roughly one site in
eight". Both were wrong, and they were wrong in the direction that flattered
the method. F3 below was never a live defect and the detector never pointed at
it. "One site in eight" is 12.5%, which is not 2/18, not 3/18, and not 2/13; it
was derivable from nothing.

## The three

### F1 — the CSV evidence path could not see delegation at all

`load_csv_bundle` never passed `dependency_edges`, and the CSV schema had no
column able to carry them. A trace with two `Agent` calls and $500 of subagent
spend reported **zero delegations, 100% closure, and the gate passed** saying
"no delegation in this run".

This is the largest defect found in this repository. It is a fail-open on the
headline mechanism, on a documented input path, and it was structural rather
than a slip: the format could not express the thing, so the absence of the thing
was reported as fact.

Two fixes, because either alone is insufficient. The schema gained an optional
`parent_event_id` column, so delegation is expressible. And a call to a known
delegation tool that spawned no recorded work is now refused rather than
counted as no delegation, because "nothing was delegated" and "the graph was not
captured" are different claims and this evidence cannot tell them apart.

Found by divergence #10-14: `make_evidence_bundle` called without
`dependency_edges` at `io.py:122` while three other callers passed it.

### F4 — blank token columns priced at $0.00, at a site published as clean

`load_csv_bundle` goes through `validate_evidence_bundle` without
`require_explicit_costs`, so a model event with no stated cost and no recorded
token usage was priced against the rate card at $0.00. `gate.unit-economics`
then passed on `cost_per_acceptable_outcome $0.00 <= $2.00`: a cost gate
clearing on spend nobody established.

The guard already existed and already fired; it was opt-in, and the three
adapters opted in while the documented CSV path did not. It is now
unconditional, because a model event with no cost and no usage has an
unestablished cost on every path.

This is divergence #16, which the table below originally recorded as *probed,
correct*. The probe used a bundle whose events carried explicit costs, so the
guard had nothing to catch and the site looked clean. A probe that cannot
observe the defect it is aimed at reports a miss and looks like diligence.

### F2 — the audit reported no grounds where the gate refused

`evidence_provenance_gate` never accepted `independently_verified`, so the
sole-provider carve-out was reachable from `audit()` and from `assess_provenance`
but not from the gate. On a corroborated instrument the audit reported
`assessable=True, grounds=()` and the gate then raised `UnattestedInstrument`.

It errs safe, so it is not a fail-open. It is still a defect: the audit is read
as a prediction of what enforcement will do, and it was not one.

Found by divergence #9.

### Not-a-finding — the success path crash that was never reachable

This was published as a third finding. It is not one.

An instrument's `agreement` is unset only when it is in `corroborated`, and
`corroborated` derives solely from `independently_verified`, which the gate
never passed before the F2 fix. So `{s.agreement:.2f}` could not be reached with
a `None`. It was dead code that fixing F2 animated, found by running the code
rather than by the method, and it was never live in any commit.

It does illustrate shape **S2** from the pre-registration. It does not count,
and counting it inflated the hit rate by half.

## The eleven sites that found nothing

| # | divergence | verdict | how |
|---|---|---|---|
| 1 | `_inspect_claude_code_jsonl_bytes(allow_empty_tasks=)` | correct | inspection |
| 2 | `_normalize_usage(allow_zero=)` | correct | inspection |
| 3 | `_numeric_issue(integer=)` | correct | inspection |
| 4 | `_numeric_issue(maximum=)` | correct | inspection |
| 5 | `_numeric_issue(minimum=)` | correct | inspection |
| 6 | `_result(task_id=)` | correct | inspection |
| 7 | `assert_mfjs_compatible(path=)` | correct | inspection |
| 8 | `assess_bundle_closure(declared=)` | correct | inspection |
| 15 | `validate_evidence_bundle(label=)` | correct | inspection |
| ~~16~~ | `validate_evidence_bundle(require_explicit_costs=)` | **DEFECT (F4)** | probed wrongly, then re-probed |
| 17 | `validate_evidence_bundle(require_task_manifest=)` | correct | **probed** |
| 18 | `direct_cost_usd` read raw vs `.cost()` | correct | inspection |

Counted as sites rather than pre-registration entries: **13 sites, 3 defective,
10 clean.** The heading of this table previously said sixteen while the table
held twelve rows.

Two were settled by running a probe. Ten were settled by reading the code, which
is weaker evidence and is marked as such. A reader who thinks one of those ten
deserves a probe is probably right; the ones left unprobed are the ones that
looked obviously intentional, and "looked obviously fine" is exactly the
property every defect in the retrospective corpus also had.

## The detector after the fixes

Regenerating the site list against the repaired code drops the divergence count
from 18 to 17. Only the provenance one disappeared: `io.py:122` now passes
`dependency_edges`, but `assurance.py:524` still omits it, so the divergence
correctly still points somewhere.

That remaining site is `evaluate()`, a compatibility wrapper with the same
inability to express a graph that produced F1. Probed: the default engine does
not run the closure gate, so nothing there consumes the edges, and any consumer
that does compose the gate hits the F1 refusal for delegation tools with no
recorded work. **Mitigated by F1, not a separate defect** — the same fix covers
both sites, which is the outcome you want from a structural repair and not one
that was designed for.

A detector whose count falls only when the underlying condition is actually
resolved is more useful than one that goes quiet when a symptom is patched.
This one kept pointing.

## What this changes about the claim

The retrospective corpus establishes that green defects exist and shows their
mechanism. It cannot report a hit rate, because suspicion found those five, not
a method.

This run can. The method was fixed and published first, the target list was
committed before probing, and the misses are counted. Three defects, one of them
the largest in the repository, from a list produced mechanically by a rule
abstracted from earlier defects.

The honest reading is narrow. One repository, one author, 18 divergences. It
does not establish that divergence-hunting generalises, and a rule derived from
five defects and then evaluated on the same codebase is fitted to its own
training set in a way no held-out claim survives. What it does establish is that
the rule produced novel true positives rather than only re-describing what was
already known, which is the minimum a method has to clear to be worth anything.
