"""Render research/FINDINGS.md: the citable index of what the audits found.

research/CORPUS.md explains each dataset at length, which is right for a
reader working through one of them and wrong for anyone who needs to point
at a result. A finding that cannot be cited cannot accumulate: it has no
stable handle, no priority date, and no fixed wording to quote, so every
reference to it has to re-explain it and every re-explanation drifts.

This is the index. One line per finding, each with an identifier that never
changes, the date it was first published, the command that checks it, and
the scope it does not claim. The numbers are duplicated into findings.json
deliberately, so a citation is stable text rather than a moving computation,
and tests/test_findings.py recomputes every one of them from the frozen
evidence and fails the build when the two disagree.

The rule that makes the index worth trusting: a published finding is never
edited in place. It is superseded by a new identifier, or retracted with a
reason, and either way the original entry stays visible.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = pathlib.Path(__file__).resolve().parent / "findings.json"

KIND_LABEL = {
    "defect": "defect",
    "measurement": "measurement",
    "clean": "clean bill",
}


def load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def render() -> str:
    document = load()
    findings = document["findings"]
    standing = [f for f in findings if f["status"] == "standing"]
    kinds = {k: sum(1 for f in standing if f["kind"] == k) for k in KIND_LABEL}

    lines = [
        "# Findings index",
        "",
        "Every audit result this project has published, with a stable",
        "identifier, the date it was first published, the command that checks",
        "it, and the scope it does not claim.",
        "",
        f"**{len(standing)} standing: {kinds['defect']} defects, "
        f"{kinds['measurement']} measurements, {kinds['clean']} clean bills.** "
        "Clean bills are listed here with the same weight as defects, because",
        "an auditor that only ever finds problems is indistinguishable from",
        "one that manufactures them.",
        "",
        "A published finding is never edited in place. It is superseded by a",
        "new identifier or retracted with a reason, and either way the",
        "original entry stays. Numbers below are fixed text so a citation",
        "does not move; a test recomputes each of them from the frozen",
        "evidence and fails the build if the two ever disagree.",
        "",
        "| id | date | kind | dataset | finding |",
        "|---|---|---|---|---|",
    ]
    for finding in findings:
        headline = finding["statement"].split(". ")[0].rstrip(".")
        if len(headline) > 150:
            headline = headline[:147].rsplit(" ", 1)[0] + "..."
        dataset = finding["dataset"].split("/")[-1]
        lines.append(
            f"| `{finding['id']}` | {finding['date']} "
            f"| {KIND_LABEL[finding['kind']]} | `{dataset}` | {headline} |"
        )

    lines += ["", "## The findings in full", ""]
    for finding in findings:
        lines += [
            f"### {finding['id']} - {KIND_LABEL[finding['kind']]}, "
            f"{finding['date']}",
            "",
            f"**Dataset.** [`{finding['dataset']}`]"
            f"(https://huggingface.co/datasets/{finding['dataset']}) at "
            f"`{finding['revision'][:8]}`",
            "",
            finding["statement"],
            "",
            f"**Check it.** `{finding['verify']}`",
            "",
            f"**What it does not claim.** {finding['scope']}",
            "",
        ]

    lines += [
        "## Citing one",
        "",
        "Quote the identifier and the date: an identifier alone is ambiguous",
        "once a finding is superseded. `AEL-2026-008 (2026-09-02)` names one",
        "result, at one revision, with one published wording, and the command",
        "beside it re-derives the number from content-free frozen evidence",
        "without trusting this repository's own summary of it.",
        "",
        "[The full audits, dataset by dataset.](CORPUS.md) "
        "[How to add one.](../docs/contributing-an-audit.md)",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
