"""The wheel must carry the data the demo needs.

Before this, `pip install` produced 36 modules and no data, so an installed
copy had nothing to decide about. A package whose whole argument is "check
it yourself" made the first check require a clone, a Makefile and an
interpreter override.

The demo inputs are copies of the files in `examples/`, which is a drift
risk, so the copies are compared here byte for byte.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGED = ROOT / "agent_economics" / "_examples"
SOURCE = ROOT / "examples"


class ThePackagedExamplesMatchTheRepository(unittest.TestCase):
    def test_source_archive_declares_the_public_contract_documents(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        for path in (
            "CHANGELOG.md",
            "CITATION.cff",
            "SECURITY.md",
            "SPEC.md",
            "THIRD_PARTY_NOTICES.md",
            "scripts/check_release.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f"include {path}", manifest)

    def test_license_metadata_uses_the_current_pep_639_shape(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('license = "Apache-2.0"', pyproject)
        self.assertIn('license-files = ["LICENSE", "NOTICE"]', pyproject)
        self.assertNotIn("License :: OSI Approved", pyproject)

    def test_every_demo_input_is_byte_identical_to_its_source(self) -> None:
        from agent_economics.cli import DEMO_INPUTS

        for name in DEMO_INPUTS:
            with self.subTest(name=name):
                self.assertEqual(
                    (PACKAGED / name).read_bytes(),
                    (SOURCE / name).read_bytes(),
                    f"agent_economics/_examples/{name} has drifted from "
                    f"examples/{name}",
                )

    def test_the_manifest_names_files_that_exist(self) -> None:
        from agent_economics.cli import DEMO_INPUTS

        for name in DEMO_INPUTS:
            with self.subTest(name=name):
                self.assertTrue((PACKAGED / name).is_file())

    def test_package_data_is_declared(self) -> None:
        """A file in the directory that setuptools is not told to ship is a
        file the wheel silently drops."""
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.setuptools.package-data]", pyproject)
        self.assertIn('agent_economics = ["_examples/*"]', pyproject)


class TheDemoRunsFromThePackagedData(unittest.TestCase):
    def test_demo_agrees_with_the_same_files_run_by_hand(self) -> None:
        """`demo` re-parses into `evaluate`, so the two cannot answer
        differently. Run both and compare, including the evidence digest."""
        packaged = subprocess.run(
            [sys.executable, "-m", "agent_economics.cli", "demo"],
            capture_output=True, text=True, cwd=ROOT,
        )
        by_hand = subprocess.run(
            [sys.executable, "-m", "agent_economics.cli", "evaluate",
             "--traces", str(SOURCE / "support_trace.csv"),
             "--outcomes", str(SOURCE / "outcomes.csv"),
             "--rates", str(SOURCE / "rates.json"),
             "--baseline", str(SOURCE / "baseline.json"),
             "--policy", str(SOURCE / "policy.json")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(packaged.returncode, by_hand.returncode)
        self.assertEqual(packaged.stdout, by_hand.stdout)
        self.assertIn("Decision:", packaged.stdout)

    def test_extract_prints_a_followup_that_survives_uvx_exit(self) -> None:
        from agent_economics import __version__

        with tempfile.TemporaryDirectory() as directory:
            extracted = pathlib.Path(directory) / "inputs"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_economics.cli",
                    "demo",
                    "--extract",
                    str(extracted),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uvx --from", result.stdout)
        self.assertIn(
            "git+https://github.com/Vyoma/agent-economics-lab@v" + __version__,
            result.stdout,
        )
        self.assertNotIn("\n  agent-economics evaluate", result.stdout)


if __name__ == "__main__":
    unittest.main()


class TheDriftGuardIsNotVacuous(unittest.TestCase):
    def test_a_changed_packaged_file_is_caught(self) -> None:
        """Proven by corrupting a copy and watching the comparison fail,
        rather than by trusting that a byte comparison compares bytes."""
        from agent_economics.cli import DEMO_INPUTS

        name = DEMO_INPUTS[0]
        target = PACKAGED / name
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"\n")
            with self.assertRaises(AssertionError):
                ThePackagedExamplesMatchTheRepository(
                    "test_every_demo_input_is_byte_identical_to_its_source"
                ).test_every_demo_input_is_byte_identical_to_its_source()
        finally:
            target.write_bytes(original)
        self.assertEqual(target.read_bytes(), (SOURCE / name).read_bytes())
