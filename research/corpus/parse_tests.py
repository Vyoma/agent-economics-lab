"""Parse test-runner logs into per-test statuses, refusing what it cannot read.

The first draft of the corpus auditor parsed only pytest's `PASSED path::test`
lines and re-adjudicated 500 published labels against them. It reported 186
disagreements. All 186 were Django instances, whose runner prints
`test_x (module.Class) ... ok` instead, and every "failing" graded test was
simply absent from the parse. The instrument was about to publish a finding
that was entirely its own blindness.

The rule that came out of that: a graded test the parser cannot locate makes
the row UNPARSED, never a disagreement. Absence of evidence from a parser is
evidence about the parser.

Three formats are handled: pytest verbose lines, the unittest/Django runner,
and sympy's own runner.
Django's runner prints a test's docstring first line instead of its name when
one exists, which is why SWE-bench graded-test ids sometimes read as prose
("Migration directories without an __init__.py file are loaded."); the
unittest pattern captures both spellings. Formats beyond these leave rows
UNPARSED and counted, not guessed at.
"""

from __future__ import annotations

import re

#: `PASSED astropy/modeling/tests/test_separable.py::test_custom_model_separable`
_PYTEST = re.compile(
    r"^(PASSED|FAILED|ERROR|XFAIL|XPASS|SKIPPED)(?:\s+\[[^\]]+\])?\s+(\S+)",
    re.M,
)

#: `test_basic (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase) ... ok`
#: `Migration directories without an __init__.py file are loaded. ... ok`
_UNITTEST = re.compile(
    r"^(.+?) \.\.\. (ok|OK|FAIL|FAILED|ERROR|skipped.*|expected failure)\s*$",
    re.M,
)

#: sympy's own runner: `test_point E` / `test_point3D ok`, one line per test.
#: Only the five statuses whose meaning is certain are mapped; an unmapped
#: status leaves the test unlocated, which fails the row closed to UNPARSED.
_SYMPY = re.compile(r"^(test_\S+)\s+(ok|E|F|f|s)\s*$", re.M)

_SYMPY_STATUS = {"ok": "PASSED", "E": "ERROR", "F": "FAILED", "f": "XFAIL", "s": "SKIPPED"}

#: The failure-detail header the unittest runner prints after the run:
#: `FAIL: test_x (module.Class)`. Redundant with the `... FAIL` line when that
#: line parsed, load-bearing when interleaved stderr corrupted it.
_UNITTEST_HEADER = re.compile(r"^(FAIL|ERROR): (test\S+(?: \([^)]+\))?)\s*$", re.M)

_STATUS = {
    "ok": "PASSED",
    "OK": "PASSED",
    "FAIL": "FAILED",
    "FAILED": "FAILED",
    "ERROR": "ERROR",
    "expected failure": "XFAIL",
}


def parse_statuses(log: str) -> dict[str, str]:
    """Every test the log names, mapped to the last status it reports for it."""
    statuses: dict[str, str] = {}
    for match in _PYTEST.finditer(log):
        statuses[match.group(2)] = match.group(1)
    for match in _UNITTEST.finditer(log):
        raw = match.group(2)
        status = _STATUS.get(raw, "SKIPPED" if raw.startswith("skipped") else raw)
        statuses[match.group(1).strip()] = status
    for match in _SYMPY.finditer(log):
        statuses[match.group(1)] = _SYMPY_STATUS[match.group(2)]
    for match in _UNITTEST_HEADER.finditer(log):
        statuses[match.group(2).strip()] = _STATUS[match.group(1)]
    return statuses


#: Strict counts only an outright pass. Lenient additionally accepts XFAIL,
#: which some harness versions grade as passing. A row is only a disagreement
#: when both readings disagree with the published label; when the readings
#: split, the row is AMBIGUOUS and excluded, because a disagreement that
#: depends on a grading convention is a convention dispute, not a finding.
_STRICT_PASS = frozenset({"PASSED"})
_LENIENT_PASS = frozenset({"PASSED", "XFAIL"})


def grade(
    statuses: dict[str, str], graded: list[str], passing: frozenset[str]
) -> tuple[list[str], list[str]]:
    """(tests that failed, tests the parser never located) among `graded`."""
    bad = [t for t in graded if t in statuses and statuses[t] not in passing]
    unlocated = [t for t in graded if t not in statuses]
    return bad, unlocated


def readjudicate(log: str, f2p: list[str], p2p: list[str]) -> dict:
    """Re-derive resolution from the raw log, or refuse.

    verdict is one of:
      RESOLVED / UNRESOLVED — both grading conventions agree.
      AMBIGUOUS             — the conventions disagree; excluded downstream.
      UNPARSED              — a graded test never appeared in the log.
    """
    statuses = parse_statuses(log)
    unlocated = [t for t in f2p + p2p if t not in statuses]
    if unlocated:
        return {
            "verdict": "UNPARSED",
            "unlocated_n": len(unlocated),
            "unlocated_sample": unlocated[:10],
        }
    verdicts = {}
    detail = {}
    for name, passing in (("strict", _STRICT_PASS), ("lenient", _LENIENT_PASS)):
        f2p_bad, _ = grade(statuses, f2p, passing)
        p2p_bad, _ = grade(statuses, p2p, passing)
        verdicts[name] = not f2p_bad and not p2p_bad
        detail[name] = {
            "f2p_bad_n": len(f2p_bad),
            "p2p_bad_n": len(p2p_bad),
            "f2p_bad_sample": f2p_bad[:10],
            "p2p_bad_sample": p2p_bad[:10],
        }
    if verdicts["strict"] != verdicts["lenient"]:
        verdict = "AMBIGUOUS"
    else:
        verdict = "RESOLVED" if verdicts["strict"] else "UNRESOLVED"
    return {"verdict": verdict, **detail}
