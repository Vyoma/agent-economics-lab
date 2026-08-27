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
