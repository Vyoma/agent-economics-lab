"""
Packaging invariants.

The version now has a single source of truth (`agent_economics.__version__`),
which `pyproject.toml` reads dynamically. `CITATION.cff` and `CHANGELOG.md`
still carry their own copies, so these tests keep them from drifting.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

import agent_economics

ROOT = Path(__file__).resolve().parents[1]

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class VersionConsistencyTest(unittest.TestCase):
    def test_package_version_is_semver(self) -> None:
        self.assertRegex(agent_economics.__version__, SEMVER)

    def test_version_is_exported(self) -> None:
        self.assertIn("__version__", agent_economics.__all__)

    def test_pyproject_takes_its_version_from_the_package(self) -> None:
        """A hardcoded `version =` under [project] would reintroduce the drift."""
        pyproject = (ROOT / "pyproject.toml").read_text()
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('version = {attr = "agent_economics.__version__"}', pyproject)
        project_block = pyproject.split("[project]", 1)[1].split("\n[", 1)[0]
        self.assertNotRegex(project_block, r"(?m)^version\s*=")

    def test_citation_matches_the_package(self) -> None:
        citation = (ROOT / "CITATION.cff").read_text()
        match = re.search(r"(?m)^version:\s*(\S+)$", citation)
        self.assertIsNotNone(match, "CITATION.cff has no version field")
        self.assertEqual(match.group(1), agent_economics.__version__)

    def test_changelog_documents_the_current_version(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text()
        headings = re.findall(r"(?m)^## (\d+\.\d+\.\d+)", changelog)
        self.assertTrue(headings, "CHANGELOG.md has no version headings")
        self.assertEqual(headings[0], agent_economics.__version__)


class CliVersionTest(unittest.TestCase):
    def test_version_flag_reports_the_package_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent_economics", "--version"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(agent_economics.__version__, result.stdout)


class RequiresPythonTest(unittest.TestCase):
    def test_declared_floor_matches_the_interpreter_features_used(self) -> None:
        """
        The code uses zip(strict=), match-free 3.10 syntax and parenthesized
        context managers. Lowering requires-python without revisiting those
        would ship a package that cannot import on the versions it claims.
        """
        pyproject = (ROOT / "pyproject.toml").read_text()
        match = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)"', pyproject)
        self.assertIsNotNone(match, "pyproject.toml has no requires-python floor")
        self.assertGreaterEqual((int(match.group(1)), int(match.group(2))), (3, 10))


if __name__ == "__main__":
    unittest.main()
