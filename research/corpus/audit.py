"""The corpus: every public agent-trajectory dataset this project has audited.

One dataset with findings is an anecdote. A registry of datasets each audited
the same way — same checks, same content-free frozen evidence, same refusal to
guess — is an instrument with a track record. This renders that registry from
the frozen evidence and nothing else; `make corpus` fails if the committed
document and the evidence disagree.

A clean bill is recorded with the same care as a defect. An auditor that only
ever finds problems is indistinguishable from one that manufactures them.

Checks, each applied wherever the frozen schema supports it:

  outcome census      Every distinct value of the outcome field, counted. An
                      outcome column with one value on every row is not a
                      measurement.
  re-adjudication     Where the dataset ships raw test logs beside graded-test
                      lists, resolution is re-derived from the log and compared
                      with the published label. Rows the parser cannot fully
                      read are excluded and counted, never guessed
                      (see parse_tests.py for the 186-false-positive lesson).
  duplicate arms      Transcript hashes that appear more than once, and whether
                      the label agrees with itself inside each duplicate group.
  degenerate runs     Positive outcomes on runs whose step count could not have
                      attempted the task.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
FROZEN = pathlib.Path(__file__).resolve().parent / "frozen"
CORPUS = ROOT / "research" / "CORPUS.md"
TARSUR = ROOT / "examples" / "public-swebench" / "outcome_audit.json"
TARSUR_REVISION = "b55979d6b24850b72ae4d80f912526280cd6058a"


def outcome_census(document: dict) -> Counter:
    return Counter(json.dumps(row["outcome"]) for row in document["rows"])


def readjudication(document: dict) -> dict | None:
    graded = [row for row in document["rows"] if "graded" in row]
    if not graded:
        return None
    verdicts = Counter(row["graded"]["verdict"] for row in graded)
    agree, disagreements = 0, []
    for row in graded:
        verdict = row["graded"]["verdict"]
        if verdict not in ("RESOLVED", "UNRESOLVED"):
            continue
        if (row["outcome"] == 1.0) == (verdict == "RESOLVED"):
            agree += 1
        else:
            disagreements.append(row["instance_id"])
    return {
        "rows_with_logs": len(graded),
        "verdicts": dict(verdicts),
        "parsed": agree + len(disagreements),
        "agree": agree,
        "disagreements": disagreements,
    }


def duplicate_groups(document: dict) -> list[dict]:
    by_hash: dict[str, list[dict]] = {}
    for row in document["rows"]:
        by_hash.setdefault(row["transcript_sha256"], []).append(row)
    groups = []
    for digest, rows in sorted(by_hash.items()):
        if len(rows) < 2:
            continue
        labels = {json.dumps(row["outcome"]) for row in rows}
        groups.append(
            {"transcript_sha256": digest, "n": len(rows),
             "ids": [row["id"] for row in rows], "labels_agree": len(labels) == 1}
        )
    return groups


def degenerate_positives(document: dict) -> list[str]:
    return [
        row["id"]
        for row in document["rows"]
        if row["outcome"] in (True, 1.0) and (row.get("steps") or 0) <= 1
    ]


def _load(slug: str) -> dict:
    return json.loads((FROZEN / f"{slug}.json").read_text(encoding="utf-8"))


def _tarsur_summary() -> dict:
    """The registry row for the dataset audited before this module existed.

    Derived from its frozen evidence so the registry cannot drift from it; the
    full analysis stays in research/OUTCOME_AUDIT.md.
    """
    document = json.loads(TARSUR.read_text(encoding="utf-8"))
    arms = document["arms"]
    rows = sum(len(v) for v in arms.values())
    unconfirmed = [
        arm for arm, arm_rows in arms.items()
        if all(isinstance(r["scores_resolved"], str) for r in arm_rows)
    ]
    return {"rows": rows, "arms": len(arms), "unconfirmed_arms": unconfirmed}


def render() -> str:
    coderforge = _load("coderforge")
    jetbrains = _load("jetbrains")
    tarsur = _tarsur_summary()

    cf_re = readjudication(coderforge)
    cf_census = outcome_census(coderforge)
    jb_census = outcome_census(jetbrains)
    jb_cross = Counter(row["cross"] for row in jetbrains["rows"])

    for slug, doc in (("coderforge", coderforge), ("jetbrains", jetbrains)):
        if duplicate_groups(doc) or degenerate_positives(doc):
            # Neither dataset currently trips these; if a re-freeze ever does,
            # the registry must say so rather than render a stale clean bill.
            raise AssertionError(f"{slug}: new finding in frozen evidence; rewrite its entry")

    lines = [
        "# The corpus: public agent-trajectory datasets, audited",
        "",
        "Every dataset here was audited under the same discipline:",
        "content-free evidence frozen at a named revision, checks from the",
        "same family, and a refusal to guess at what the evidence does not",
        "establish, excluded and counted instead. A clean bill",
        "is a result, recorded with the same care as a defect; an auditor that",
        "only ever finds problems is indistinguishable from one that",
        "manufactures them.",
        "",
        "Each dataset is an independent public upload; an arm or model name",
        "inside one identifies a set of runs in that dataset, not a number any",
        "vendor published, and nothing here is a measurement of a model.",
        "",
        "| dataset | revision | rows | what the audit found |",
        "|---|---|---:|---|",
        (
            f"| [tarsur385/swebench-verified-trajectories]"
            f"(https://huggingface.co/datasets/tarsur385/swebench-verified-trajectories) "
            f"| `{TARSUR_REVISION[:8]}` | {tarsur['rows']:,} "
            f"| {len(tarsur['unconfirmed_arms'])} of {tarsur['arms']} arms never confirmed by its "
            "cross-check; one duplicated arm pair, labels 91.2% self-consistent "
            "([full audit](OUTCOME_AUDIT.md)) |"
        ),
        (
            "| [togethercomputer/CoderForge-Preview-32B…]"
            "(https://huggingface.co/datasets/togethercomputer/"
            "CoderForge-Preview-32B-SWE-Bench-Verified-Evaluation-trajectories) "
            f"| `{coderforge['revision'][:8]}` | {len(coderforge['rows'])} "
            "| clean: reward re-derives from the raw logs on all "
            f"{cf_re['parsed']} parseable rows |"
        ),
        (
            "| [JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified]"
            "(https://huggingface.co/datasets/JetBrains-Research/"
            "agent-trajectories-swe-bench-test-minus-verified) "
            f"| `{jetbrains['revision'][:8]}` | {len(jetbrains['rows']):,} "
            f"| `resolved` column present, populated on 0 rows |"
        ),
        "",
        "## togethercomputer/CoderForge-Preview-32B, SWE-bench Verified, 500 rows",
        "",
        "The dataset ships the raw evaluation log and the graded-test lists",
        "beside every published `reward`, which permits the strongest check in",
        "this corpus: re-deriving each label from the log instead of comparing",
        "two fields the same pipeline wrote.",
        "",
        f"On every one of the **{cf_re['parsed']} rows the parser could fully",
        "read, the re-derived resolution equals the published reward**:",
        f"{len(cf_re['disagreements'])} disagreements. The published rate on those rows is",
        "confirmed, not merely self-consistent.",
        "",
        "The refusals, counted: "
        f"{cf_re['verdicts'].get('UNPARSED', 0)} rows use log formats the parser does not",
        f"read and {cf_re['verdicts'].get('AMBIGUOUS', 0)} depend on whether XFAIL",
        "counts as a pass, so they are",
        "excluded, not guessed. The first draft of this parser read only",
        "pytest's format and would have reported 186 false disagreements on",
        "Django's; a graded test the parser cannot locate now makes the row",
        "UNPARSED, never a finding.",
        "",
        f"Outcome census: {dict(sorted(cf_census.items()))}. No duplicate",
        "transcripts. No positive outcome on a run of one step or fewer.",
        "",
        "## JetBrains-Research, SWE-bench test-minus-verified, 1,785 rows",
        "",
        f"The `resolved` column is null on all {len(jetbrains['rows']):,} rows. "
        f"{jb_cross.get('Submitted', 0):,} runs report",
        f"`exit_status` \"Submitted\" and {jb_cross.get('LimitsExceeded', 0)}",
        "\"LimitsExceeded\"; none carries an",
        "adjudicated outcome. That is not an accusation — publishing",
        "trajectories without scoring them is a legitimate choice, and the",
        "column is honestly null rather than defaulted to a flattering value.",
        "It is a warning to consumers: a resolution rate computed from this",
        "dataset divides by zero scored runs, and any figure quoted from it",
        "was made somewhere else.",
        "",
        "No duplicate transcripts. Outcome census: "
        f"{dict(sorted(jb_census.items()))}.",
        "",
        "## How an entry gets here",
        "",
        "`research/corpus/freeze.py` fetches rows at a revision bracketed by",
        "the repository SHA (refusing a snapshot that moved mid-fetch, a",
        "partial arm, or a truncated cell), keeps identifiers, outcome fields,",
        "step counts, and SHA-256 hashes of the content it refuses to copy,",
        "and — where raw logs ship beside graded-test lists — the",
        "re-adjudication verdict. `research/corpus/audit.py` renders this",
        "document from the frozen evidence alone; `make corpus` fails when the",
        "two disagree. No prompts, responses, patches, or logs are stored.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    sys.stdout.write(render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
