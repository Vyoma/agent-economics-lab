"""Generate the plumbing for a corpus entry, so a contributor writes analysis.

    python3 research/corpus/scaffold_entry.py <owner/dataset>

Landing one entry means a freeze spec, an extractor, an upstream verifier,
a findings record and recomputation tests. That is roughly six hundred lines
of boilerplate whose shape the contract already fixes, and it stands between
a reader who has noticed something and a finding anyone can cite. This emits
the boilerplate from the dataset's own schema and leaves the parts that
require judgement blank, with a checklist naming them.

What it emits is a proposal, in the same sense `audit_any.py` proposes column
roles: guessed from names and value shapes, correct often enough to be worth
editing and never correct enough to commit unread. It refuses a dataset whose
licence is undeclared, because the corpus cannot publish derived metadata
from one.

A dataset that fits the rows transport gets its upstream verifier for free,
since `verify_corpus.VERIFIERS` registers everything in `freeze.SPECS`. That
is why this scaffolds a SPECS entry rather than a standalone freezer: the
standalone path exists for transports the rows API cannot serve, and it costs
a verifier nobody writes.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

_INFO = "https://huggingface.co/api/datasets"
_SPLITS = "https://datasets-server.huggingface.co/splits"
_FIRST = "https://datasets-server.huggingface.co/first-rows"


def _get(url: str):
    with urllib.request.urlopen(url, timeout=300) as response:
        return json.load(response)


def inspect(dataset: str) -> dict:
    quoted = urllib.parse.quote(dataset, safe="")
    info = _get(f"{_INFO}/{dataset}")
    licence = (info.get("cardData") or {}).get("license")
    splits = _get(f"{_SPLITS}?dataset={quoted}")["splits"]
    config, split = splits[0]["config"], splits[0]["split"]
    first = _get(
        f"{_FIRST}?dataset={quoted}"
        f"&config={urllib.parse.quote(config)}&split={urllib.parse.quote(split)}"
    )
    return {
        "dataset": dataset,
        "revision": info["sha"],
        "license": licence,
        "config": config,
        "split": split,
        "features": first["features"],
        "row": first["rows"][0]["row"] if first.get("rows") else {},
        "splits": [(s["config"], s["split"]) for s in splits],
    }


def _slug(dataset: str) -> str:
    return dataset.split("/")[-1].lower().replace("_", "-")[:28]


def _propose(found: dict) -> dict:
    sys.path.insert(0, str(__file__.rsplit("/", 1)[0]))
    from audit_any import propose_roles

    return propose_roles(found["features"], [found["row"]])


def render(found: dict, slug: str) -> str:
    roles = _propose(found)
    # propose_roles returns a list of candidates per role. Taking the list
    # itself produced `"outcome_field": "['correctness_count']"`, a spec
    # naming a column that cannot exist, which the first run caught.
    outcome_candidates = roles.get("outcome") or []
    outcome = outcome_candidates[0] if outcome_candidates else "REPLACE_ME"
    # A second outcome column on the same rows is what makes an instrument
    # measurable rather than assumed, so it is worth naming when there is one.
    cross = outcome_candidates[1] if len(outcome_candidates) > 1 else None
    names = [f["name"] for f in found["features"]]
    identifier = next(
        (n for n in ("id", "instance_id", "uuid", "task_id") if n in names),
        names[0] if names else "id",
    )
    cross_literal = f'"{cross}"' if cross else "None"

    others = ", ".join(outcome_candidates[2:]) or "none"
    return f'''# proposed outcome column: {outcome}
# second outcome column, if the roles were guessed right: {cross or "none"}
# other candidates the guesser saw: {others}

=== 1. freeze spec: paste into SPECS in research/corpus/freeze.py

    "{slug}": {{
        "dataset": "{found['dataset']}",
        "config": "{found['config']}",
        "split": "{found['split']}",
        "expected_rows": REPLACE_WITH_THE_COUNT,   # declared up front, so a
                                                   # short freeze is an error
        "outcome_field": "{outcome}",
        "cross_field": {cross_literal},
        "extract": _{slug.replace("-", "_")},
        "license": "{found['license']}",
    }},

=== 2. extractor: paste above SPECS. Content-free, or the sweep fails the build

def _{slug.replace("-", "_")}(row: dict) -> dict:
    """Hashes, labels, counts and identifiers. Never a message, a patch, a
    prompt or a log: the content sweep in tests/test_corpus.py fails the
    build on a forbidden key, and a hash of a truncated cell is a hash of
    nothing."""
    return {{
        "id": row.get("{identifier}"),
        "outcome": row.get("{outcome}"),
        "cross": row.get({cross_literal}) if {cross_literal} else None,
        # add the small scalars your finding needs, and a SHA-256 of any
        # content you are refusing to copy
    }}

=== 3. upstream verifier: nothing to write

Registering in SPECS gives it one. `verify_corpus.VERIFIERS` covers every
SPECS slug through the shared `verify`, so `make verify-corpus` will
re-derive rows from source once the freeze lands. If this dataset's rows API
cannot serve it, you need a standalone freezer and a verifier of your own;
see `_verify_cogym` for the shape.

=== 4. findings record: append to research/findings.json

  {{
    "id": "AEL-2026-REPLACE",
    "date": "REPLACE",
    "status": "standing",
    "kind": "defect | measurement | clean",
    "dataset": "{found['dataset']}",
    "revision": "{found['revision']}",
    "statement": "What you found, with the interval if it is a rate.",
    "figures": {{}},
    "verify": "make corpus",
    "action": "What a reader using this dataset should do differently.",
    "scope": "What this does not claim. Longer than forty characters, and a
              test enforces that, because an unbounded finding gets quoted
              out of context."
  }}

=== 5. tests: add to tests/test_findings.py

    def test_REPLACE_the_{slug.replace("-", "_")}_figures(self) -> None:
        from corpus_report import {slug.replace("-", "_")}_summary

        summary = {slug.replace("-", "_")}_summary()
        published = _figures("AEL-2026-REPLACE")
        # every published figure recomputed from the frozen evidence
        self.assertEqual(published["rows"], summary["rows"])
        # and at least one guard proven to fire when the evidence is wrong

=== what is left for you, and it is the only part that matters

  [ ] the expected row count, so a short freeze is an error
  [ ] the extractor's fields: what your finding actually needs
  [ ] the base rate, before any suspicion becomes a claim. "Resolved rows
      with empty patches" died here when empty patches turned out equally
      common among failures
  [ ] a verification pass against upstream for anything accusatory
  [ ] the statement, the action, and the scope
  [ ] one guard proven non-vacuous by corrupting the evidence and watching
      it fail

Proposed roles are guesses from column names and value shapes. Read them.
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", help="owner/name on the Hugging Face hub")
    parser.add_argument("--slug", help="short name for the corpus entry")
    args = parser.parse_args(argv)

    try:
        found = inspect(args.dataset)
    except urllib.error.HTTPError as error:
        print(
            f"could not read {args.dataset}: HTTP {error.code}. The datasets "
            "API rate-limits sustained use and returns 500 for some datasets "
            "it cannot serve; wait and retry, and if it persists the dataset "
            "needs a standalone freezer and a verifier of its own rather "
            "than a SPECS entry.", file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as error:
        print(f"could not reach the hub: {error.reason}", file=sys.stderr)
        return 1
    if not found["license"]:
        print(
            f"{args.dataset} declares no licence. The corpus cannot publish "
            "derived metadata from a dataset whose terms are unstated, so "
            "there is nothing to scaffold. This is a blocker, not a warning.",
            file=sys.stderr,
        )
        return 1
    slug = args.slug or _slug(args.dataset)
    print(f"# {found['dataset']}  revision {found['revision'][:8]}  "
          f"licence {found['license']}")
    print(f"# {len(found['splits'])} config/split pair(s); scaffolding "
          f"{found['config']}/{found['split']}")
    print(render(found, slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())
