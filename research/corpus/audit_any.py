"""Audit any public agent-trajectory dataset, without writing code for it.

Every entry in this corpus needed a hand-written spec and extractor, which
meant the registry could only grow at the rate its author wrote Python.
That is the wrong shape for a registry that wants third-party entries: the
contract in docs/contributing-an-audit.md asks people to freeze evidence
and compute censuses, and then hands them a blank file.

This points the same checks at an arbitrary Hugging Face dataset. It reads
the schema, proposes which columns look like outcomes and which look like
transcripts, freezes a content-free sample, and runs the census family the
corpus uses: outcome coverage, duplicate detection, degenerate positives,
and - where a dataset carries two outcome signals - agreement between them,
which is the measurement that produced this project's sharpest finding.

    python3 research/corpus/audit_any.py <dataset-id>
    python3 research/corpus/audit_any.py <dataset-id> --rows 2000
    python3 research/corpus/audit_any.py <dataset-id> --outcome resolved

What it will not do is decide anything for you. Column roles are *proposed*
and printed as proposals; a dataset whose outcome column it cannot identify
is reported as such rather than audited against a guess. Nothing it prints
is a finding: it is a census, and the contract requires a suspicion to
survive its base rate and a verification pass before it becomes one. The
output says so.

This is deliberately a sample by default, and every figure is labelled with
the denominator it was computed over. A rate over a sample presented as a
census is the defect this corpus most often finds in other people's data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

_ROWS = "https://datasets-server.huggingface.co/rows"
_INFO = "https://huggingface.co/api/datasets"
_SPLITS = "https://datasets-server.huggingface.co/splits"

#: Column names that usually carry an outcome. Matched case-insensitively
#: as whole words or suffixes, and always reported as a proposal.
OUTCOME_HINTS = (
    "resolved", "success", "correct", "passed", "pass", "accepted",
    "label", "score", "rating", "reward", "target", "verdict", "outcome",
)
#: Columns that usually carry the work itself, hashed and never stored.
TRANSCRIPT_HINTS = ("messages", "trajectory", "conversation", "transcript",
                    "event_log", "history", "steps")
#: Columns that usually carry effort, for the degenerate-positive check.
EFFORT_HINTS = ("cost", "tokens", "calls", "steps", "duration", "time",
                "iterations", "turns")


def _get(url: str) -> dict | None:
    """Fetch with backoff, and treat 429 as the instruction it is.

    A linear few-second backoff is not enough after sustained use: the
    first version of this gave up inside fifteen seconds against a rate
    limit that wanted minutes, which for a tool someone else runs reads as
    "the dataset is broken". 429 and 503 back off exponentially and honour
    Retry-After when the server sends one.
    """
    import time

    last: Exception | None = None
    for attempt in range(7):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last = error
            if error.code in (429, 503):
                header = error.headers.get("Retry-After") if error.headers else None
                wait = int(header) if (header or "").isdigit() else 2 ** attempt * 5
                print(
                    f"  rate limited, waiting {wait}s "
                    f"(attempt {attempt + 1}/7)", file=sys.stderr, flush=True,
                )
                time.sleep(min(wait, 120))
                continue
        except Exception as error:  # retried, then surfaced
            last = error
        time.sleep(3 * (attempt + 1))
    raise SystemExit(
        f"could not read {url.split('?')[0]} after 7 attempts: {last}. "
        "The Hugging Face datasets API rate-limits sustained use; wait and "
        "retry, or pass a smaller --rows."
    )


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _looks_like(name: str, hints: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(h == lowered or lowered.endswith("_" + h) or h in lowered
               for h in hints)


def _usable(value: object) -> bool:
    """A value that could carry an outcome. Strings like 'unknown' do not.

    This corpus exists partly because a dataset published a 100% resolution
    rate from a field whose cross-check read "unknown" on every row, so a
    string where a verdict belongs is treated as absent, not as data.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    return False


def propose_roles(features: list[dict], rows: list[dict]) -> dict:
    """Roles are proposed from names and values, and printed as proposals."""
    names = [f["name"] for f in features]
    outcomes, transcripts, effort = [], [], []
    for name in names:
        values = [r.get(name) for r in rows]
        usable = [v for v in values if _usable(v)]
        distinct = {v for v in usable}
        if _looks_like(name, TRANSCRIPT_HINTS):
            transcripts.append(name)
            continue
        if _looks_like(name, EFFORT_HINTS) and usable:
            effort.append(name)
        # An outcome is named like one, or is a small-cardinality numeric
        # column: booleans, 0/1, or a Likert range.
        if (_looks_like(name, OUTCOME_HINTS) and usable) or (usable and len(distinct) <= 6 and all(
            isinstance(v, (int, float)) and not isinstance(v, str)
            for v in usable
        ) and len(usable) > len(values) / 2):
            outcomes.append(name)
    return {"outcome": outcomes, "transcript": transcripts, "effort": effort}


