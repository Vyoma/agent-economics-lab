"""The path a stranger walks from their own evidence to a verifiable claim.

A record with one issuer is not a record. Until now the only way to obtain a
bundle -- which `claim`, `audit` and `verify` all require -- was one of three
adapters, so anyone holding ordinary CSV evidence could evaluate it and never
publish a claim about it. That is friction that keeps a record single-issuer,
and it is the kind that is invisible from inside the project.

This walks the whole path in one test, as an outsider would: CSV in, verified
claim out, issued under a name that is not this project's.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from agent_economics.cli import main

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

TRACES = (
    "task_id,event_id,timestamp,event_type,name,model,"
    "input_tokens,output_tokens,direct_cost_usd\n"
    "t1,e1,2026-07-01T10:00:00Z,model,answer,frontier-large,1200,300,\n"
    "t2,e2,2026-07-01T10:01:00Z,model,answer,frontier-large,900,250,\n"
)
# Every economic column is declared: an outcomes file silent about
# incident loss has not said there was none, and the loader refuses it.
OUTCOMES = (
    "task_id,acceptable,business_value_usd,human_minutes,remediation_cost_usd,incident_loss_usd\n"
    "t1,true,10,,,\n"
    "t2,false,0,45,120,1200\n"
)


def _run(argv: list[str]) -> tuple[int, str]:
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue() + err.getvalue()


class AStrangerCanPublishAClaim(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = pathlib.Path(tempfile.mkdtemp())
        (self.dir / "traces.csv").write_text(TRACES, encoding="utf-8")
        (self.dir / "outcomes.csv").write_text(OUTCOMES, encoding="utf-8")
        for name in ("rates.json", "baseline.json", "policy.json"):
            shutil.copy(EXAMPLES / name, self.dir / name)

    def _bundle(self, *extra: str) -> tuple[int, str]:
        return _run([
            "bundle",
            "--traces", str(self.dir / "traces.csv"),
            "--outcomes", str(self.dir / "outcomes.csv"),
            "--rates", str(self.dir / "rates.json"),
            "--baseline", str(self.dir / "baseline.json"),
            "--policy", str(self.dir / "policy.json"),
            "--out", str(self.dir / "bundle.json"),
            *extra,
        ])

    def test_csv_evidence_becomes_a_bundle(self) -> None:
        code, _ = self._bundle("--label-source", "my-team.manual-review@v1")
        self.assertEqual(code, 0)
        document = json.loads((self.dir / "bundle.json").read_text())
        self.assertEqual(document["label_source"], "my-team.manual-review@v1")

    def test_the_whole_path_ends_in_a_supported_verdict(self) -> None:
        self.assertEqual(self._bundle("--label-source", "my-team.rubric@1")[0], 0)
        claim = self.dir / "my.claim.json"
        code, _ = _run([
            "claim", "--bundle", str(self.dir / "bundle.json"),
            "--assertion", "Our two tasks do not clear the gates.",
            "--issuer", "some-other-team",
            "--source-commit", "0" * 40,
            "--output", str(claim),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(claim.read_text())["issuer"], "some-other-team",
            "a claim must be attributable to whoever issued it",
        )
        code, text = _run([
            "verify", "--claim", str(claim),
            "--bundle", str(self.dir / "bundle.json"),
        ])
        self.assertEqual(code, 0, text)
        self.assertIn("SUPPORTED", text)

    def test_the_claim_is_refuted_against_different_evidence(self) -> None:
        """The path must produce something falsifiable, not just something."""
        self.assertEqual(self._bundle()[0], 0)
        claim = self.dir / "my.claim.json"
        _run([
            "claim", "--bundle", str(self.dir / "bundle.json"),
            "--assertion", "x", "--source-commit", "0" * 40,
            "--output", str(claim),
        ])
        code, _ = _run([
            "verify", "--claim", str(claim),
            "--bundle", str(EXAMPLES / "claude-code" / "bundle.json"),
        ])
        self.assertEqual(code, 4, "wrong evidence must exit REFUTED")

    def test_bad_evidence_fails_closed_rather_than_writing_a_bundle(self) -> None:
        (self.dir / "traces.csv").write_text("task_id\nt1\n", encoding="utf-8")
        code, text = self._bundle()
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE", text)
        self.assertFalse((self.dir / "bundle.json").exists())


if __name__ == "__main__":
    unittest.main()
