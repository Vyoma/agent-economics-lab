# Results of the pre-registered search

The site list in [PROBE_SITES.md](PROBE_SITES.md) was committed in `552323b`,
before any probe was written. This is what probing it found, including what it
did not.

## Headline

**18 divergences probed. 3 real defects, at 2 distinct sites. 16 found nothing.**

A hit rate of roughly one site in eight. That is not a good detector. It is a
detector that works, which is a different and lower bar, and it is reported with
its denominator so the difference stays visible.

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

### F2 — the audit reported no grounds where the gate refused

`evidence_provenance_gate` never accepted `independently_verified`, so the
sole-provider carve-out was reachable from `audit()` and from `assess_provenance`
but not from the gate. On a corroborated instrument the audit reported
`assessable=True, grounds=()` and the gate then raised `UnattestedInstrument`.

It errs safe, so it is not a fail-open. It is still a defect: the audit is read
as a prediction of what enforcement will do, and it was not one.

Found by divergence #9.

### F3 — the success path crashed on the case the carve-out exists for

Fixing F2 exposed it immediately. An instrument exempted as not-sole-provider
has no agreement figure, because nothing attested it. The gate's success summary
formatted `{s.agreement:.2f}` unconditionally and raised `TypeError`.

This is shape **S2** from the pre-registration, "formatted number with no check
that it is known" — the shape dismissed as too coarse at 123 sites. It was too
coarse to enumerate usefully. It was not wrong.

## The sixteen that found nothing

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
| 16 | `validate_evidence_bundle(require_explicit_costs=)` | correct | **probed** |
| 17 | `validate_evidence_bundle(require_task_manifest=)` | correct | **probed** |
| 18 | `direct_cost_usd` read raw vs `.cost()` | correct | inspection |

Twelve rows, not sixteen, because divergences #10-14 are five entries naming one
site and #3-5 are three parameters of one call. Counted as sites rather than
entries: **13 sites, 2 defective**.

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
