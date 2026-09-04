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
        forbidden = {"messages", "test_output", "output_patch",
                     "patch", "trajectory", "problem_statement", "paths"}
        for path in sorted(FROZEN.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            rows = document.get("rows") or [
                row for group in document.get("groups", ()) for row in group["rows"]
            ]
            self.assertTrue(rows, f"{path.name}: nothing swept for content")
            for row in rows:
                with self.subTest(dataset=path.name, row=row.get("id")):
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


class PaginationNeverShadowsItsParameters(unittest.TestCase):
    """Every page after the first must request an integer length.

    The first draft assigned the response dict over the length parameter, so
    request two urlencoded a nine-megabyte page as `length=` and the server
    answered 414. The freeze died after fetching 50 of 76,002 rows.
    """

    def test_every_request_carries_the_integer_length(self) -> None:
        from unittest import mock

        import freeze

        seen = []

        def fake_get(url: str) -> dict:
            seen.append(url)
            page = len(seen) - 1
            return {
                "rows": [
                    {"row": {"i": page * 2 + n}, "truncated_cells": []}
                    for n in range(2)
                ],
                "num_rows_total": 6,
            }

        with mock.patch.object(freeze, "_get", fake_get):
            rows = freeze._rows("d", "c", "s", page_length=2)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(seen), 3)
        for url in seen:
            self.assertIn("length=2", url)


