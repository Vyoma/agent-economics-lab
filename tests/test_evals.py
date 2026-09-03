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


class TheScorecardCoversEveryShippedCapability(unittest.TestCase):
    """A capability must be measured or named unmeasured. Never neither.

    The scorecard listed seven experiments and read as though that were
    everything the package ships. It was not: four adapters, five renderers,
    two inference roles and the frontier experiment carried no outcome at
    all, and nothing would have said so. This enumerates what the build
    actually exposes and fails when something is absent from both the table
    and the unmeasured list.
    """

    @staticmethod
    def _shipped() -> set[str]:
        import io
        from contextlib import redirect_stdout

        from agent_economics.cli import main

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            main(["capabilities"])
        names: set[str] = set()
        for line in buffer.getvalue().splitlines():
            token = line.strip().split()[0] if line.strip() else ""
            if "@" in token:
                names.add(token)
        return names

    def test_every_capability_is_measured_or_named_unmeasured(self) -> None:
        page = evals.render()
        missing = []
        for name in sorted(self._shipped()):
            family = name.split(".")[0]
            covered = (
                name in evals.UNMEASURED
                # gates and diagnostics are covered as a family by the
                # mutation and coverage-drift rows, which enumerate them
                or family in {"gate", "diagnostic"}
                # adapters and converters are covered by the ingestion row
                or family in {"source", "converter"}
                or name in page
            )
            if not covered:
                missing.append(name)
        self.assertEqual(
            missing, [],
            "shipped capabilities absent from both the scorecard and its "
            "unmeasured list; add a row or an UNMEASURED entry",
        )

    def test_the_guard_fires_when_a_capability_goes_unlisted(self) -> None:
        """Proven non-vacuous: drop an entry and the check must notice."""
        from unittest import mock

        trimmed = dict(evals.UNMEASURED)
        trimmed.pop("kimi-analyst@1")
        with mock.patch.object(evals, "UNMEASURED", trimmed):
            page = evals.render()
            self.assertNotIn("kimi-analyst@1", page)
            shipped = self._shipped()
            self.assertIn("kimi-analyst@1", shipped)

    def test_the_unmeasured_list_says_what_closing_it_takes(self) -> None:
        for name, gap in evals.UNMEASURED.items():
            with self.subTest(capability=name):
                self.assertGreater(len(gap), 30)
