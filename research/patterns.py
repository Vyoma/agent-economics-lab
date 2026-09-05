"""Render research/PATTERNS.md: what the audits say that one cannot.

Each corpus entry is a statement about one dataset. A registry earns its
name when the entries together support something none of them does alone,
and there are three such things. This renders them, computed
from the same frozen evidence the entries use, so the synthesis cannot
drift from what it summarises.

The temptation in a page like this is to generalise: "outcome instruments
are unreliable", "duplication is endemic". Datasets chosen partly for
being auditable do not support statements about a population, and the page
says so at the point where a reader would otherwise start extrapolating.
What it does support is narrower and still useful: a reader can see the
measured instruments side by side against the floor this package enforces,
which is a comparison nobody had assembled.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "corpus"))

from audit import (
    _load,
    cogym_summary,
    nebius_openhands_summary,
    nebius_sweagent_summary,
    posttrainbench_summary,
    hle_verifier_summary,
    swesmith_summary,
)

#: The floor agent_economics.provenance requires of an outcome instrument
#: before a green decision can be issued, for kappa-family methods.
KAPPA_FLOOR = 0.60


def _dataset_count() -> int:
    """From the findings index, not typed into the prose. This page said
    "Eight datasets" while the corpus held ten, in a generated file whose
    own header promises the build fails if it drifts; the build compared
    stale text with stale text and agreed with itself."""
    import json

    registry = json.loads(
        (ROOT / "research" / "findings.json").read_text(encoding="utf-8")
    )
    return len({f["dataset"] for f in registry["findings"]})


def measure() -> dict:
    openhands = nebius_openhands_summary()
    cogym = cogym_summary()
    ptb = posttrainbench_summary()
    smith = swesmith_summary()
    sweagent = nebius_sweagent_summary()
    jetbrains = _load("jetbrains")

    hle = hle_verifier_summary()
    human = cogym["pairs"]["outcomeRating|agentRating"]
    return {
        "instruments": [
            {
                "instrument": "model-generated tests",
                "against": "adjudicated hidden-test outcome",
                "statistic": "Cohen's kappa",
                "value": openhands["kappa"],
                "low": openhands["kappa_low"],
                "high": openhands["kappa_high"],
                "family": "kappa",
                "n": openhands["cross_present"],
                "dataset": "nebius/SWE-rebench-openhands-trajectories",
            },
            {
                "instrument": "one person's artifact rating",
                "against": "the same person's satisfaction rating",
                "statistic": "quadratic-weighted kappa",
                "value": human["qwk"],
                "low": human["qwk_low"],
                "high": human["qwk_high"],
                "family": "kappa",
                "n": human["n"],
                "dataset": "SALT-NLP/cogym-real-trajectories",
            },
            {
                "instrument": (
                    f"{len(hle['graders'])} models asked to verify, worst"
                ),
                "against": "exact match against a published answer",
                "statistic": "within-question AUC",
                "value": hle["worst"]["auc"],
                "low": hle["worst"]["low"],
                "high": hle["worst"]["high"],
                "family": "auc",
                "n": hle["questions"],
                "dataset": "FUSE-verifiers/HLE-Verifications",
            },
            {
                "instrument": (
                    f"{len(hle['graders'])} models asked to verify, best"
                ),
                "against": "exact match against a published answer",
                "statistic": "within-question AUC",
                "value": hle["best"]["auc"],
                "low": hle["best"]["low"],
                "high": hle["best"]["high"],
                "family": "auc",
                "n": hle["questions"],
                "dataset": "FUSE-verifiers/HLE-Verifications",
            },
        ],
        "absence": [
            {
                "dataset": "JetBrains-Research/agent-trajectories",
                "field": "resolved",
                "missing": sum(1 for r in jetbrains["rows"] if r["outcome"] is None),
                "rows": len(jetbrains["rows"]),
            },
            {
                "dataset": "aisa-group/PostTrainBench-Trajectories",
                "field": "accuracy",
                "missing": ptb["unusable_accuracy"],
                "rows": ptb["rows"],
            },
            {
                "dataset": "SALT-NLP/cogym-real-trajectories",
                "field": "communicationRating",
                "missing": cogym["rows"] - cogym["coverage"]["communicationRating"],
                "rows": cogym["rows"],
            },
            {
                "dataset": "SWE-bench/SWE-smith-trajectories",
                "field": "resolved",
                "missing": 0,
                "rows": smith["rows"],
            },
            {
                "dataset": "nebius/SWE-agent-trajectories",
                "field": "target",
                "missing": 0,
                "rows": sweagent["rows"],
            },
        ],
        "duplication": {
            "swesmith_verbatim": smith["xml_identical_duplicate_rows"],
            "swesmith_cross_split": smith["tool_xml_overlap"],
            "swesmith_rows": smith["rows"],
        },
    }


def render() -> str:
    data = measure()
    lines = [
        "# What the audits say together",
        "",
        "Each entry in [the corpus](CORPUS.md) is a statement about one",
        "dataset. These are the three things the entries support jointly and",
        "none supports alone. Every figure is computed from the same frozen",
        "evidence the entries use; `make patterns` regenerates this page and",
        "the build fails if it drifts.",
        "",
        "## Outcome instruments, side by side",
        "",
        "This package refuses a green decision unless the instrument that",
        f"produced the outcome labels is attested at kappa {KAPPA_FLOOR:.2f}",
        f"or better. {len({row['dataset'] for row in data['instruments']})}"
        " datasets in this corpus record two outcome signals",
        "on the same rows, which is what makes the instrument measurable",
        "rather than assumed. The floor governs chance-corrected agreement,",
        "so the AUC rows are shown beside it and not graded against it:",
        "there is no AUC floor in the contract, and reading one across",
        "metric families is a category error this project has published",
        "once already.",
        "",
        "| instrument | measured against | statistic | value (95% CI) | n"
        f" | clears {KAPPA_FLOOR:.2f}? |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in data["instruments"]:
        # Graded from the interval, not the point estimate, and only where
        # the floor governs that metric. This column read "yes" for a
        # quadratic-weighted kappa of 0.625 whose interval runs to 0.520,
        # and graded two AUCs against a kappa floor that does not govern
        # them: deciding pass or fail from a point estimate, and comparing
        # across metric families, in the same six characters.
        if row.get("family") == "auc":
            clears = "not comparable"
        elif row["low"] >= KAPPA_FLOOR:
            clears = "yes"
        elif row["high"] < KAPPA_FLOOR:
            clears = "**no**"
        else:
            clears = f"undetermined at n={row['n']:,}"
        lines.append(
            f"| {row['instrument']} | {row['against']} | {row['statistic']} "
            f"| {row['value']:.3f} [{row['low']:.3f}, {row['high']:.3f}]"
            f" | {row['n']:,} | {clears} |"
        )
    lines += [
        "",
        "The two are not the same kind of measurement and the table should",
        "not be read as a ranking. The first compares an automated signal",
        "against an adjudicated one and is a validity measurement. The",
        "second compares two questions put to the same person, so it is a",
        "spread between constructs, not a reliability figure - the human was",
        "never asked the same thing twice.",
        "",
        "What survives that caveat is worth stating plainly. The cheap",
        "automated oracle the field reaches for when there is no answer key",
        "lands at chance. And the human judgement everything else is",
        "validated against, asked two adjacent questions about one session,",
        "spreads by more than the margin most published instrument",
        "comparisons are arguing over. Anything reported as agreement with",
        "human labels inherits whichever question was asked, and none of",
        "these datasets record which.",
        "",
        "## The outcome column is often not an outcome",
        "",
        "Five entries carry a field a consumer would read as the outcome.",
        "How much of it is populated varies by more than an order of",
        "magnitude, and no dataset announces the difference:",
        "",
        "| dataset | field | rows without a usable value |",
        "|---|---|---:|",
    ]
    for row in sorted(data["absence"], key=lambda r: -r["missing"] / r["rows"]):
        share = row["missing"] / row["rows"]
        lines.append(
            f"| `{row['dataset'].split('/')[-1]}` | `{row['field']}` "
            f"| {row['missing']:,} of {row['rows']:,} ({share:.1%}) |"
        )
    lines += [
        "",
        "Two of the five are complete. One is empty. The pattern that",
        "matters for a reader is not the average but the range: a rate",
        "computed from any of these without checking the denominator is a",
        "rate over an unknown population, and two of the five would give a",
        "number quietly computed over a fraction of the dataset.",
        "",
        "## Duplication is easy to ship and invisible downstream",
        "",
        f"In one dataset alone: {data['duplication']['swesmith_verbatim']:,}",
        "rows are verbatim duplicates of other rows in the same split, and",
        f"{data['duplication']['swesmith_cross_split']:,} transcripts appear",
        "byte-identically in two splits, out of "
        f"{data['duplication']['swesmith_rows']:,} rows. A second dataset",
        "publishes two model arms whose transcripts are identical on every",
        "one of 500 tasks. Neither is visible without hashing, neither is",
        "mentioned on a dataset card, and training or evaluating on both",
        "halves counts the same work twice.",
        "",
        "## What this does not establish",
        "",
        f"{_dataset_count()} datasets, chosen partly because they were"
        " auditable at all,",
        "are not a sample of anything. These are not prevalence estimates,",
        "and a reader who leaves with \"agent datasets are unreliable\" has",
        "taken more than the evidence gives. Every figure above is a",
        "statement about a named dataset at a named revision, and the",
        "[findings index](FINDINGS.md) keeps each one attached to the",
        "command that checks it.",
        "",
        "The honest summary is narrower and still worth having: when these",
        "datasets were checked, the checks that failed were about whether",
        "the outcome could be trusted at all, rather than about the agents.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
