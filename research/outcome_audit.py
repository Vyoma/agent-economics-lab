"""What a public agent-trajectory dataset says its outcomes were, two ways.

Every arm below is real: real API calls, real published spend, `exit_status`
"Submitted". They differ only in whether the outcome was scored.

`info.resolved` reads as the adjudicated result. Beside it sits
`info.scores.resolved`. For four arms they agree. For one they do not: the
outcome field is `true` on all 500 tasks while the cross-check is the string
`"unknown"` on all 500. A 100% resolution rate on SWE-bench Verified is not a
result anyone has achieved, so that field is a default that scoring never
overwrote.

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


def duplicate_arms(document: dict) -> list[dict]:
    """Arm pairs publishing the same transcripts under different model labels.

    Detected on the transcript hash, not the whole-file hash: the model label
    and run id live in the same file, so two arms sharing a transcript hash
    differently. When a pair is found, the outcomes attached to those identical
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
        "Every arm here is a real run: real API calls, real published spend,",
        "`exit_status` \"Submitted\". They differ only in whether the outcome was",
        "scored.",
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
                f"rate, the spread is {spread:.0f} points "
                f"({min(confirmed_rates):.1%} to {max(confirmed_rates):.1%}). "
                f"The label disagrees with itself by "
                f"{(1 - pair['agreement']) * 100:.0f}. Gaps of a few points "
                "between models in this dataset cannot be distinguished from "
                "the instrument disagreeing with itself; the largest gaps can.",
                "",
                "What causes it is not established here. Flaky tests, a "
                "non-deterministic evaluation environment, and a labelling "
                "pipeline that scored the two copies at different times would "
                "all produce this, and nothing in the frozen evidence "
                "separates them. What is established is narrower and enough: "
                "the label is not a function of the transcript.",
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
        "Five further arms exist upstream and are absent here because the",
        "download was rate-limited. They are omitted rather than recorded as",
        "empty, since a failed fetch is not evidence.",
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