def _kappa(pairs: list[tuple]) -> float | None:
    """Cohen's kappa, quadratic-weighted when the scale is ordinal."""
    if len(pairs) < 30:
        return None
    categories = sorted({v for pair in pairs for v in pair})
    if len(categories) < 2:
        return None
    n = len(pairs)
    observed = Counter(pairs)
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    span = (max(categories) - min(categories)) ** 2 or 1
    num = sum(((i - j) ** 2 / span) * observed.get((i, j), 0)
              for i in categories for j in categories)
    den = sum(((i - j) ** 2 / span) * left[i] * right[j] / n
              for i in categories for j in categories)
    return 1 - num / den if den else None


def audit(dataset: str, wanted_rows: int, outcome_override: str | None) -> dict:
    info = _get(f"{_INFO}/{dataset}")
    if info is None:
        raise SystemExit(f"{dataset}: not found, or not public")
    revision = info["sha"]
    licence = (info.get("cardData") or {}).get("license")

    splits = _get(f"{_SPLITS}?dataset={urllib.parse.quote(dataset)}")
    if not splits or not splits.get("splits"):
        raise SystemExit(
            f"{dataset}: the rows API serves no splits for this dataset. "
            "Directory-structured datasets need a bespoke freezer; see "
            "research/corpus/freeze_cogym.py for the shape."
        )
    first = splits["splits"][0]
    config, split = first["config"], first["split"]

    rows: list[dict] = []
    features: list[dict] = []
    total = None
    page = 50
    while len(rows) < wanted_rows:
        query = urllib.parse.urlencode({
            "dataset": dataset, "config": config, "split": split,
            "offset": len(rows), "length": page,
        })
        document = _get(f"{_ROWS}?{query}")
        if not document or not document.get("rows"):
            break
        features = features or document.get("features", [])
        total = document.get("num_rows_total", total)
        for wrapper in document["rows"]:
            if wrapper.get("truncated_cells"):
                # A truncated cell hashes to something that is not the row.
                continue
            rows.append(wrapper["row"])
        if total and len(rows) >= total:
            break
    if not rows:
        raise SystemExit(f"{dataset}: no rows could be read")

    roles = propose_roles(features, rows)
    if outcome_override:
        roles["outcome"] = [outcome_override]

    report: dict = {
        "dataset": dataset, "revision": revision, "license": licence,
        "config": config, "split": split,
        "rows_read": len(rows), "rows_upstream": total,
        "sampled": bool(total and len(rows) < total),
        "proposed_roles": roles,
        "coverage": {}, "duplicates": {}, "agreement": [], "degenerate": {},
        "notes": [],
    }
    if licence is None:
        report["notes"].append(
            "no license is declared; the corpus contract does not permit "
            "publishing derived metadata from an unlicensed dataset"
        )
    if not roles["outcome"]:
        report["notes"].append(
            "no column proposed as an outcome; pass --outcome to name one "
            "rather than have this guess"
        )

    for name in roles["outcome"]:
        values = [r.get(name) for r in rows]
        usable = [v for v in values if _usable(v)]
        report["coverage"][name] = {
            "usable": len(usable), "of": len(values),
            "distinct": len({str(v) for v in usable}),
        }

    for name in roles["transcript"]:
        digests = [_sha(r.get(name)) for r in rows]
        groups = Counter(digests)
        repeated = {d: c for d, c in groups.items() if c > 1}
        report["duplicates"][name] = {
            "distinct": len(groups),
            "duplicate_groups": len(repeated),
            "rows_in_duplicate_groups": sum(repeated.values()),
        }

    # Two outcome signals on the same rows is the shape that makes an
    # instrument measurable rather than assumed.
    for i, first_name in enumerate(roles["outcome"]):
        for second_name in roles["outcome"][i + 1:]:
            pairs = [
                (r[first_name], r[second_name]) for r in rows
                if _usable(r.get(first_name)) and _usable(r.get(second_name))
            ]
            pairs = [(int(a), int(b)) for a, b in pairs
                     if float(a).is_integer() and float(b).is_integer()]
            value = _kappa(pairs)
            if value is not None:
                report["agreement"].append({
                    "pair": [first_name, second_name], "n": len(pairs),
                    "exact": sum(1 for a, b in pairs if a == b) / len(pairs),
                    "kappa": value,
                })

    for outcome_name in roles["outcome"]:
        for effort_name in roles["effort"]:
            positives = [
                r for r in rows
                if _usable(r.get(outcome_name)) and bool(r[outcome_name])
                and isinstance(r.get(effort_name), (int, float))
            ]
            if len(positives) < 20:
                continue
            efforts = [r[effort_name] for r in positives]
            floor = min(efforts)
            at_floor = sum(1 for e in efforts if e <= floor)
            report["degenerate"][f"{outcome_name}/{effort_name}"] = {
                "positives": len(positives),
                "median_effort": statistics.median(efforts),
                "at_minimum_effort": at_floor,
            }
    return report


