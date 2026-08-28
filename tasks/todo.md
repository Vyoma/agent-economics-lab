# Production readiness — agent-economics-lab

Baseline at start: 157 tests, `make reproduce` green, 82% coverage, zero runtime
dependencies, fail-closed exit codes (2 on bad input).

## P0 — correctness

- [x] `agent_economics/kimi_analyst.py`: 6 undefined names in the public API.
      Fixed with a real module-level import from `.models` (no cycle: models.py
      imports only stdlib). `typing.get_type_hints()` now resolves; locked by a
      regression test.
- [x] `sensitivity_sweep.py`: removed the local re-import that shadowed
      `build_evidence`, plus unused imports and locals across all three scripts.

## P1 — guard the shipped claims

- [x] `tests/test_kimi_analyst.py`: 24 tests, network always mocked.
      Coverage 23% -> 84%.
- [x] `tests/test_research_scripts.py`: 14 tests locking the README numbers
      (588 mutations, 100% kill, 23 survivors, the per-gate breakdown, the
      ASSIST real-trace verdict, 55 brittle scenarios, 25/98 fragility).
- [x] Extracted `mutation_stats()`, `verdict_stats()`, `sweep_stats()` so those
      numbers come from testable functions, not print blocks.
- [x] `make mutation`, `make real-trace`, `make sensitivity`, all wired into
      `make reproduce` so CI executes them.

## P2 — hygiene

- [x] Ruff config in `pyproject.toml`, `make lint`, and a CI lint job.
      259 findings -> 0. Documented ignores: RUF001-003 and RUF005 (style only),
      and per-file E501 for the five terminal-report renderers.
- [x] `agent_economics.__version__` is the single source; `pyproject.toml` reads
      it dynamically; `agent-economics --version` added;
      `tests/test_packaging.py` pins it against CITATION.cff and CHANGELOG.md.
- [x] Test stdout noise: 88 lines -> 0, via a `_QuietStdout` base case.

## Found while working

- [x] `make` hardcoded `python3`. On a machine whose default is 3.9 (below the
      declared 3.10 floor) the suite silently ran on an unsupported interpreter.
      Added a `check-python` guard and a `PYTHON=` override.
- [x] Ruff's F401 autofix deleted a deliberate re-export
      (`claude_code.load_conversion_contract`, used by `__init__` and `cli`).
      Restored with the explicit redundant-alias form.
- [x] Ruff's isort split every aliased import into its own statement; fixed with
      `combine-as-imports = true`.

## Review

Result: 157 -> 202 tests, coverage 82% -> 86%, lint 259 -> 0 findings,
`make reproduce` and `make lint` both green on a clean 3.12 venv, wheel builds
and the installed console script reproduces the fixture report byte-for-byte.

Two things worth flagging:

1. A mechanical line-rewrap pass silently merged adjacent report lines in
   `kimi_analyst.py` and `frontier_report.py`. Caught by snapshotting the
   rendered text before the change and diffing after; both files were reverted
   and the fixes re-applied by hand. Final output is byte-identical across 7
   captured contexts. Lesson: never bulk-edit string literals without an
   output-equality check.
2. Local verification ran on 3.9 (rejected by the new guard) and 3.12 only.
   3.10, 3.11 and 3.13 are covered by the CI matrix, not by this session.

---

# Session 2026-08-28 — the audit's own honesty

Plan came from a 9-agent pass (5 proposers with distinct lenses, 3
cross-examiners seeing all proposals, 1 synthesizer). All three examiners
ranked the same build first; none tried to kill it. The declarative `--spec`
plane was dropped on their unanimous objection that it traded rigour for reach.

## Planned

- [x] (a) `normalized_json_document` emits `{"unsupplied": ...}` and reads it
      back, so a checks-only bundle can reach the file `audit --bundle` loads.
- [x] (b) `--attestations`, `--as-of`, `--independently-verified` on the audit
      parser, threaded into the call site.
- [x] (c) Promote "no evidence instrument recorded" from a note to a ground.
- [x] (d) `examples/checks-only/`, byte-verified, plus `make audit` inside
      `make reproduce`.
- [x] (e) Parametrized conformance test over `Unsupplied` and the metric type.
- [x] Dropped: the declarative `--spec` plane.

## Found while building, not planned

- [x] Defect 8: the audit renderer printed `$0.0000 of delegated spend` for a
      bundle declaring no rate card. Now states that the spend cannot be stated;
      JSON reports `null`.
