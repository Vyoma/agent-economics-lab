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
