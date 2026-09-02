"""The scorecard recomputes, and its guard is proven non-vacuous."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

import evals  # noqa: E402


class TheScorecardRecomputes(unittest.TestCase):
    def test_committed_page_matches_render(self) -> None:
        committed = (ROOT / "research" / "EVALS.md").read_text(encoding="utf-8")
        self.assertEqual(committed, evals.render())

    def test_every_row_keeps_its_limit_column(self) -> None:
        """A scorecard row with an empty does-not-establish cell is the
        instrument grading itself on a curve."""
        page = evals.render()
        rows = [
            line for line in page.splitlines()
            if line.startswith("| ") and not line.startswith("| question")
            and not line.startswith("|---")
        ]
        self.assertGreaterEqual(len(rows), 7)
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            with self.subTest(row=cells[0]):
                self.assertEqual(len(cells), 4)
                self.assertGreater(len(cells[3]), 20)

    def test_the_headline_pattern_guard_fires_on_drift(self) -> None:
        """If PROBE_RESULTS.md's headline moves, render() must refuse loudly
        rather than publish a scorecard missing the prospective row."""
        from unittest import mock

        real_read_text = pathlib.Path.read_text

        def doctored(self, *args, **kwargs):
            text = real_read_text(self, *args, **kwargs)
            if self.name == "PROBE_RESULTS.md":
                return text.replace("divergences probed", "divergences examined")
            return text

        with mock.patch.object(pathlib.Path, "read_text", doctored), \
                self.assertRaises(AssertionError):
            evals.render()


if __name__ == "__main__":
    unittest.main()