- [x] Defect 9: cost-weighted closure summed `direct_cost_usd or 0.0` instead of
      `TraceEvent.cost`, so rate-priced events weighed nothing. $100 declared
      plus $18 undeclared reported 100% closure and $0.00 unaccounted. Now 85%
      and $18.00.
- [x] Closure raising `UnpricedDelegation` reached callers through `audit()`.
      Now converted to a withheld verdict.
- [x] A run with zero delegations rendered as "closure 100%". Now says the run
      delegated no work.

## Review

462 tests, lint clean, `make reproduce` green, 24/24 CI checks green. Decision
contract digest `e7faae0cb2b0fb62...` unchanged throughout, which is the point:
none of this altered check identity.

Both new build targets were proven to fail before being trusted — the example
gate on a tampered bundle, the audit gate on its `--ci` exit code.

## Not done, and why

- [ ] A CLI producer for checks-only traces. Needs `direct_cost_usd` itself to
      be unsuppliable: 18 reads across 7 files, and the same shape that leaked
      before when a metric subclassed `float`. The example's producer is the
      committed generator using the documented public API, which is honest but
      is not `convert`. This is the next real piece of work.

---

# Session 2026-08-28b — unpriced event cost

## What the investigation actually found

The premise in the previous entry was wrong in a useful way. `direct_cost_usd`
does not need an `Unsupplied` variant. `None` already means "not stated, derive
from the rate card", and an unsupplied rate card already refuses every read, so
the model-event path fails closed today. Two real holes remain, and one is a
regression I introduced in the closure fix.

- [x] **Regression, mine.** `delegation_closure_gate` calls `assess_closure`
      without rates, though `EvaluationView` carries them. After the defect-9
      fix, a bundle whose model events are rate-priced (`direct_cost_usd=None`)
      raises `UnpricedDelegation` inside the gate even though the rates are
      right there. 462 tests missed it: nothing exercises a rate-priced
      delegation through the gate.
- [x] **Tool events are asserted free.** `TraceEvent.cost` returns 0.0 for any
      non-model event before consulting rates. Real adapters price tool calls
      (claude_code.py:1325), so with no rate card an undeclared subagent whose
      descendants are all `WebSearch`/`WebFetch` reports `$0.00` unaccounted.
      The verdict held; the figure was invented. Same shape as defect 8.

## Design: report richly, gate strictly

Closure is cost-weighted because one subagent burning most of the run matters
more than five that return immediately. That weighting needs costs. Without
them the honest fallback is not refusal and not zero, it is a different and
weaker measurement, named as such: count the delegations.

- [x] `ClosureReport.basis` is `"cost"` or `"count"`.
- [x] Cost basis when every delegated event's cost can be established.
      Count basis otherwise, and then `delegated_cost_usd` and
      `unaccounted_cost_usd` are `None`, never `0.0`.
- [x] `delegation_closure_gate` refuses under count basis. A ratio of counts
      must never be silently compared against a threshold meaning cost. The
      report gains information; the gate keeps failing closed.
- [x] Renderer states which basis produced the number.

## Then the thing that was blocked

- [x] `convert --checks-only`: the conversion contract may omit pricing,
      baseline and policy. Events carry real token counts and state no cost.
- [x] Regenerate `examples/checks-only/` from a real session through `convert`
      rather than the bespoke build script, if that path proves sufficient.

## Success criteria

- A rate-priced delegation passes through the gate again (regression closed).
- No `$0.00` appears anywhere costs were not established.
- The count-basis gate refusal is proven, not assumed.
- `make reproduce` green, decision contract digest unchanged.

## Review

466 tests, lint clean, `make reproduce` green. All four success criteria met:
the rate-priced delegation passes the gate again, no `$0.00` appears anywhere
costs were not established, the count-basis gate refusal is proven by test, and
the decision contract digest is unchanged.

`examples/checks-only/` is now the same session as `examples/claude-code/`,
converted under a contract declaring no rate card, so the example is produced by
`convert` rather than by a bespoke script. The build script it replaced is
deleted.

Two more defects found while building, both mine, both recorded in
docs/novelty.md as 10 and 11. The tenth was introduced by the fix for the ninth,
in the same file, within the hour. Worth remembering when the fix feels obvious.

A third, caught by the loader rather than by me: `EvidenceBundle.digest` is a
stored field, so building a bundle and then `dataclasses.replace`-ing content
onto it keeps the old digest. The conversion now builds in one call. The load
path verifies the receipt digest against recomputed evidence, which is what
surfaced it.
