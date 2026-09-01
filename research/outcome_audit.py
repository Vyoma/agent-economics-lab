"""What a public agent-trajectory dataset says its outcomes were, two ways.

Every arm below is real: real API calls, real published spend, `exit_status`
"Submitted". They differ only in whether the outcome was scored.

`info.resolved` reads as the adjudicated result. Beside it sits
`info.scores.resolved`. For most arms they agree. For one they do not: the
outcome field is `true` on all 500 tasks while the cross-check is the string
`"unknown"` on all 500.

What that field is recording for that arm is not established here. It is
observed to be `true` everywhere while nothing confirms it anywhere, and nine
of those runs record a single API call and no spend, which is not a run that
resolved a SWE-bench issue. Calling it "a default" would be an inference, and
the observation is enough without one.

The dataset is not at fault. It ships the cross-check that makes this visible,
and the maintainers marked the unscored arm honestly. The failure would belong
to a consumer that reads one field and reports a rate.

That is the shape this repository was built around: the information needed to
refuse was present, one field away, and reading only the headline turns it into
a confident and impossible number.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "examples" / "public-swebench" / "outcome_audit.json"


def _summarise(rows: list[dict]) -> dict:
    scored = [r for r in rows if not isinstance(r["scores_resolved"], str)]
    unknown = [r for r in rows if isinstance(r["scores_resolved"], str)]
    naive_true = sum(1 for r in rows if r["resolved"] is True)
    return {
        "n": len(rows),
        "naive_resolved": naive_true,
        "naive_rate": naive_true / len(rows) if rows else 0.0,
        "unknown": len(unknown),
        "scored": len(scored),
        "confirmed_resolved": sum(1 for r in scored if r["resolved"] is True),
        "confirmed_rate": (
            sum(1 for r in scored if r["resolved"] is True) / len(scored)
            if scored else None
        ),
        "spend_usd": sum(r["instance_cost_usd"] or 0.0 for r in rows),
        "api_calls": sum(r["api_calls"] or 0 for r in rows),
    }


def _split(document: dict, pair: dict) -> tuple[int, int]:
    """How the disagreements fall in each direction.

    A symmetric split is evidence against the two arms being different runs:
    two different configurations would not be expected to trade wins evenly.
    """
    first, second = pair["arms"]
    left = {r["task_id"]: r["resolved"] for r in document["arms"][first]}
    right = {r["task_id"]: r["resolved"] for r in document["arms"][second]}
    shared = set(left) & set(right)
    return (
        sum(1 for t in shared if left[t] and not right[t]),
        sum(1 for t in shared if right[t] and not left[t]),
    )


def _resolved_count(document: dict, arm: str) -> int:
    return sum(1 for r in document["arms"][arm] if r["resolved"] is True)


def _idle(document: dict, arm: str) -> int:
    """Runs claiming success on one API call and no spend.

    A task resolved with a single call and $0.00 of spend is not a task that
    was resolved. This is checkable in the shipped evidence, unlike an appeal
    to what resolution rates are plausible.
    """
    return sum(
        1 for row in document["arms"][arm]
        if (row["api_calls"] or 0) <= 1
        and (row["instance_cost_usd"] or 0.0) == 0.0
        and row["resolved"] is True
    )


def duplicate_arms(document: dict) -> list[dict]:
    """Arm pairs publishing the same transcripts under different model labels.

    Detected on the transcript hash, not the whole-file hash: the model label
    and run id live in the same file, so two arms sharing a transcript still
    hash differently as whole files. When a pair is found, the outcomes attached to those identical
    transcripts give a direct reading of how repeatable the outcome label is,
    because the same input was scored twice.
    """
    arms = document["arms"]
    found = []
    names = sorted(arms)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            left = {r["task_id"]: r for r in arms[first]}
            right = {r["task_id"]: r for r in arms[second]}
            shared = sorted(set(left) & set(right))
            if not shared:
                continue
            identical = [
                t for t in shared
                if left[t]["messages_sha256"] == right[t]["messages_sha256"]
            ]
            if len(identical) != len(shared):
                continue
            disagree = [
                t for t in identical if left[t]["resolved"] != right[t]["resolved"]
            ]
            found.append({
                "arms": (first, second),
                "n": len(identical),
                "disagree": len(disagree),
                "agreement": (len(identical) - len(disagree)) / len(identical),
                "examples": disagree[:3],
            })
    return found


def render(document: dict) -> str:
    arms = {arm: _summarise(rows) for arm, rows in document["arms"].items()}
    order = sorted(arms, key=lambda a: (arms[a]["confirmed_rate"] is None, a))
    lines = [
        "# What the outcome field says, and what its cross-check says",
        "",
        "The dataset is an independent upload under an individual account, not",
        "a release by any of the vendors whose models the arms are named for. An",
        "arm name identifies a set of runs in this dataset. It is not a number any",
        "vendor published, and nothing below is a measurement of a model.",
        "",
        "Every arm here records real API calls and real published spend, both",
        "of which are in the frozen evidence and checkable. They differ in",
        "whether the outcome was confirmed.",
        "",
        "`naive` reads `info.resolved` alone, which is what a consumer computing",
        "a leaderboard from this dataset would do. `confirmed` counts only the",
        "trajectories whose `info.scores.resolved` is a number rather than the",
        "string `\"unknown\"`.",
        "",
        "| arm | n | naive resolved | naive rate | cross-check unknown | confirmed rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in order:
        s = arms[arm]
        confirmed = (
            f"{s['confirmed_rate']:.1%}" if s["confirmed_rate"] is not None
            else "**unestablished**"
        )
        lines.append(
            f"| `{arm}` | {s['n']} | {s['naive_resolved']} | "
            f"{s['naive_rate']:.1%} | {s['unknown']} | {confirmed} |"
        )
    unscored = [a for a in order if arms[a]["confirmed_rate"] is None]
    lines += [
        "",
        f"**{len(unscored)} of {len(arms)} arms examined report a resolution rate "
        "that their own cross-check field does not confirm for a single task.**",
        "",
    ]
    for arm in unscored:
        s = arms[arm]
        lines += [
            f"`{arm}` reads **{s['naive_rate']:.0%}** from `info.resolved` across "
            f"all {s['n']} tasks, at ${s['spend_usd']:,.2f} of published spend "
            f"over {s['api_calls']:,} API calls. Its cross-check is `\"unknown\"` "
            f"on all {s['unknown']}. There is no confirmed rate to report, which "
            "is different from a low one.",
            "",
            (
                f"Harder than any plausibility argument: {_idle(document, arm)} "
                f"of those {s['n']} runs record a single API call and no spend, "
                "and `info.resolved` is `true` for every one of them. Whatever "
                "those runs were, they did not resolve a SWE-bench issue."
                if _idle(document, arm) else ""
            ),
            "",
        ]
    duplicates = duplicate_arms(document)
    confirmed_rates = [
        s["confirmed_rate"] for s in arms.values() if s["confirmed_rate"] is not None
    ]
    spread = (max(confirmed_rates) - min(confirmed_rates)) * 100 if confirmed_rates else 0.0
    if duplicates:
        lines += [
            "## The same transcripts, published twice, scored differently",
            "",
            "One arm pair carries byte-identical transcripts. Same messages,",
            "same cost to sixteen decimal places, same API call count; the",
            "files differ only in `info.docent.model_label` and the run id.",
            "",
            "That accident is useful. It scored the same input twice, which is",
            "a direct reading of how repeatable this outcome label is.",
            "",
        ]
        for pair in duplicates:
            first, second = pair["arms"]
            lines += [
                f"`{first}` and `{second}`: **{pair['n']} of {pair['n']} "
                f"transcripts identical**, and `info.resolved` disagrees on "
                f"**{pair['disagree']}** of them. Agreement with itself on "
                f"identical input: **{pair['agreement']:.1%}**.",
                "",
                f"Examples where the same transcript was scored both ways: "
                f"{', '.join('`' + t + '`' for t in pair['examples'])}.",
                "",
                f"Across the {len(confirmed_rates)} arms with a confirmed "
                f"rate, the spread is {spread:.1f} points "
                f"({min(confirmed_rates):.1%} to {max(confirmed_rates):.1%}). "
                f"The label disagrees with itself by "
                f"{(1 - pair['agreement']) * 100:.1f}. Gaps of a few points "
                "between models in this dataset cannot be distinguished from "
                "the instrument disagreeing with itself; the largest gaps can.",
                "",
                "What causes it is not established here. Flaky tests, a "
                "non-deterministic evaluation environment, and a labelling "
                "pipeline that scored the two copies at different times would "
                "all produce this, and nothing in the frozen evidence "
                "separates them.",
                "",
                "A fourth possibility undercuts the reading above rather than "
                "explaining it: these may have been two genuinely different "
                "runs whose transcript files were duplicated during packaging "
                "while their labels were joined in separately. That would make "
                "this a packaging artifact and not a reading of the label at "
                "all, and the figure would not be a test-retest figure.",
                "",
                f"Two things in the evidence argue against it. The "
                f"{pair['disagree']} disagreements split exactly "
                f"{_split(document, pair)[0]}/{_split(document, pair)[1]} in "
                "each direction, and both arms resolve exactly "
                f"{_resolved_count(document, pair['arms'][0])} of {pair['n']}. "
                "Two different configurations would not be expected to produce "
                "either. Neither settles it.",
                "",
                "What is established is narrower and enough: whatever produced "
                "these labels, it did not produce the same label twice for the "
                "same transcript.",
                "",
            ]
    lines += [
        "## What this is and is not",
        "",
        "It is a factual reading of two fields in a public MIT-licensed dataset,",
        "reproducible from the frozen content-free evidence in",
        "`examples/public-swebench/outcome_audit.json`, where every row carries",
        "the SHA-256 of the complete upstream trajectory it came from.",
        "",
        "It is not a claim that the dataset is wrong. The dataset ships the",
        "cross-check that makes this visible and marks the unscored arm honestly.",
        "A consumer reading one field and publishing a rate is the failure.",
        "",
        "It is not a claim about any model's real capability. An unscored arm is",
        "unscored; nothing here establishes whether it would have done well.",
        "",
    ]
    missing = document.get("not_obtained") or {}
    if missing:
        lines += [
            f"{len(missing)} arm(s) published upstream are absent here because "
            "the download did not complete: "
            + ", ".join(f"`{a}` ({n} of "
                        f"{document.get('expected_tasks_per_arm', '?')})"
                        for a, n in sorted(missing.items()))
            + ". They are omitted rather than recorded as empty, since a "
            "failed fetch is not evidence of a result.",
            "",
        ]
    else:
        lines += [
            f"All {len(arms)} arms published upstream at the pinned revision "
            "are included. Nothing was dropped for a failed fetch.",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    if not AUDIT.exists():
        print(f"missing {AUDIT}", file=sys.stderr)
        return 1
    print(render(json.loads(AUDIT.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
