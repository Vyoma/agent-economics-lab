"""The claim ledger, and the rule that gives it teeth.

A record of claims strangers checked is the only asset here that cannot be
copied by reading it, and it only exists if it accumulates. The first version
overwrote two files on every reissue, so the record was permanently two current
claims with the history visible only in git, where no reader looks.

The rule: REFUTED is a build failure, forever. UNVERIFIED against today's code
is acceptable for a historical claim, provided it pinned a revision a reader can
check it against. A claim that stopped reproducing because a gate was
refactored is not a claim that was wrong.
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

from research.ledger import _entries, check, render

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "research" / "claims"
LEDGER = CLAIMS / "LEDGER.md"


class TheRecordAccumulates(unittest.TestCase):
    def test_claim_filenames_carry_a_date_and_a_revision(self) -> None:
        """Append-only depends on the name being unique per issuance."""
        files = sorted(CLAIMS.glob("*.claim.json"))
        self.assertTrue(files, "the ledger must hold at least one claim")
        for path in files:
            with self.subTest(claim=path.name):
                self.assertRegex(
                    path.name,
                    r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+-[0-9a-f]{8}\.claim\.json$",
                )

    def test_no_two_claims_share_a_filename(self) -> None:
        """Append-only is a naming property before it is anything else."""
        names = [path.name for path in CLAIMS.glob("*.claim.json")]
        self.assertEqual(sorted(names), sorted(set(names)))

    def test_every_claim_pins_a_revision(self) -> None:
        for path in sorted(CLAIMS.glob("*.claim.json")):
            with self.subTest(claim=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertRegex(document["source_commit"], r"^[0-9a-f]{40}$")


class NothingFalseSurvivesOnTheRecord(unittest.TestCase):
    def test_the_current_ledger_has_no_problems(self) -> None:
        self.assertEqual(check(_entries()), [])

    def test_a_refuted_claim_is_a_build_failure(self) -> None:
        problems = check([
            {"file": "x.claim.json", "verdict": "REFUTED", "source_commit": "a" * 40},
        ])
        self.assertEqual(len(problems), 1)
        self.assertIn("falsehood on the record", problems[0])

    def test_an_unverified_claim_that_pins_a_revision_is_allowed(self) -> None:
        """Refactoring a gate must not turn the record into a liability."""
        self.assertEqual(
            check([{
                "file": "x.claim.json", "verdict": "UNVERIFIED",
                "source_commit": "a" * 40,
            }]),
            [],
        )

    def test_an_unverified_claim_pinning_nothing_is_a_build_failure(self) -> None:
        problems = check([
            {"file": "x.claim.json", "verdict": "UNVERIFIED", "source_commit": ""},
        ])
        self.assertEqual(len(problems), 1)
        self.assertIn("nothing a reader could check it against", problems[0])

    def test_a_malformed_claim_is_a_build_failure(self) -> None:
        problems = check([{"file": "x.claim.json", "verdict": "MALFORMED"}])
        self.assertEqual(len(problems), 1)


class ThePublishedLedgerIsCurrent(unittest.TestCase):
    def test_the_committed_page_matches_what_regenerates(self) -> None:
        # `main` prints, so the file carries one trailing newline render omits.
        self.assertEqual(
            LEDGER.read_text(encoding="utf-8"), render(_entries()) + "\n",
            "run `make ledger` after issuing a claim",
        )

    def test_the_headline_count_matches_the_files(self) -> None:
        text = LEDGER.read_text(encoding="utf-8")
        match = re.search(r"\*\*(\d+) claims on the record", text)
        self.assertIsNotNone(match)
        self.assertEqual(
            int(match.group(1)), len(list(CLAIMS.glob("*.claim.json")))
        )


if __name__ == "__main__":
    unittest.main()
