"""The claim ledger: append-only, and a build failure if anything here is false.

A record of claims that strangers checked is the only asset in this repository
that cannot be copied by reading it. Formats copy. Techniques copy. Calendar
time does not, and it cannot be backfilled.

That record only exists if it accumulates. The first version overwrote two
files on every reissue, so the "record" was permanently two current claims and
the history lived only in git, where no reader looks. Claims here are now
append-only: one file per issuance, named by the date and the revision it was
issued against, never rewritten.

The rule this enforces is the one that gives the record teeth:

    REFUTED is a build failure, forever.
    UNVERIFIED against today's code is fine for a historical claim, provided
    it pinned the revision a reader can check it against.

The distinction matters. A claim that no longer reproduces because a gate was
refactored is not a claim that was wrong; it is a claim you must check out a
commit to test. A claim the evidence actively contradicts is a published
falsehood, and it stays a failure until it is retracted rather than quietly
regenerated.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent_economics.adapters import (
    load_normalized_json_bundle,
)
from agent_economics.claim import (
    Verdict,
    parse_claim,
    verify,
)
from agent_economics.evidence import recompute_digest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "research" / "claims"
EXAMPLES = ROOT / "examples"


def _bundles_by_digest() -> dict[str, pathlib.Path]:
    """Every bundle this repository ships, keyed by recomputed digest.

    Keyed by what the contents hash to, not by any digest a file declares about
    itself, so a doctored bundle simply fails to match rather than resolving.
    """
    found: dict[str, pathlib.Path] = {}
    for path in sorted(EXAMPLES.rglob("*.json")):
        try:
            found[recompute_digest(load_normalized_json_bundle(path))] = path
        except (OSError, ValueError, LookupError):
            continue
    return found


def _entries() -> list[dict]:
    bundles = _bundles_by_digest()
    rows: list[dict] = []
    for path in sorted(CLAIMS.glob("*.claim.json")):
        row: dict = {"file": path.name}
        try:
            claim = parse_claim(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            rows.append({**row, "verdict": "MALFORMED", "detail": str(error)})
            continue
        row.update(
            assertion=claim.assertion,
            decision=claim.decision,
            issued_at=claim.issued_at,
            issuer=claim.issuer or "(unattributed)",
            source_commit=claim.source_commit,
        )
        evidence = bundles.get(claim.evidence_digest)
        if evidence is None:
            rows.append({
                **row, "verdict": "UNVERIFIED",
                "detail": "the evidence this names is not shipped in this repository",
                "evidence": "(absent)",
            })
            continue
        result = verify(claim, load_normalized_json_bundle(evidence))
        rows.append({
            **row,
            "evidence": str(evidence.relative_to(ROOT)),
            "verdict": result.verdict.value,
            "detail": result.reasons[0] if result.reasons else "",
        })
    return rows


def check(rows: list[dict]) -> list[str]:
    """Everything that must fail the build. REFUTED always; unpinned drift too."""
    problems: list[str] = []
    for row in rows:
        if row["verdict"] == Verdict.REFUTED.value:
            problems.append(
                f"{row['file']}: REFUTED. A published claim the evidence "
                "contradicts is a falsehood on the record. Retract it "
                "explicitly; do not regenerate it."
            )
        if row["verdict"] == "MALFORMED":
            problems.append(f"{row['file']}: malformed ({row.get('detail','')})")
        if row["verdict"] == Verdict.UNVERIFIED.value and not row.get("source_commit"):
            problems.append(
                f"{row['file']}: UNVERIFIED and pins no revision, so there is "
                "nothing a reader could check it against."
            )
    return problems


def render(rows: list[dict]) -> str:
    supported = sum(1 for r in rows if r["verdict"] == "SUPPORTED")
    lines = [
        "# Claim ledger",
        "",
        "Append-only. One file per issuance, named by the date and the revision",
        "it was issued against, never rewritten. `make ledger` regenerates this",
        "page and fails the build on anything false.",
        "",
        "A claim that no longer reproduces because a gate was refactored is not",
        "a claim that was wrong; it is one you check out a commit to test, and",
        "the verdict names which commit. A claim the evidence contradicts is a",
        "published falsehood and fails the build until it is retracted.",
        "",
        f"**{len(rows)} claims on the record, {supported} reproducing against "
        "the current tree.**",
        "",
        "| issued | claim | decision | against today's code |",
        "|---|---|---|---|",
    ]
    for row in rows:
        assertion = row.get("assertion", "(unreadable)")
        if len(assertion) > 88:
            assertion = assertion[:85] + "..."
        lines.append(
            f"| {row.get('issued_at','?')} | {assertion} | "
            f"`{row.get('decision','?')}` | **{row['verdict']}** |"
        )
    lines += ["", "## Each claim in full", ""]
    for row in rows:
        lines += [
            f"### `{row['file']}`",
            "",
            f"> {row.get('assertion','(unreadable)')}",
            "",
            f"- Issued **{row.get('issued_at','?')}** by "
            f"{row.get('issuer','(unattributed)')}",
            f"- Decision claimed: `{row.get('decision','?')}`",
            f"- Evidence: `{row.get('evidence','?')}`",
            f"- Issued against commit: `{row.get('source_commit') or '(none)'}`",
            f"- Against the current tree: **{row['verdict']}**",
        ]
        if row.get("detail"):
            lines.append(f"- {row['detail']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rows = _entries()
    problems = check(rows)
    if "--check" in argv:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
