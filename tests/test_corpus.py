"""The corpus auditor: the parser refuses what it cannot read, the registry
cannot drift from the frozen evidence, and the published counts recompute.

The load-bearing property is fail-closed parsing. The first draft of the
re-adjudicator parsed only pytest's format and reported 186 disagreements on
Django rows, every one of which was the parser's own blindness. These tests
feed each supported format, then a format the parser does not know, and
require UNPARSED rather than a verdict.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "corpus"))

from audit import (  # noqa: E402
    FROZEN,
    degenerate_positives,
    duplicate_groups,
    outcome_census,
    readjudication,
    render,
)
from parse_tests import parse_statuses, readjudicate  # noqa: E402

PYTEST_LOG = """\
PASSED astropy/modeling/tests/test_separable.py::test_custom_model_separable
FAILED astropy/modeling/tests/test_separable.py::test_coord_matrix - boom
============ 1 failed, 1 passed in 0.29s ============
"""

DJANGO_LOG = """\
test_basic (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase) ... ok
Migration directories without an __init__.py file are loaded. ... ok
test_accent (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase) ... FAIL
test_column (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase) ... skipped 'no pg'
======================================================================
FAIL: test_accent (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)
----------------------------------------------------------------------
Ran 4 tests in 0.01s
"""

SYMPY_LOG = """\
test_point E
test_point3D ok
test_transform f
=========== tests finished: 1 passed, 1 exceptions, in 0.32 seconds ============
"""


class ParserReadsEachFormat(unittest.TestCase):
    def test_pytest_lines(self) -> None:
        statuses = parse_statuses(PYTEST_LOG)
        self.assertEqual(
            statuses["astropy/modeling/tests/test_separable.py::test_custom_model_separable"],
            "PASSED",
        )
        self.assertEqual(
            statuses["astropy/modeling/tests/test_separable.py::test_coord_matrix"],
            "FAILED",
        )

    def test_django_lines_including_docstring_names(self) -> None:
        statuses = parse_statuses(DJANGO_LOG)
        self.assertEqual(
            statuses["test_basic (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
            "PASSED",
        )
        self.assertEqual(
            statuses["Migration directories without an __init__.py file are loaded."],
            "PASSED",
        )
        self.assertEqual(
            statuses["test_accent (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
            "FAILED",
        )
        self.assertEqual(
            statuses["test_column (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
            "SKIPPED",
        )

    def test_sympy_lines(self) -> None:
        statuses = parse_statuses(SYMPY_LOG)
        self.assertEqual(statuses["test_point"], "ERROR")
        self.assertEqual(statuses["test_point3D"], "PASSED")
        self.assertEqual(statuses["test_transform"], "XFAIL")

    def test_a_traceback_line_is_not_a_status(self) -> None:
        log = '  File "/testbed/sympy/core/mul.py", line 1296, in _eval_is_prime\n'
        self.assertEqual(parse_statuses(log), {})


class ReadjudicationFailsClosed(unittest.TestCase):
    """A graded test the parser cannot locate is UNPARSED, never a verdict."""

    def test_resolved_when_every_graded_test_passes(self) -> None:
        verdict = readjudicate(
            DJANGO_LOG,
            ["Migration directories without an __init__.py file are loaded."],
            ["test_basic (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
        )
        self.assertEqual(verdict["verdict"], "RESOLVED")

    def test_unresolved_when_a_graded_test_fails(self) -> None:
        verdict = readjudicate(
            DJANGO_LOG,
            ["test_accent (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
            [],
        )
        self.assertEqual(verdict["verdict"], "UNRESOLVED")
        self.assertEqual(verdict["strict"]["f2p_bad_n"], 1)

    def test_the_186_false_positive_shape_is_unparsed(self) -> None:
        """Django-graded tests against a log in a format the parser missed."""
        verdict = readjudicate(
            "some runner format nobody wrote a parser for\n",
            ["test_accent (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
            [],
        )
        self.assertEqual(verdict["verdict"], "UNPARSED")
        self.assertEqual(verdict["unlocated_n"], 1)

    def test_one_unlocated_graded_test_poisons_the_whole_row(self) -> None:
        verdict = readjudicate(
            DJANGO_LOG,
            ["test_basic (dbshell.test_postgresql.PostgreSqlDbshellCommandTestCase)"],
            ["test_never_ran (module.Class)"],
        )
        self.assertEqual(verdict["verdict"], "UNPARSED")

    def test_a_convention_dependent_row_is_ambiguous_not_a_finding(self) -> None:
        verdict = readjudicate(SYMPY_LOG, ["test_transform"], ["test_point3D"])
        self.assertEqual(verdict["verdict"], "AMBIGUOUS")


class ChecksRecomputeFromSyntheticEvidence(unittest.TestCase):
    def _document(self, rows: list[dict]) -> dict:
        return {"rows": rows}

    def test_duplicate_groups_report_label_disagreement(self) -> None:
        rows = [
            {"id": "a", "outcome": True, "transcript_sha256": "x"},
            {"id": "b", "outcome": False, "transcript_sha256": "x"},
            {"id": "c", "outcome": True, "transcript_sha256": "y"},
        ]
        groups = duplicate_groups(self._document(rows))
        self.assertEqual(len(groups), 1)
        self.assertFalse(groups[0]["labels_agree"])

    def test_degenerate_positives_catch_the_one_call_resolution(self) -> None:
        rows = [
            {"id": "a", "outcome": True, "steps": 1, "transcript_sha256": "x"},
            {"id": "b", "outcome": True, "steps": 40, "transcript_sha256": "y"},
            {"id": "c", "outcome": False, "steps": 1, "transcript_sha256": "z"},
        ]
        self.assertEqual(degenerate_positives(self._document(rows)), ["a"])

    def test_outcome_census_distinguishes_null_from_false(self) -> None:
        rows = [
            {"id": "a", "outcome": None, "transcript_sha256": "x"},
            {"id": "b", "outcome": False, "transcript_sha256": "y"},
        ]
        census = outcome_census(self._document(rows))
        self.assertEqual(census["null"], 1)
        self.assertEqual(census["false"], 1)


class FrozenEvidenceMatchesThePublishedRegistry(unittest.TestCase):
    """The committed CORPUS.md is exactly what the frozen evidence renders."""

    def test_registry_is_regenerated_from_evidence(self) -> None:
        committed = (ROOT / "research" / "CORPUS.md").read_text(encoding="utf-8")
        self.assertEqual(committed, render())

    def test_coderforge_clean_bill_recomputes(self) -> None:
        document = json.loads((FROZEN / "coderforge.json").read_text(encoding="utf-8"))
        summary = readjudication(document)
        self.assertEqual(summary["disagreements"], [])
        self.assertGreater(summary["parsed"], 400)
        self.assertEqual(len(document["rows"]), 500)
        self.assertEqual(
            summary["parsed"]
            + summary["verdicts"].get("UNPARSED", 0)
            + summary["verdicts"].get("AMBIGUOUS", 0),
            500,
        )

    def test_jetbrains_outcome_is_null_on_every_row(self) -> None:
        document = json.loads((FROZEN / "jetbrains.json").read_text(encoding="utf-8"))
        census = outcome_census(document)
        self.assertEqual(census, {"null": 1785})

    def test_frozen_rows_are_content_free(self) -> None:
        """No messages, prompts, patches, or logs may ever be committed."""
        for path in sorted(FROZEN.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            for row in document["rows"]:
                with self.subTest(dataset=path.name, row=row.get("id")):
                    forbidden = {"messages", "test_output", "output_patch",
                                 "patch", "trajectory", "problem_statement"}
                    self.assertFalse(forbidden & set(row))

    def test_registry_leads_every_entry_with_provenance(self) -> None:
        text = (ROOT / "research" / "CORPUS.md").read_text(encoding="utf-8")
        table = text.index("| dataset |")
        self.assertIn("independent public upload", text[:table])
        self.assertIn("not a number any", text[:table])


class TheGuardActuallyGuards(unittest.TestCase):
    """render() must refuse a stale clean bill when the evidence gains a finding.

    Written by deliberately corrupting the evidence, because this repository
    has shipped a guard that passed with the defect restored.
    """

    def test_render_refuses_when_a_duplicate_appears(self) -> None:
        document = json.loads((FROZEN / "coderforge.json").read_text(encoding="utf-8"))
        document["rows"][1]["transcript_sha256"] = document["rows"][0]["transcript_sha256"]
        script = (
            "import json, sys; sys.path.insert(0, 'research/corpus'); import audit;"
            "audit._load = lambda slug, _d=json.loads(sys.stdin.read()): ("
            "_d if slug == 'coderforge' else "
            "json.loads((audit.FROZEN / (slug + '.json')).read_text()));"
            "audit.render()"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps(document),
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("rewrite its entry", proc.stderr)


if __name__ == "__main__":
    unittest.main()