def render(report: dict) -> str:
    lines = [
        f"# {report['dataset']}",
        f"revision {report['revision'][:8]}  license "
        f"{report['license'] or 'UNDECLARED'}  "
        f"{report['config']}/{report['split']}",
        "",
    ]
    scope = (
        f"{report['rows_read']:,} rows read"
        + (f" of {report['rows_upstream']:,} upstream" if report["rows_upstream"]
           else "")
        + ("  — A SAMPLE. Every figure below is over the sample, not the "
           "dataset." if report["sampled"] else "  — the whole split.")
    )
    lines += [scope, ""]

    roles = report["proposed_roles"]
    lines += ["## Proposed column roles (proposals, not findings)", ""]
    for role in ("outcome", "transcript", "effort"):
        found = ", ".join(f"`{n}`" for n in roles[role]) or "none"
        lines.append(f"- {role}: {found}")
    lines.append("")

    if report["coverage"]:
        lines += ["## Outcome coverage", "",
                  "| column | usable | of | distinct values |",
                  "|---|---:|---:|---:|"]
        for name, c in report["coverage"].items():
            lines.append(
                f"| `{name}` | {c['usable']:,} | {c['of']:,} "
                f"| {c['distinct']} |"
            )
        lines.append("")

    if report["duplicates"]:
        lines += ["## Duplicate work", "",
                  "| column | distinct | duplicate groups | rows in them |",
                  "|---|---:|---:|---:|"]
        for name, d in report["duplicates"].items():
            lines.append(
                f"| `{name}` | {d['distinct']:,} | {d['duplicate_groups']:,} "
                f"| {d['rows_in_duplicate_groups']:,} |"
            )
        lines.append("")

    if report["agreement"]:
        lines += ["## Two outcome signals on the same rows", "",
                  "| pair | n | exact | kappa |", "|---|---:|---:|---:|"]
        for a in report["agreement"]:
            lines.append(
                f"| `{a['pair'][0]}` vs `{a['pair'][1]}` | {a['n']:,} "
                f"| {a['exact']:.1%} | {a['kappa']:.3f} |"
            )
        lines += ["",
                  "A kappa below 0.60 would not clear the floor this package "
                  "requires of an outcome instrument. Whether these two "
                  "columns are the same question asked twice, or two "
                  "different questions, this cannot know - and that "
                  "distinction decides whether the number is a reliability "
                  "measurement or a spread between constructs.", ""]

    if report["degenerate"]:
        lines += ["## Positives at minimum effort", "",
                  "| outcome/effort | positives | median effort | at minimum |",
                  "|---|---:|---:|---:|"]
        for key, d in report["degenerate"].items():
            lines.append(
                f"| `{key}` | {d['positives']:,} | {d['median_effort']} "
                f"| {d['at_minimum_effort']} |"
            )
        lines.append("")

    if report["notes"]:
        lines += ["## Notes", ""] + [f"- {n}" for n in report["notes"]] + [""]

    lines += [
        "## What this is",
        "",
        "A census, not a finding. Nothing above has survived a base-rate "
        "check or a verification pass against upstream, and the corpus "
        "contract requires both before a number becomes a published "
        "result: a difference that looks dramatic pooled has more than "
        "once turned out to be composition. Column roles were proposed "
        "from names and value shapes and may be wrong.",
        "",
        "To turn one of these into a corpus entry, see "
        "[the contract](../../docs/contributing-an-audit.md).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", help="Hugging Face dataset id, owner/name")
    parser.add_argument("--rows", type=int, default=1000,
                        help="rows to read (default 1000)")
    parser.add_argument("--outcome", help="name the outcome column yourself")
    parser.add_argument("--json", action="store_true", help="emit the report")
    args = parser.parse_args(argv)

    report = audit(args.dataset, args.rows, args.outcome)
    sys.stdout.write(
        json.dumps(report, indent=1, sort_keys=True) + "\n"
        if args.json else render(report)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
