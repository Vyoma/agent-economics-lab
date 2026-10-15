"""A public release is one bound object, not three matching strings by convention."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_release", ROOT / "scripts" / "check_release.py"
)
assert SPEC and SPEC.loader
check_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_release)


class ReleaseMetadataTests(unittest.TestCase):
    def test_current_tree_has_one_matching_release_identity(self) -> None:
        version, release_date = check_release.validate_release(
            tag="v0.10.0",
            package_init=ROOT / "agent_economics" / "__init__.py",
            changelog=ROOT / "CHANGELOG.md",
        )
        self.assertEqual(version, "0.10.0")
        self.assertEqual(release_date.isoformat(), "2026-10-14")

    def test_wrong_tag_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match package version"):
            check_release.validate_release(
                tag="v0.9.0",
                package_init=ROOT / "agent_economics" / "__init__.py",
                changelog=ROOT / "CHANGELOG.md",
            )

    def test_duplicate_changelog_identity_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            changelog = Path(directory) / "CHANGELOG.md"
            changelog.write_text(
                "# Changelog\n\n## Unreleased\n\n"
                "## 0.10.0 - 2026-10-14\n\n"
                "## 0.10.0 - 2026-10-14\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exactly one dated heading"):
                check_release.changelog_date(changelog, "0.10.0")

    def test_version_is_parsed_without_importing_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_init = Path(directory) / "__init__.py"
            package_init.write_text(
                '__version__ = "1.2.3"\nraise RuntimeError("must not import")\n',
                encoding="utf-8",
            )
            self.assertEqual(check_release.package_version(package_init), "1.2.3")


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_workflow_checks_every_published_surface(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        for required in (
            "fetch-depth: 0",
            "scripts/check_release.py",
            "make reproduce",
            "python -m build --sdist --wheel",
            'agent-economics" demo',
            'scripts/check_release.py --tag "$GITHUB_REF_NAME"',
            "sha256sum",
            "gh release upload",
        ):
            self.assertIn(required, workflow)


if __name__ == "__main__":
    unittest.main()
