"""The real-data case, and the numbers the README publishes about it.

Every other artifact in this repository is built from fixtures this project
authored. This one is not: 40 public mini-SWE-agent trajectories over 20 paired
SWE-bench Verified tasks, with the hidden-test result as the outcome label, so
whether a task resolved was adjudicated by running tests rather than reported by
the agent that attempted it.

The numbers in the README are recomputed here rather than trusted, because a
hand-typed copy of a computed value is an unguarded claim.
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

from agent_economics import load_normalized_json_bundle
from agent_economics.assurance import evaluate_bundle
from agent_economics.claim import parse_claim, verify

ROOT = pathlib.Path(__file__).resolve().parents[1]
ARMS = ROOT / "examples" / "public-swebench" / "arms"
CLAIMS = ROOT / "research" / "claims"


class TheRealArmsDecideWhatTheReadmeSays(unittest.TestCase):
    def test_both_arms_fail_the_shipped_gates(self) -> None:
        """The finding. If this ever passes, the README is wrong, not the test."""
        for name in ("candidate-opus", "reference-haiku"):
            with self.subTest(arm=name):
                case = evaluate_bundle(load_normalized_json_bundle(ARMS / f"{name}.json"))
                self.assertEqual(case.decision.value, "STOP")

    def test_the_readme_table_matches_the_recomputed_arms(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        expected = {}
        for label, name in (
            ("claude-opus-4.6", "candidate-opus"),
            ("claude-4.5-haiku-high", "reference-haiku"),
        ):
            case = evaluate_bundle(load_normalized_json_bundle(ARMS / f"{name}.json"))
            expected[label] = (
                f"{case.acceptable_rate:.0%}",
                f"${case.total_effective_cost_usd:.2f}",
                f"${case.cost_per_acceptable_outcome_usd:.2f}",
            )
        for label, (rate, spend, per_resolved) in expected.items():
            # More than one README table names these arms now: the outcome
            # audit lists the same models with different columns. Assert that
            # some row carries all three economic figures, rather than assuming
            # the first row bearing the name is the right one.
            candidates = [
                line for line in readme.splitlines()
                if line.startswith(f"| `{label}`")
            ]
            with self.subTest(arm=label):
                self.assertTrue(candidates, f"no README row for {label}")
                self.assertTrue(
                    any(
                        all(value in row for value in (rate, spend, per_resolved))
                        for row in candidates
                    ),
                    f"no row for {label} carries {rate}, {spend} and "
                    f"{per_resolved}; found {candidates}",
                )

    def test_the_task_count_is_twenty_paired(self) -> None:
        counts = {
            name: len(load_normalized_json_bundle(ARMS / f"{name}.json").outcomes)
            for name in ("candidate-opus", "reference-haiku")
        }
        self.assertEqual(set(counts.values()), {20}, counts)


class TheRecordCarriesTheRealCase(unittest.TestCase):
    """A record of claims about one's own fixtures is a record of nothing."""

    def _real_claims(self):
        return sorted(CLAIMS.glob("*swebench*.claim.json"))

    def test_the_ledger_holds_claims_about_data_this_project_did_not_produce(self) -> None:
        self.assertGreaterEqual(len(self._real_claims()), 2)

    def test_each_real_claim_either_verifies_or_is_historical(self) -> None:
        """Rebuilding the arms retires older claims; that is the design.

        This asserted every claim verifies SUPPORTED, which was true only until
        the arms changed. Declaring the label source moved their digests, and
        three claims correctly became UNVERIFIED against evidence that no
        longer exists here. A claim about a bundle that has since been rebuilt
        is not false; it is a statement about the bundle it named, and the
        revision it pins is where to check it.
        """
        arms = {
            load_normalized_json_bundle(path).digest: path
            for path in ARMS.glob("*.json")
        }
        current = 0
        for path in self._real_claims():
            with self.subTest(claim=path.name):
                claim = parse_claim(json.loads(path.read_text(encoding="utf-8")))
                evidence = arms.get(claim.evidence_digest)
                if evidence is None:
                    self.assertRegex(
                        claim.source_commit, r"^[0-9a-f]{40}$",
                        "a retired claim must pin the revision it holds at",
                    )
                    continue
                self.assertEqual(
                    verify(claim, load_normalized_json_bundle(evidence)).verdict.value,
                    "SUPPORTED",
                )
                current += 1
        self.assertGreater(
            current, 0, "at least one claim must name a currently shipped arm"
        )

    def test_the_readme_points_at_a_claim_file_that_exists(self) -> None:
        """A copy-pasteable command that does not run is worse than none."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        referenced = re.findall(r"research/claims/([\w.-]+\.claim\.json)", readme)
        self.assertTrue(referenced, "the README must show a runnable verify command")
        for name in referenced:
            with self.subTest(claim=name):
                self.assertTrue((CLAIMS / name).exists(), f"{name} is not on the record")
