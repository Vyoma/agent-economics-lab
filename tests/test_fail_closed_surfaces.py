"""The auditor and the gates may not disagree on any shipped surface.

A hostile review produced the sharpest sentence anyone has written about this
package: "their own auditor refuses the evidence their own CI gate passes
green." `evaluate --ci` and the GitHub Action returned SCALE, exit 0, for a
bundle whose outcome instrument nobody had attested and whose delegation was
never declared, while `audit --ci` on the identical bundle withheld with
grounds. The reassuring answer was the default.

These tests are those two attacks, kept as regressions. Every green decision
now goes through `decide()`, which runs the audit and demotes a SCALE it
refuses to INCOMPLETE, so the only reachable exit 0 is one the audit has no
grounds against. ASSIST and STOP pass through: they are already refusals to
scale, and hiding why the evidence failed behind why it was inadmissible would
help nobody.
"""

from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_economics.cli import main  # noqa: E402

EXAMPLES = ROOT / "examples"

#: The permissive policy from the review's reproduction: every economic gate
#: clears on the bundled demo data, so only the audit stands between this
#: evidence and an exit 0.
PERMISSIVE_POLICY = {
    "human_hourly_cost_usd": 60.0,
    "min_acceptable_rate": 0.70,
    "max_cost_per_acceptable_outcome_usd": 10.0,
    "max_p95_task_cost_usd": 20.0,
    "max_trace_cost_per_task_usd": 1.0,
    "max_calls_per_task": 20,
    "min_expected_net_value_per_attempt_usd": 0.0,
    "min_incremental_net_value_vs_baseline_usd": 0.0,
    "repetition_warning_threshold": 3,
}


def _evaluate(*extra: str, policy_dir: pathlib.Path) -> tuple[int, str]:
    policy_path = policy_dir / "policy.json"
    policy_path.write_text(json.dumps(PERMISSIVE_POLICY), encoding="utf-8")
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = main(
            [
                "evaluate",
                "--traces", str(EXAMPLES / "support_trace.csv"),
                "--outcomes", str(EXAMPLES / "outcomes.csv"),
                "--rates", str(EXAMPLES / "rates.json"),
                "--baseline", str(EXAMPLES / "baseline.json"),
                "--policy", str(policy_path),
                "--ci",
                *extra,
            ]
        )
    return code, out.getvalue()


class AttackA_UnattestedInstrumentCannotScale(unittest.TestCase):
    """The review's Attack A, verbatim: judge-labelled bundle, no attestation."""

    def test_an_unattested_judge_is_incomplete_not_scale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, output = _evaluate(
                "--label-source", "judge:kimi-k3",
                policy_dir=pathlib.Path(directory),
            )
        self.assertEqual(code, 2, output)
        self.assertIn("**Decision: INCOMPLETE**", output)
        self.assertIn("audit: unattested instruments", output)

    def test_recording_no_instrument_at_all_is_also_incomplete(self) -> None:
        """Silence must not out-perform honesty about the label source."""
        with tempfile.TemporaryDirectory() as directory:
            code, output = _evaluate(policy_dir=pathlib.Path(directory))
        self.assertEqual(code, 2, output)
        self.assertIn("audit: no evidence instrument recorded", output)

    def test_a_reliability_only_attestation_still_cannot_scale(self) -> None:
        """Test-retest measures repeatability, not correctness, at 0.99 too."""
        with tempfile.TemporaryDirectory() as directory:
            attestations = pathlib.Path(directory) / "attestations.json"
            attestations.write_text(
                json.dumps(
                    {
                        "judge:kimi-k3": {
                            "method": "test-retest-agreement",
                            "agreement": 0.99,
                            "sample_size": 500,
                            "reference": "the same judge, run twice",
                            "measured_at": "2026-08-15",
                        }
                    }
                ),
                encoding="utf-8",
            )
            code, output = _evaluate(
                "--label-source", "judge:kimi-k3",
                "--attestations", str(attestations),
                "--as-of", "2026-09-01",
                policy_dir=pathlib.Path(directory),
            )
        self.assertEqual(code, 2, output)
        self.assertIn("audit: unattested instruments", output)

    def test_a_validity_attestation_reaches_scale(self) -> None:
        """The demotion is a door with a key, not a wall."""
        with tempfile.TemporaryDirectory() as directory:
            code, output = _evaluate(
                "--label-source", "fixture.manual-review",
                "--attestations", str(EXAMPLES / "attestations.json"),
                "--as-of", "2026-09-01",
                policy_dir=pathlib.Path(directory),
            )
        self.assertEqual(code, 0, output)
        self.assertIn("**Decision: SCALE**", output)

    def test_evaluate_and_audit_agree_on_the_same_bundle(self) -> None:
        """The published embarrassment, forbidden by construction: the two
        commands may never again return opposite answers for one bundle."""
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            policy_path = directory / "policy.json"
            policy_path.write_text(json.dumps(PERMISSIVE_POLICY), encoding="utf-8")
            bundle_path = directory / "bundle.json"
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(out):
                built = main(
                    [
                        "bundle",
                        "--traces", str(EXAMPLES / "support_trace.csv"),
                        "--outcomes", str(EXAMPLES / "outcomes.csv"),
                        "--rates", str(EXAMPLES / "rates.json"),
                        "--baseline", str(EXAMPLES / "baseline.json"),
                        "--policy", str(policy_path),
                        "--label-source", "judge:kimi-k3",
                        "--out", str(bundle_path),
                    ]
                )
                evaluate_code = main(
                    ["evaluate", "--bundle", str(bundle_path), "--ci"]
                )
                audit_code = main(
                    ["audit", "--bundle", str(bundle_path), "--ci"]
                )
        self.assertEqual(built, 0)
        self.assertNotEqual(
            evaluate_code, 0, "evaluate passed evidence the audit refuses"
        )
        self.assertNotEqual(audit_code, 0)


class AttackB_UndeclaredDelegationCannotScale(unittest.TestCase):
    """The review's Attack B: a Task tool spawning an undeclared child."""

    def test_an_undeclared_delegation_is_incomplete_not_scale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            traces = directory / "traces.csv"
            lines = (
                (EXAMPLES / "support_trace.csv")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            # Same evidence, one Task call spawning a child the manifest never
            # declared, expressed through the optional parent_event_id column.
            widened = [lines[0] + ",parent_event_id"]
            widened += [line + "," for line in lines[1:]]
            widened += [
                't-001,e-900,2026-07-01T10:59:00Z,tool,Task,,0,0,0.0,ok,"{}",',
                "t-001,e-901,2026-07-01T10:59:10Z,model,subtask,edge-small,"
                '900,120,0.9,ok,"{}",e-900',
            ]
            traces.write_text("\n".join(widened) + "\n", encoding="utf-8")
            policy_path = directory / "policy.json"
            policy_path.write_text(json.dumps(PERMISSIVE_POLICY), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(out):
                code = main(
                    [
                        "evaluate",
                        "--traces", str(traces),
                        "--outcomes", str(EXAMPLES / "outcomes.csv"),
                        "--rates", str(EXAMPLES / "rates.json"),
                        "--baseline", str(EXAMPLES / "baseline.json"),
                        "--policy", str(policy_path),
                        "--label-source", "fixture.manual-review",
                        "--attestations", str(EXAMPLES / "attestations.json"),
                        "--as-of", "2026-09-01",
                        "--ci",
                    ]
                )
            output = out.getvalue()
        self.assertEqual(code, 2, output)
        self.assertIn("audit: unaccounted delegation", output)


if __name__ == "__main__":
    unittest.main()
