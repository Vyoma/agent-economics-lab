#!/usr/bin/env python3
"""Fail closed when a release tag, package version, and changelog disagree."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def package_version(package_init: Path) -> str:
    tree = ast.parse(package_init.read_text(encoding="utf-8"), filename=str(package_init))
    assignments = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "__version__":
            assignments.append(node.value)
    if len(assignments) != 1:
        raise ValueError("package must assign __version__ exactly once")
    value = ast.literal_eval(assignments[0])
    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise ValueError(f"package version is not strict SemVer: {value!r}")
    return value


def changelog_date(changelog: Path, version: str) -> dt.date:
    text = changelog.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## {re.escape(version)} - (\d{{4}}-\d{{2}}-\d{{2}})$",
        re.MULTILINE,
    )
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ValueError(
            f"CHANGELOG.md must contain exactly one dated heading for {version}; "
            f"found {len(matches)}"
        )
    try:
        release_date = dt.date.fromisoformat(matches[0])
    except ValueError as exc:
        raise ValueError(f"invalid changelog date for {version}: {matches[0]}") from exc
    unreleased = text.find("## Unreleased")
    released = text.find(f"## {version} - ")
    if unreleased < 0 or unreleased > released:
        raise ValueError("CHANGELOG.md must keep Unreleased ahead of the current release")
    return release_date


def validate_release(*, tag: str, package_init: Path, changelog: Path) -> tuple[str, dt.date]:
    version = package_version(package_init)
    expected = f"v{version}"
    if tag != expected:
        raise ValueError(f"release tag {tag!r} does not match package version {expected!r}")
    return version, changelog_date(changelog, version)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--tag", required=True, help="Git tag, for example v0.10.0")
    result.add_argument(
        "--package-init",
        type=Path,
        default=ROOT / "agent_economics" / "__init__.py",
    )
    result.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        version, release_date = validate_release(
            tag=args.tag,
            package_init=args.package_init,
            changelog=args.changelog,
        )
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"release metadata invalid: {exc}", file=sys.stderr)
        return 2
    print(f"release metadata valid: v{version} ({release_date.isoformat()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
