from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_economics import Decision, evaluate_bundle, load_normalized_json_bundle
from agent_economics.frontier import FrontierDecision, run_frontier


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples" / "public-swebench"


class PublicSwebenchCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.generated = Path(cls._temporary.name)
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(ROOT)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(
            [
                sys.executable,
                str(CASE / "build_case.py"),
                "--source",
                str(CASE / "runs.json"),
                "--output-dir",
                str(cls.generated),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_source_manifest_is_real_paired_and_content_free(self) -> None:
        source = json.loads((CASE / "runs.json").read_text(encoding="utf-8"))
        self.assertEqual(source["schema"], "public.swebench-paired-runs@1")
        self.assertEqual(source["license"], "MIT")
        self.assertEqual(len(source["tasks"]), 20)
        self.assertTrue(source["selection"]["outcome_blind"])
        self.assertEqual(source["selection"]["eligible_task_count"], 500)
        self.assertEqual(
            source["selection"]["eligible_task_ids_sha256"],
            "a6b0fd7c8c2969a0eef892e032250adcfa6d32362d395c246930e61b575ac9b9",
        )
        self.assertEqual(
            source["selection"]["selected_task_ids_sha256"],
            "539a7c78003458fb692ebc2213c0c55177d41af13a2d6f254cf9c828161be872",
        )
        for task in source["tasks"]:
            self.assertEqual(
                set(task["runs"]),
                {"claude-4.5-haiku-high", "claude-opus-4.6"},
            )
            for run in task["runs"].values():
                self.assertGreater(run["api_calls"], 0)
                self.assertGreater(run["instance_cost_usd"], 0)
                self.assertEqual(run["scores_resolved"], int(run["resolved"]))
                self.assertRegex(run["source_sha256"], r"^[0-9a-f]{64}$")
        rendered = json.dumps(source, sort_keys=True).lower()
        for excluded in (
            '"messages"',
            '"submission"',
            '"patch"',
            '"prompt"',
            '"reasoning"',
            '"tool_output"',
        ):
            self.assertNotIn(excluded, rendered)

    def test_checked_in_assurance_case_uses_observed_public_results(self) -> None:
        bundle = load_normalized_json_bundle(
            self.generated / "arms" / "candidate-opus.json"
        )
        case = evaluate_bundle(bundle)
        self.assertEqual(case.decision, Decision.STOP)
        self.assertEqual(len(case.tasks), 20)
        self.assertEqual(case.acceptable_rate, 0.70)
        self.assertAlmostEqual(case.total_effective_cost_usd, 8.43580275)
        self.assertAlmostEqual(case.cost_per_acceptable_outcome_usd, 0.6025573393)
        self.assertEqual(
            case.source_manifest_id,
            "source.public-swebench-mini-agent@1",
        )

    def test_paired_frontier_refuses_an_underpowered_costlier_switch(self) -> None:
        case = run_frontier(self.generated / "manifest.json")
        self.assertEqual(case.decision, FrontierDecision.HOLD)
        comparison = case.comparisons[0]
        self.assertEqual(comparison.harmful_regressions, 1)
        self.assertEqual(comparison.beneficial_changes, 4)
        self.assertEqual(comparison.acceptable_rate_delta, 0.15)
        self.assertAlmostEqual(
            comparison.mean_cost_reduction_rate,
            -0.5694702161,
        )
        self.assertGreater(comparison.breakage_rate_upper, 0.24)
        self.assertFalse(comparison.eligible)

    def test_all_derived_artifacts_are_byte_reproducible(self) -> None:
        artifacts = (
            "assurance-case.md",
            "frontier/frontier.json",
            "frontier/frontier.md",
        )
        for relative in artifacts:
            self.assertEqual(
                (self.generated / relative).read_bytes(),
                (CASE / relative).read_bytes(),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
