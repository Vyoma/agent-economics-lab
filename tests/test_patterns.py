"""The synthesis cannot drift from the entries, or overreach past them.

A page that reads across eight datasets is where a registry is most likely
to start generalising: the numbers are assembled, the pattern looks clean,
and the population it came from is out of sight. These recompute every
figure from the same evidence the entries use, and hold the page to saying
what it does not establish.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "corpus"))

import patterns  # noqa: E402


class TheFiguresComeFromTheEntries(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = patterns.measure()

    def test_the_instrument_figures_match_their_entries(self) -> None:
        from audit import cogym_summary, nebius_openhands_summary

        by_name = {row["instrument"]: row for row in self.data["instruments"]}
        self.assertAlmostEqual(
            by_name["model-generated tests"]["value"],
            nebius_openhands_summary()["kappa"], places=6,
        )
        self.assertAlmostEqual(
            by_name["one person's artifact rating"]["value"],
            cogym_summary()["pairs"]["outcomeRating|agentRating"]["qwk"],
            places=6,
        )

    def test_the_absence_figures_never_exceed_their_row_counts(self) -> None:
        for row in self.data["absence"]:
            with self.subTest(dataset=row["dataset"]):
                self.assertLessEqual(row["missing"], row["rows"])
                self.assertGreaterEqual(row["missing"], 0)

    def test_the_table_spans_complete_and_empty(self) -> None:
        """The published point is the range, so the range must exist."""
        shares = [r["missing"] / r["rows"] for r in self.data["absence"]]
        self.assertEqual(min(shares), 0.0)
        self.assertEqual(max(shares), 1.0)

    def test_the_floor_matches_what_the_package_enforces(self) -> None:
        """The table's 'clears the floor' column is only meaningful if the
        floor is the one the code actually applies."""
        from agent_economics.provenance import METHOD_FLOORS

        self.assertEqual(patterns.KAPPA_FLOOR, METHOD_FLOORS["cohens-kappa"])


class ThePageRefusesToGeneralise(unittest.TestCase):
    def test_it_says_what_it_does_not_establish(self) -> None:
        page = patterns.render()
        self.assertIn("What this does not establish", page)
        for phrase in ("not a sample", "not prevalence estimates"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, page)

    def test_it_disclaims_the_ranking_reading(self) -> None:
        """Two different kinds of measurement in one table invite a ranking."""
        page = patterns.render()
        self.assertIn("should\nnot be read as a ranking", page)

    def test_the_committed_page_matches_the_renderer(self) -> None:
        committed = (ROOT / "research" / "PATTERNS.md").read_text(encoding="utf-8")
        self.assertEqual(committed, patterns.render())


if __name__ == "__main__":
    unittest.main()
