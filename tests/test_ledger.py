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


class TheRecordCarriesTheInvariant(unittest.TestCase):
    """The record is only worth keeping if a regression would refute it.

    Two claims saying "this fixture does not clear the gates" are safe and
    nearly unfalsifiable. The invariant claims are the opposite: each asserts
    that removing one required gate turns an otherwise-passing run into
    INCOMPLETE. Injecting the dynamic-contract fail-open this package argues
    against -- shrinking the contract to whatever the enabled checks cover --
    refutes several of them and fails the build.
    """

    def _required_gates(self) -> set[str]:
        from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE, default_checks
        return {
            spec.id
            for spec in default_checks()
            if set(spec.covers) & set(DEFAULT_REQUIRED_COVERAGE)
        }

    def test_every_required_gate_has_an_invariant_claim(self) -> None:
        """Dropping a gate's claim must not be a silent way to weaken the record."""
        claimed = set()
        for path in CLAIMS.glob("*invariant*.claim.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            present = {binding["id"] for binding in document["checks"]}
            missing = self._required_gates() - present
            claimed |= missing
        self.assertEqual(
            claimed, self._required_gates(),
            "every required gate needs a claim asserting the run goes "
            "INCOMPLETE without it",
        )

    def test_each_invariant_claim_keeps_full_coverage_and_claims_incomplete(self) -> None:
        from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE
        paths = sorted(CLAIMS.glob("*invariant*.claim.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(claim=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    set(document["required_coverage"]),
                    set(DEFAULT_REQUIRED_COVERAGE),
                    "the requirement must not depart with the gate",
                )
                self.assertEqual(document["decision"], "INCOMPLETE")

    def test_the_baseline_claim_asserts_the_run_otherwise_passes(self) -> None:
        """Without this, "removing a gate yields INCOMPLETE" could be trivially true."""
        baseline = sorted(CLAIMS.glob("*tree-baseline*.claim.json"))
        self.assertEqual(len(baseline), 1)
        document = json.loads(baseline[0].read_text(encoding="utf-8"))
        self.assertEqual(document["decision"], "SCALE")
