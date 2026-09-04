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


#: Shipped capabilities carrying no outcome figure in the table above. The
#: guard in tests/test_evals.py enumerates the capabilities the build
#: actually exposes and fails when one is neither measured nor listed here,
#: so a new capability cannot arrive unmeasured and unmentioned.
UNMEASURED: dict[str, str] = {
    "experiment.paired-budget-frontier@1": "its statistical kernel is "
    "verified against closed forms (row above), but the frozen study is "
    "synthetic. Its protocol names the exit criterion: a permissioned "
    "matched-task study from a real workflow, three or more configurations, "
    "100+ paired task digests, and an independent reproduction.",
    "kimi-analyst@1": "no evaluation at all. It recommends fixes from a "
    "decided case, and nothing measures whether the recommendations are "
    "sound. Closing it means a labelled set of decided cases with expert "
    "remediations to score against - the same shape as the judge eval in "
    "research/eval/judge-eval-set.json, which exists and which the row "
    "above reports; no equivalent set exists for remediations.",
}


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
    # Counted from the findings registry's own `kind`, not by matching the
    # word "clean" in the corpus prose. The regex version matched "clean
    # labels" in the row whose finding is kappa 0.062, and so filed this
    # project's sharpest result as a clean bill - in a generated,
    # byte-compared page, which shipped it green.
    registry = json.loads(
        (ROOT / "research" / "findings.json").read_text(encoding="utf-8")
    )
    standing = [f for f in registry["findings"] if f["status"] == "standing"]
    clean_datasets = {f["dataset"] for f in standing if f["kind"] == "clean"}
    finding_datasets = {f["dataset"] for f in standing if f["kind"] != "clean"}

    claims = sorted((ROOT / "research" / "claims").glob("*.claim.json"))

    sys.path.insert(0, str(ROOT / "research"))
    from adapter_fidelity import measure, token_reconciliation

    paths = measure()
    reconciliation = token_reconciliation()
    orphaned = sum(len(r["orphaned"]) for r in paths.values())
    units = sum(r["source"] for r in paths.values())

    judge = json.loads(
        (ROOT / "research" / "eval" / "judge-eval-set.json").read_text(
            encoding="utf-8"
        )
    )
    # Version 1, deliberately, not the later 25/25. The eval set's own notes
    # record that a case was restructured after observing this judge, so the
    # later run is partly informed by the model under test; the untouched
    # set is the stronger evidence and the weaker number.
    first = next(
        run for run in judge["measured_runs"] if str(run["eval_version"]) == "1"
    )

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
            f" {len(finding_datasets)} with verified findings,"
            f" {len(clean_datasets)} clean | an arm name identifies runs in a"
            " dataset, never a measurement of a model |"
        ),
        (
            "| Do the published claims still verify? |"
            f" {len(claims)} claims in the ledger | `make ledger` fails the"
            " build on any REFUTED or unpinned-UNVERIFIED claim | verification"
            " binds evidence digests, not the truth of the world |"
        ),
        (
            "| Does anything vanish on the way in? | every source unit in"
            " each of the four ingestion paths, cited by a decoded entity or"
            " named as excluded |"
            f" {orphaned} of {units} units orphaned; session-tree spend"
            " reconciles to the bundle with residual"
            f" {reconciliation['residual_in']}/{reconciliation['residual_out']}"
            " tokens | the repository's own fixtures, which are small and"
            " were written here; it is conservation, not field-level"
            " fidelity |"
        ),
        (
            "| How good is the shipped judge (`kimi-judge@1`)? | agreement"
            " with hand-authored"
            f" rubric-derived labels, {judge['case_count']}"
            " constructed cases |"
            f" {first['agreement_rate']:.1%} agreement,"
            f" {first['false_accept_rate']:.0%} false-accept (eval-version 1)"
            " | not accuracy against production ground truth; constructed"
            " cases are easier than real ones, and the later 100% run is"
            " excluded here because the set was edited after seeing this"
            " judge |"
        ),
        (
            "| Does the rendered case keep what decided it? |"
            " completeness of `renderer.markdown@1` and `renderer.json@1`"
            " against a case with simultaneous breaches | every breach,"
            " check id, status, failure route and both digests reach the"
            " page; proven non-vacuous by stripping both carriers | the"
            " information is present, not that a reader draws the right"
            " conclusion from it; and it is one constructed case, not every"
            " shape a case can take |"
        ),
        (
            "| Does a comparison report keep every arm and refusal? |"
            " completeness of `renderer.frontier-markdown@1`,"
            " `renderer.frontier-json@1` and"
            " `renderer.frontier-svg@1` against the"
            " frozen four-arm case | every arm named, every refusal carrying"
            " its reason, both digests per arm, the post-selection caveat"
            " intact, and the chart plotting exactly as many points as there"
            " are arms | structural presence only: whether a chart misleads"
            " a human eye is not something a test decides |"
        ),
        (
            "| Are the frontier statistics right? | Clopper-Pearson bound"
            " against its closed form, plus distribution and monotonicity"
            " properties | exact to 9 decimal places across every tested"
            " trial size and alpha (`tests/test_frontier_statistics.py`) |"
            " the statistical kernel only; the frozen frontier study itself"
            " is synthetic and labelled so in its protocol |"
        ),
        "",
        "## What is not measured",
        "",
        "A scorecard that lists only what it measures reads as though that is",
        "everything there is. These are the shipped capabilities with no",
        "outcome figure above, named so the coverage claim is total, each",
        "with what closing it would take:",
        "",
    ]
    for name, gap in sorted(UNMEASURED.items()):
        lines.append(f"- **`{name}`** - {gap}")
    lines += [
        "",
        "## Reading it honestly",
        "",
        "Several of these rows are conformance against synthetic fixtures",
        "the harness itself generated - the mutation, coverage-drift and",
        "ablation rows, and the ingestion row, whose fixtures were written",
        "here. They establish that the contract behaves as specified, not",
        "that the specification catches everything that matters.",
        "",
        "The rows carrying field weight are the ones measured against",
        "something this project did not author: real defects found by",
        "pre-registered search in this codebase, real findings in",
        "third-party data that reproduce from upstream, and a ledger where a",
        "refuted claim is a permanent red build until retracted.",
        "",
        "Two rows are deliberately the weaker number. The judge row publishes",
        "95.8% rather than the later 100%, because the later eval set was",
        "edited after observing the judge under test. The ablation row",
        "records the instrument's two known blind spots. An eval suite that",
        "cannot embarrass its subject is advertising.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
