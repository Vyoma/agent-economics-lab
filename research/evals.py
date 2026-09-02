"""Render research/EVALS.md: one scorecard for the instrument itself.

The eval artifacts already exist — mutation score, coverage-drift
conformance, evidence ablation, the catalogued green defects, the
pre-registered prospective search, the corpus, the claim ledger — but a
reader asking the only question that matters, "how good is the auditor?",
had to assemble the answer from seven files. This renders the assembly,
computing every figure from the frozen artifact that owns it and quoting
each experiment's own claim-boundary text, because a scorecard that
aggregates numbers while shedding their limits is how instruments start
grading themselves on a curve.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research" / "results"


def _load(name: str) -> dict:
    return json.loads((RESULTS / name / "summary.json").read_text(encoding="utf-8"))


def render() -> str:
    mutation = _load("mutation-score")
    drift = _load("decision-coverage-drift")
    ablation = _load("evidence-ablation")

    substitution = mutation["operators"]["substitution"]

    sys.path.insert(0, str(ROOT / "research"))
    from green_defects import DEFECTS

    probe_results = (ROOT / "research" / "PROBE_RESULTS.md").read_text(encoding="utf-8")
    headline = re.search(
        r"\*\*(\d+) divergences probed\. (\d+) real defects, at (\d+) distinct sites\.\*\*",
        probe_results,
    )
    assert headline, "PROBE_RESULTS.md headline moved; update the pattern"
    probed, real, sites = (int(g) for g in headline.groups())

    corpus = (ROOT / "research" / "CORPUS.md").read_text(encoding="utf-8")
    registry_rows = re.findall(r"^\| \[[^]]+\]\(https://huggingface", corpus, re.M)
    clean_rows = len(re.findall(r"\| clean[ :]", corpus))

    claims = sorted((ROOT / "research" / "claims").glob("*.claim.json"))

    lines = [
        "# How good is the instrument?",
        "",
        "The scorecard for the auditor itself, every figure computed from the",
        "frozen artifact that owns it, every experiment's own claim boundary",
        "kept attached. Regenerate with `make evals`; each source is",
        "byte-compared in `make reproduce`, so this page cannot drift from",
        "the evidence it summarises.",
        "",
        "| question | measurement | figure | what it does not establish |",
        "|---|---|---:|---|",
        (
            "| Does a gutted gate survive? | substitution mutants (same id,"
            " version, coverage, route; enforcing nothing) | "
            f"{substitution['fixed_contract_killed']}/{substitution['scored_mutants']}"
            " killed by decision change; all"
            f" {substitution['contract_digest_changed']} of"
            f" {substitution['mutants']} changed the contract digest, so no"
            " substitution is silent |"
            " synthetic conformance fixture, not harness hardness in the"
            " field |"
        ),
        (
            "| Does required coverage vanish with its gate? |"
            f" {drift['comparisons']} disable-one-gate comparisons |"
            f" fixed contract: {drift['fixed_contract_false_scale_transitions']}"
            " false SCALE; dynamic coverage:"
            f" {drift['dynamic_false_scale_transitions']} | conformance on"
            " synthetic bundles, not a production prevalence estimate |"
        ),
        (
            "| Does deleting raw evidence go unnoticed? |"
            f" {ablation['ablation_count']} evidence ablations |"
            f" {ablation['operational_refusals']} refused outright;"
            f" {ablation['false_scale_transitions']} ASSIST->SCALE transitions"
            " exposing two documented source-contract gaps | the gaps are"
            " boundary cases, recorded in the protocol, not a failure rate |"
        ),
        (
            "| Do the catalogued defects have discriminating probes? |"
            f" {len(DEFECTS)} green defects, each re-run at its pinned"
            " pre-fix commit | every probe fails before the fix and passes"
            " after (`make green-defects`) | catalogued means found once;"
            " it is not a census of what remains |"
        ),
        (
            "| Does prospective search find anything? | pre-registered site"
            f" list, committed before probing | {probed} divergences probed,"
            f" {real} real defects at {sites} distinct sites | the count was"
            " published wrong twice (in the flattering direction both"
            " times); PROBE_RESULTS.md keeps that history |"
        ),
        (
            "| Does it work on data it did not produce? |"
            f" {len(registry_rows)} public datasets audited |"
            f" {len(registry_rows) - clean_rows} with verified findings,"
            f" {clean_rows} clean bill | an arm name identifies runs in a"
            " dataset, never a measurement of a model |"
        ),
        (
            "| Do the published claims still verify? |"
            f" {len(claims)} claims in the ledger | `make ledger` fails the"
            " build on any REFUTED or unpinned-UNVERIFIED claim | verification"
            " binds evidence digests, not the truth of the world |"
        ),
        "",
        "## Reading it honestly",
        "",
        "Three of these rows are conformance against synthetic fixtures the",
        "harness itself generated; they establish that the contract behaves",
        "as specified, not that the specification catches everything that",
        "matters. The rows that carry field weight are the last three: real",
        "defects found by pre-registered search in this codebase, real",
        "findings in third-party data that reproduce from upstream, and a",
        "ledger where a refuted claim is a permanent red build until",
        "retracted. The evidence-ablation row records the instrument's two",
        "known blind spots in its own scorecard, because an eval suite that",
        "cannot embarrass its subject is advertising.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