class SweSmithNumbersRecompute(unittest.TestCase):
    """Every figure in the SWE-smith entry, recomputed from frozen evidence."""

    @classmethod
    def setUpClass(cls) -> None:
        from audit import swesmith_summary

        cls.smith = swesmith_summary()

    def test_the_split_totals(self) -> None:
        self.assertEqual(self.smith["rows"], 76002)
        self.assertEqual(
            self.smith["split_rows"],
            {"swesmith-tool": 24100, "swesmith-xml": 26076, "swesmith-ticks": 25826},
        )

    def test_labels_agree_across_every_duplicate_group(self) -> None:
        self.assertEqual(self.smith["duplicate_groups"], 18167)
        self.assertEqual(self.smith["label_disagreeing_groups"], 0)

    def test_the_duplication_figures(self) -> None:
        self.assertEqual(self.smith["xml_identical_duplicate_rows"], 2255)
        self.assertEqual(self.smith["tool_xml_overlap"], 14984)

    def test_patch_emptiness_is_outcome_independent(self) -> None:
        """The gap between overall and resolved emptiness stays under a point;
        were it large, 'resolved with no patch' would be a label finding and
        the entry's dismissal of it would be wrong."""
        gap = abs(self.smith["empty_rate"] - self.smith["resolved_empty_rate"])
        self.assertLess(gap, 0.01)

    def test_the_misalignment_figures(self) -> None:
        self.assertEqual(self.smith["cross_repo_patch_groups"], 266)
        self.assertEqual(self.smith["cross_repo_patch_rows"], 1933)
        self.assertEqual(self.smith["check_nontrivial"], self.smith["check_groups"])
        self.assertEqual(self.smith["check_failures"], 0)
        self.assertGreater(self.smith["check_foreign"], 0)

    def test_the_verification_sidecar_is_internally_consistent(self) -> None:
        check = json.loads(
            (FROZEN / "swesmith-patch-check.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(check["groups"]), check["groups_checked"])
        for group in check["groups"]:
            with self.subTest(group=group["patch_sha256"][:12]):
                # every row in a group carries the same patch hash by
                # construction, so equal byte lengths are entailed
                lengths = {row["patch_bytes"] for row in group["rows"]}
                self.assertEqual(len(lengths), 1)
                repos = {row["repo"] for row in group["rows"]}
                self.assertGreater(len(repos), 1)

    def test_the_registry_refuses_a_label_disagreement(self) -> None:
        """Corrupt one duplicate row's label; the summary must not stay quiet."""
        from unittest import mock

        import audit

        real_load = audit._load

        def corrupted(slug: str) -> dict:
            document = real_load(slug)
            if slug == "swesmith-xml":
                by_hash: dict[str, int] = {}
                for row in document["rows"]:
                    h = row["transcript_sha256"]
                    if h in by_hash:
                        row["outcome"] = not row["outcome"]
                        return document
                    by_hash[h] = 1
            return document

        with mock.patch.object(audit, "_load", corrupted):
            smith = audit.swesmith_summary()
        self.assertGreater(smith["label_disagreeing_groups"], 0)


class NebiusNumbersRecompute(unittest.TestCase):
    """Entries five and six, recomputed from frozen evidence."""

    @classmethod
    def setUpClass(cls) -> None:
        from audit import nebius_openhands_summary, nebius_sweagent_summary

        cls.sweagent = nebius_sweagent_summary()
        cls.openhands = nebius_openhands_summary()

    def test_the_sweagent_clean_bill(self) -> None:
        s = self.sweagent
        self.assertEqual(s["rows"], 80036)
        self.assertEqual(s["resolved"], 13389)
        self.assertEqual(s["duplicate_transcript_groups"], 0)
        self.assertEqual(s["resolved_with_empty_patch"], 0)
        self.assertEqual(s["resolved_with_empty_logs"], 0)
        self.assertGreater(s["unresolved_empty_patch"], 9000)

    def test_the_openhands_label_coherence(self) -> None:
        o = self.openhands
        self.assertEqual(o["rows"], 67074)
        self.assertEqual(o["empty_patch_resolved"], 0)
        self.assertEqual(o["duplicate_transcript_groups"], 0)
        self.assertLess(
            o["max_iteration_resolved"] / o["max_iteration_rows"],
            o["resolved"] / o["rows"],
        )

    def test_the_generated_test_instrument_measurement(self) -> None:
        o = self.openhands
        self.assertEqual(o["cross_present"], 31389)
        self.assertAlmostEqual(o["kappa"], 0.062, places=3)
        self.assertAlmostEqual(o["valid_kappa"], 0.101, places=3)
        self.assertAlmostEqual(o["valid_precision"], 0.729, places=3)
        # the published framing depends on even the best case missing the
        # floor by a wide margin; if this ever passes 0.60 the entry is wrong
        self.assertLess(o["valid_kappa"], 0.60)

    def test_the_measurement_refuses_flipped_labels(self) -> None:
        """Corrupt the frozen cross-signal; kappa must move, proving the
        computation reads the evidence rather than echoing a constant."""
        from unittest import mock

        import audit

        real_load = audit._load

        def corrupted(slug: str) -> dict:
            document = real_load(slug)
            if slug == "nebius-openhands":
                for row in document["rows"]:
                    if row["cross"] is not None:
                        row["cross"] = 1.0 if row["outcome"] == 1 else 0.0
            return document

        with mock.patch.object(audit, "_load", corrupted):
            perfect = audit.nebius_openhands_summary()
        self.assertGreater(perfect["kappa"], 0.99)


class PostTrainBenchNumbersRecompute(unittest.TestCase):
    """Entry eight: the most-downloaded dataset, and a finding that died."""

    @classmethod
    def setUpClass(cls) -> None:
        from audit import posttrainbench_summary

        cls.ptb = posttrainbench_summary()

    def test_the_shape(self) -> None:
        self.assertEqual(self.ptb["rows"], 1842)
        self.assertEqual(self.ptb["groups"], 62)

    def test_what_carries_no_usable_outcome(self) -> None:
        p = self.ptb
        self.assertEqual(p["no_metrics_file"], 208)
        self.assertEqual(p["malformed_metrics"], 52)
        self.assertEqual(p["unusable_accuracy"], 260)
        self.assertEqual(p["unjudged"], 331)

    def test_the_judge_verdict_counts(self) -> None:
        self.assertEqual(self.ptb["judged"], 1511)
        self.assertEqual(self.ptb["contaminated"], 176)
        self.assertEqual(self.ptb["disallowed_model"], 2)

    def test_the_pooled_figure_overstates_by_an_order_of_magnitude(self) -> None:
        """The published claim is the ratio, so pin the ratio.

        If a re-freeze ever made pooled and stratified agree, the entry's
        whole argument would be wrong and this must fail rather than let the
        prose stand.
        """
        p = self.ptb
        self.assertAlmostEqual(p["pooled_difference"], 0.209, places=3)
        self.assertAlmostEqual(p["stratified_difference"], 0.018, places=3)
        self.assertGreater(p["overstatement"], 10)

    def test_the_confound_is_where_the_entry_says_it_is(self) -> None:
        p = self.ptb
        self.assertEqual(p["worst_benchmark"], "bfcl")
        self.assertGreater(p["worst_rate"], 0.35)
        self.assertGreater(p["worst_share_of_contamination"], 0.45)
        self.assertGreater(p["worst_clean_mean"], 0.6)

    def test_contamination_does_not_help_in_most_benchmarks(self) -> None:
        p = self.ptb
        self.assertLess(
            p["benchmarks_where_contamination_helps"],
            p["comparable_benchmarks"] - 1,
        )

    def test_the_stratification_is_proven_to_matter(self) -> None:
        """Non-vacuity: collapse every run onto one benchmark and the
        stratified figure must converge on the pooled one, which is the
        confound this entry exists to describe."""
        import json
        from unittest import mock

        import audit

        real = audit._load

        def flattened(slug: str) -> dict:
            document = real(slug)
            if slug == "posttrainbench":
                document = json.loads(json.dumps(document))
                for row in document["rows"]:
                    row["benchmark"] = "only"
            return document

        with mock.patch.object(audit, "_load", flattened):
            collapsed = audit.posttrainbench_summary()
        self.assertAlmostEqual(
            collapsed["stratified_difference"],
            collapsed["pooled_difference"],
            places=6,
        )
