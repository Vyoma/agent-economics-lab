#!/usr/bin/env python3
"""Read-only, standard-library audit for an artifact-first OSS repository."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


CLAIM_PATTERNS = {
    "first-or-only-category": re.compile(
        r"\b(?:the\s+)?(?:first|only)\b.{0,60}\b"
        r"(?:platform|framework|tool|system|solution|engine)\b",
        re.I,
    ),
    "enterprise-proven": re.compile(r"\benterprise[- ]proven\b", re.I),
    "production-ready": re.compile(r"\bproduction[- ]ready\b", re.I),
    "dependency-free": re.compile(r"\bdependency[- ]free\b", re.I),
    "zero-compute": re.compile(r"\bzero[- ]compute(?:[- ]cost)?\b", re.I),
    "deadlock-proof": re.compile(r"\b(?:deadlock[- ]proof|prevents? deadlocks?)\b", re.I),
    "unbounded-integration": re.compile(
        r"\b(?:works with|integrates with|plug(?:s|ged)? in(?:to)?)\b.{0,80}"
        r"\b(?:galileo|langsmith|opentelemetry)\b",
        re.I,
    ),
    "universal-compatibility": re.compile(
        r"\bworks with\b.{0,100}\b(?:all|any|every)\b", re.I
    ),
    "outcome-prevention": re.compile(
        r"\bprevents?\b.{0,80}\b(?:unsafe|failure|risk|incident|harm)\b", re.I
    ),
}


def git(repo: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode, (result.stdout or result.stderr).strip()


def any_exists(repo: Path, patterns: tuple[str, ...]) -> bool:
    return any(any(repo.glob(pattern)) for pattern in patterns)


def check(name: str, passed: bool, passed_detail: str, review_detail: str) -> Check:
    return Check(name, passed, passed_detail if passed else review_detail)


def scan_claims(readme: Path) -> list[dict[str, object]]:
    if not readme.exists():
        return []
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(readme.read_text(errors="replace").splitlines(), 1):
        for label, pattern in CLAIM_PATTERNS.items():
            if pattern.search(line):
                findings.append(
                    {"label": label, "line": line_number, "text": line.strip()}
                )
    return findings


def audit(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    readme = repo / "README.md"
    readme_text = readme.read_text(errors="replace") if readme.exists() else ""

    checks = [
        check("README", readme.exists(), "README.md is present", "README.md was not found"),
        check(
            "License",
            any_exists(repo, ("LICENSE", "LICENSE.*", "COPYING", "COPYING.*")),
            "A license file is present",
            "No recognized license file was found",
        ),
        check(
            "Contributing",
            (repo / "CONTRIBUTING.md").exists(),
            "CONTRIBUTING.md is present",
            "CONTRIBUTING.md was not found",
        ),
        check(
            "Security",
            (repo / "SECURITY.md").exists(),
            "SECURITY.md is present",
            "SECURITY.md was not found",
        ),
        check(
            "CI",
            any_exists(repo, (".github/workflows/*.yml", ".github/workflows/*.yaml")),
            "A GitHub Actions workflow is present",
            "No GitHub Actions workflow was found",
        ),
        check(
            "Tests",
            any_exists(repo, ("tests/*", "test/*", "**/*_test.py", "**/*.test.*")),
            "A test surface is present",
            "No recognized test surface was found",
        ),
        check(
            "Package metadata",
            any_exists(repo, ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")),
            "Recognized package metadata is present",
            "No recognized package metadata was found",
        ),
        check(
            "Limitations",
            bool(re.search(r"\blimitations?\b|\bclaim boundary\b", readme_text, re.I))
            or any_exists(repo, ("docs/*limit*", "research/*DATA_CARD*")),
            "Limitations or a claim boundary are visible",
            "No visible limitations or claim boundary were found",
        ),
        check(
            "Runnable command",
            bool(re.search(r"\b(?:make reproduce|reproduc(?:e|tion))\b", readme_text, re.I))
            or bool(
                re.search(
                    r"```(?:bash|sh)?\s*\n[\s\S]{0,300}?\b"
                    r"(?:make|python3?|npm|pnpm|yarn|cargo|go)\b",
                    readme_text,
                    re.I,
                )
            ),
            "README exposes a runnable or reproduction command",
            "README has no recognized runnable or reproduction command",
        ),
        check(
            "Synthetic labeling",
            not re.search(r"\b(?:scenarios|ablations|benchmark)\b", readme_text, re.I)
            or bool(re.search(r"\bsynthetic\b", readme_text, re.I)),
            "Benchmark language is paired with a synthetic label when applicable",
            "Benchmark language appears without an explicit synthetic label",
        ),
    ]

    git_repo_code, _ = git(repo, "rev-parse", "--is-inside-work-tree")
    head_code, head_detail = git(repo, "rev-parse", "--verify", "HEAD")
    status_code, status_detail = git(repo, "status", "--short")
    checks.extend(
        [
            check(
                "Git repository",
                git_repo_code == 0,
                "Repository has Git metadata",
                "No Git repository metadata was found",
            ),
            Check("Git history", head_code == 0, head_detail or "No commit exists"),
            Check(
                "Clean worktree",
                status_code == 0 and not status_detail,
                status_detail or "Working tree is clean",
            ),
        ]
    )

    claim_findings = scan_claims(readme)
    passed = sum(check.passed for check in checks)
    return {
        "repository": str(repo),
        "score": {"passed": passed, "total": len(checks)},
        "checks": [asdict(check) for check in checks],
        "claim_findings": claim_findings,
    }


def render_markdown(report: dict[str, object]) -> str:
    score = report["score"]
    lines = [
        "# Artifact-First Repository Audit",
        "",
        f"Repository: `{report['repository']}`",
        f"Checks passed: **{score['passed']} / {score['total']}**",
        "",
        "## Checks",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        result = "PASS" if check["passed"] else "REVIEW"
        detail = str(check["detail"]).replace("\n", "<br>").replace("|", "\\|")
        lines.append(f"| {check['name']} | {result} | {detail} |")

    lines.extend(["", "## Claim-language findings", ""])
    findings = report["claim_findings"]
    if findings:
        for finding in findings:
            lines.append(
                f"- Line {finding['line']} · `{finding['label']}`: {finding['text']}"
            )
    else:
        lines.append("No high-risk phrases found in README.md.")

    lines.extend(
        [
            "",
            "These are review prompts, not automatic failures. Inspect context before editing.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    report = audit(Path(args.repository))
    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
