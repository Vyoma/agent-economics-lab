"""The green-defect corpus, and the published claim that rests on it.

The claim is that every catalogued defect was live at a commit where the whole
suite passed. It is checked by `make green-defects`, which checks out those
commits and runs them. These tests guard the shape of the artifact and the
numbers quoted from it, so a stale figure fails rather than drifts.
"""

from __future__ import annotations

import pathlib
import re
import unittest

from research.green_defects import DEFECTS

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "research" / "GREEN_DEFECTS.md"


class TheCorpusIsWellFormed(unittest.TestCase):
    def test_every_defect_states_why_no_test_expressed_it(self) -> None:
        """The invisibility field is the contribution. An empty one is a gap."""
        for defect in DEFECTS:
            with self.subTest(defect=defect.id):
                self.assertGreater(len(defect.invisibility), 60)
                self.assertGreater(len(defect.mechanism), 60)

    def test_ids_are_unique(self) -> None:
        ids = [d.id for d in DEFECTS]
        self.assertEqual(len(ids), len(set(ids)))


class ThePublishedNumbersMatchTheReport(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(REPORT.exists(), "run `make green-defects`")
        self.text = REPORT.read_text(encoding="utf-8")

    def test_every_defect_appears(self) -> None:
        for defect in DEFECTS:
            with self.subTest(defect=defect.id):
                self.assertIn(defect.id, self.text)

    def test_the_headline_counts_the_whole_corpus(self) -> None:
        match = re.search(
            r"\*\*(\d+) of (\d+) defects were live at a commit where the "
            r"entire suite passed\*\*, across ([\d,]+) passing tests",
            self.text,
        )
        self.assertIsNotNone(match, "headline sentence missing or reworded")
        green, total, tests = match.groups()
        self.assertEqual(int(total), len(DEFECTS))
        self.assertEqual(
            int(green), len(DEFECTS),
            "a defect was live at a commit whose suite was red; the corpus "
            "claim does not hold for it and the entry must be removed or "
            "the claim narrowed",
        )
        self.assertGreater(int(tests.replace(",", "")), 2000)

    def test_every_probe_discriminated(self) -> None:
        """A probe that reports the same thing before and after found nothing."""
        pairs = re.findall(
            r"- while live: `(.+?)`\n  - after the fix: `(.+?)`", self.text
        )
        self.assertEqual(len(pairs), len(DEFECTS))
        for live, fixed in pairs:
            with self.subTest(live=live[:40]):
                self.assertNotEqual(live, fixed)

    def test_the_readme_table_matches_the_generated_report(self) -> None:
        """A hand-typed copy of a computed value is an unguarded claim.

        The README quotes each defect's commit and the suite size there. Those
        come from `make green-defects`; this asserts the copy did not drift.
        """
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        rows = re.findall(
            r"^\| (?:the |a |rate-priced |tool )[^|]+\| `([0-9a-f]{7})` \| (\d+) \|",
            readme, re.MULTILINE,
        )
        self.assertEqual(
            len(rows), len(DEFECTS), "README table lost or gained a row"
        )
        for commit, tests in rows:
            with self.subTest(commit=commit):
                self.assertIn(
                    f"`{commit}` | {tests} |", self.text,
                    f"README claims {tests} tests at {commit}; the generated "
                    "report disagrees",
                )
        # The distinct suite total, not the column sum. The five defects sit at
        # three commits, so summing the column double-counted two of them and
        # published 2275 where the distinct figure is 1365.
        self.assertIn("1365 tests", readme)
        # 2275 may appear only where the README says it was wrong, never as the
        # figure itself. A correction that erases the corrected number hides
        # that anything was corrected.
        for line in readme.splitlines():
            if "2275" in line:
                self.assertIn("not the 2275", line)

    def test_the_population_limit_is_stated(self) -> None:
        """A case series presented as a rate would be the thing this repo is against."""
        self.assertIn("case series, not a rate", self.text)


if __name__ == "__main__":
    unittest.main()
