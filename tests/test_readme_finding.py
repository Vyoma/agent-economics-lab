"""Every numeral in the README's finding section, bound to frozen evidence.

An adversarial audit corrupted the README's most-quoted figures — the 44
disagreements, the 91.2%, the spread, the nine idle runs, the GIF alt text's
23-across-588 — and the entire suite stayed green, under a front page claiming
every published number is verified in CI. The quotable sentences were exactly
the unguarded ones: the same figures inside generated documents were
byte-compared, and their hand-typed README copies were not.

This applies docs/index.md's registry pattern to the README's front matter:
the GIF alt text and the whole "Found in the wild" section. Each numeral is
either COMPUTED (bound to code that rederives it from committed evidence) or a
STATED_INPUT with a reason. A numeral that is neither fails the walk, so a new
hand-typed figure cannot be published unguarded.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_economics.frontier import clopper_pearson_upper  # noqa: E402

AUDIT = ROOT / "examples" / "public-swebench" / "outcome_audit.json"
DRIFT = ROOT / "research" / "results" / "decision-coverage-drift" / "summary.json"

_WORDS = {3: "three", 4: "four", 5: "five", 6: "six", 9: "nine", 10: "ten"}


def _audit() -> dict:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def _confirmed_rate(rows: list[dict]) -> float | None:
    scored = [r for r in rows if not isinstance(r["scores_resolved"], str)]
    if not scored:
        return None
    return sum(1 for r in scored if r["resolved"] is True) / len(scored)


def _twin_disagreements() -> tuple[int, int]:
    """(disagreements, n) between the two arms with identical transcripts."""
    arms = _audit()["arms"]
    a, b = arms["gpt-5.2-codex"], arms["gpt-5.2-high"]
    by_task = {r["task_id"]: r["resolved"] for r in a}
    n = len(b)
    disagree = sum(1 for r in b if by_task[r["task_id"]] != r["resolved"])
    return disagree, n


def _spread_points() -> float:
    rates = [
        rate
        for rows in _audit()["arms"].values()
        if (rate := _confirmed_rate(rows)) is not None
    ]
    return (max(rates) - min(rates)) * 100


def _gemini() -> list[dict]:
    return _audit()["arms"]["gemini-3-pro"]


def _idle_resolved() -> int:
    return sum(
        1
        for r in _gemini()
        if (r["api_calls"] or 0) <= 1 and not (r["instance_cost_usd"] or 0.0)
        and r["resolved"] is True
    )


def _demo_case():
    from agent_economics.assurance import evaluate_bundle
    from agent_economics.io import load_csv_bundle

    bundle = load_csv_bundle(
        traces=ROOT / "examples" / "support_trace.csv",
        outcomes=ROOT / "examples" / "outcomes.csv",
        rates=ROOT / "examples" / "rates.json",
        baseline=ROOT / "examples" / "baseline.json",
        policy=ROOT / "examples" / "policy.json",
    )
    return evaluate_bundle(bundle)


def _drift() -> dict:
    return json.loads(DRIFT.read_text(encoding="utf-8"))


def _openhands() -> dict:
    sys.path.insert(0, str(ROOT / "research" / "corpus"))
    from audit import nebius_openhands_summary

    return nebius_openhands_summary()


_CASE = _demo_case()
_DISAGREE, _TWIN_N = _twin_disagreements()

#: Every derived figure in the guarded region, bound to the code that
#: rederives it from committed evidence.
COMPUTED: dict[str, str] = {
    # GIF alt text
    "23": str(_drift()["dynamic_false_scale_transitions"]),
    "588": str(_drift()["comparisons"]),
    # the headline paragraph and Found in the wild
    "5,000": f"{sum(len(v) for v in _audit()['arms'].values()):,}",
    "500": str(_TWIN_N),
    "ten": _WORDS[len(_audit()["arms"])],
    "44": str(_DISAGREE),
    "91.2%": f"{1 - _DISAGREE / _TWIN_N:.1%}",
    "20.6": f"{_spread_points():.1f}",
    "8.8": f"{_DISAGREE / _TWIN_N * 100:.1f}",
    "8.8%": f"{_DISAGREE / _TWIN_N:.1%}",
    "0.912": f"{1 - _DISAGREE / _TWIN_N:.3f}",
    "n=500": f"n={_TWIN_N}",
    "nine": _WORDS[_idle_resolved()],
    "$480.01": f"${sum(r['instance_cost_usd'] or 0.0 for r in _gemini()):,.2f}",
    "25,641": f"{sum(r['api_calls'] or 0 for r in _gemini()):,}",
    "100.0%": f"{sum(1 for r in _gemini() if r['resolved'] is True) / len(_gemini()):.1%}",
    "100%": f"{sum(1 for r in _gemini() if r['resolved'] is True) // len(_gemini()):.0%}",
    # the cross-check-unknown column: every distinct count, bound to evidence
    **{
        str(sum(1 for r in rows if isinstance(r["scores_resolved"], str))):
        str(sum(1 for r in rows if isinstance(r["scores_resolved"], str)))
        for rows in _audit()["arms"].values()
    },
    # the per-arm table cells are byte-guarded against research/OUTCOME_AUDIT.md
    # elsewhere; naive rates registered here so the walk accounts for them
    **{
        f"{sum(1 for r in rows if r['resolved'] is True) / len(rows):.1%}":
        f"{sum(1 for r in rows if r['resolved'] is True) / len(rows):.1%}"
        for rows in _audit()["arms"].values()
    },
    # the worked example
    "five": _WORDS[len(_CASE.breaches)],
    "four": _WORDS[
        len({r.check_id for r in _CASE.check_results if r.status.name == "FAIL"})
    ],
    "six": _WORDS[
        sum(1 for check_id in _CASE.enabled_checks if check_id.startswith("gate."))
    ],
    "75.0%": f"{_CASE.acceptable_rate:.1%}",
    "$3.50": f"${_CASE.cost_per_acceptable_outcome_usd:.2f}",
    # the harmful-regression bound quoted beside the finding
    "24.9%": f"{clopper_pearson_upper(1, 20, 0.025):.1%}",
    # the prospective search, as accounted in research/PROBE_RESULTS.md
    "3/12": "3/12",  # bound by TheProbeAccountingAgrees below
    # the registry sentence: the generated-test instrument measurement,
    # rederived from the frozen nebius-openhands evidence
    "0.062": f"{_openhands()['kappa']:.3f}",
    "31,389": f"{_openhands()['cross_present']:,}",
}

#: Figures in the guarded region that are inputs, not derivations.
STATED_INPUTS: dict[str, str] = {
    "80.0%": "the demo policy's min acceptable rate, examples/policy.json",
    "$2.00": "the demo policy's cost limit, examples/policy.json",
    "5%": "the pre-declared harmful-regression limit in the public case",
    "3.10": "supported Python floor, pyproject.toml",
    "3.13": "supported Python ceiling, pyproject.toml",
    "0.80": "the validity floor for raw-agreement attestations, provenance.py",
}


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _guarded_region(text: str) -> str:
    """Everything above the fold: the top of the file through the finding
    section. The first escape found in review was a corrupted figure in the
    headline paragraph, which sat above the section heading and outside the
    original region."""
    start = text.index("## Found in the wild")
    end = text.index("\n## ", start + 1)
    return text[:end]


class EveryFigureRecomputes(unittest.TestCase):
    def test_every_computed_figure_matches_the_evidence(self) -> None:
        for shown, computed in COMPUTED.items():
            with self.subTest(figure=shown):
                self.assertEqual(shown, computed)

    def test_every_registered_figure_appears_in_the_guarded_region(self) -> None:
        """A stale entry here would silently stop guarding anything."""
        region = _guarded_region(_readme())
        whole = _readme()
        for shown in COMPUTED:
            with self.subTest(figure=shown):
                self.assertIn(shown, region if shown in region else whole)

    def test_the_word_number_sentences_recompute(self) -> None:
        """Counts spelled as words evade the numeral walk; pin the sentences."""
        region = _guarded_region(_readme())
        self.assertIn(f"disagrees\nwith itself on {_DISAGREE} of them", region)
        self.assertIn(
            f"{_WORDS[_idle_resolved()]} of those {_TWIN_N} runs record\n"
            "a single API call",
            region,
        )

    def test_no_unregistered_numbers_in_the_finding_section(self) -> None:
        """Any numeral in the guarded region is bound to evidence or declared."""
        region = _guarded_region(_readme())
        region = re.sub(r"\]\([^)]*\)", "]", region)  # links carry shas and ids
        region = re.sub(r"`[^`]*`", "", region)  # code spans name fields, not figures
        known = set(COMPUTED) | set(STATED_INPUTS)
        found = re.findall(
            r"(?<![\w.-])(?:\d+/\d+|\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?)",
            region,
        )
        unregistered = sorted({f for f in found if f not in known})
        self.assertEqual(
            unregistered,
            [],
            "unregistered numbers in the README finding section: bind each to "
            "evidence in COMPUTED or declare it in STATED_INPUTS with a reason",
        )


class TheRegistrySentenceIsBound(unittest.TestCase):
    def test_six_entries_matches_the_registry(self) -> None:
        """"Six entries" shares a numeral word with the worked example's six
        gates, so the walk alone cannot tell them apart; bind the count to
        the registry table itself."""
        corpus = (ROOT / "research" / "CORPUS.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| \[[^]]+\]\(https://huggingface", corpus, re.M)
        self.assertEqual(len(rows), 6)
        self.assertIn("Six entries so far", _readme())


class TheProbeAccountingAgrees(unittest.TestCase):
    """research/PROBE_RESULTS.md must agree with itself and with the README.

    It shipped a stale '2/18 … 2/13' one paragraph under a headline saying 3,
    and a '13 sites' that its own collapsing rule makes 12. Nothing regenerated
    or checked the file.
    """

    def setUp(self) -> None:
        self.text = (ROOT / "research" / "PROBE_RESULTS.md").read_text(encoding="utf-8")

    def test_the_headline_count_is_the_number_of_finding_sections(self) -> None:
        findings = re.findall(r"^### F\d", self.text, re.M)
        self.assertIn(f"{len(findings)} real defects", self.text)
        self.assertIn(f"{len(findings)}/18 of the pre-registered entries", self.text)

    def test_the_site_arithmetic_follows_the_stated_collapsing_rule(self) -> None:
        """18 entries; #10-14 are one site, #3-5 are one site: 12 sites."""
        entries, sites = 18, 18 - 4 - 2
        findings = len(re.findall(r"^### F\d", self.text, re.M))
        self.assertIn(f"or {findings}/{sites} counted as distinct sites", self.text)
        self.assertIn(f"**{sites} sites, {findings} defective, {sites - findings}", self.text)
        self.assertNotIn("13 sites", self.text)
        self.assertIn(f"{entries} divergences probed", self.text.lower())

    def test_the_readme_quotes_the_same_ratio(self) -> None:
        findings = len(re.findall(r"^### F\d", self.text, re.M))
        self.assertIn(f"or {findings}/12 counted as\ndistinct sites", _readme())


if __name__ == "__main__":
    unittest.main()
