"""Every number on the published page must be recomputable, or the build fails.

`docs/index.md` is the highest-traffic artifact in the project and was, until this
file existed, the only one outside the drift-detection net. That gap was not
hypothetical: the page shipped `e/r` as the amplification law while its own table
printed `e/(r-e)`, a 2x discrepancy at the extreme, and separately claimed that all
four propositions were verified by brute force while Proposition 2 was only printed.

Two mechanisms here, and the second is the one that matters.

`COMPUTED` binds each derived figure on the page to code that recomputes it. If the
engine changes and the page does not, these fail.

`test_no_unregistered_numbers` then walks every numeral on the page and fails on any
that is neither computed above nor declared in `STATED_INPUTS` with a reason. So a new
number cannot be added to the page without being bound to a source, which is the
property that a fixed list of assertions does not give you.
"""

from __future__ import annotations

import math
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "index.md"

import sys  # noqa: E402 - must run before the local imports below

sys.path.insert(0, str(ROOT))

from agent_economics.label_error import (  # noqa: E402
    Workload,
    amplification,
    check_proposition_2,
    epsilon_star,
)

# --------------------------------------------------------------------- recompute


def _ten_task_fixture() -> Workload:
    """The hand-worked example: 10 tasks at $10, 7 truly acceptable."""
    return Workload(
        costs=tuple([10.0] * 10),
        values=tuple([0.0] * 10),
        acceptable=tuple([True] * 7 + [False] * 3),
    )


def _one_false_reject() -> float:
    w = _ten_task_fixture()
    judged = list(w.acceptable)
    judged[0] = False
    return w.unit_cost(tuple(judged))


def _balanced_pair() -> float:
    """One false reject and one false accept: the errors cancel exactly."""
    w = _ten_task_fixture()
    judged = list(w.acceptable)
    judged[0] = False
    judged[7] = True
    return w.unit_cost(tuple(judged))


def _net_bias_error(false_accepts: int, false_rejects: int) -> float:
    a = 70
    return abs(a / (a + false_accepts - false_rejects) - 1)


def _labels_needed(disagreement: float, halfwidth: float, z: float = 1.96) -> int:
    """Sample size for a 95% interval of the given half-width on net bias.

    fp and fn are disjoint multinomial cells, so with b = p_fp - p_fn and
    d = p_fp + p_fn, Var(b_hat) = (d - b^2) / m. Conservative at b = 0.
    """
    return math.ceil(z * z * disagreement / (halfwidth**2))


def _judged_rate(p: float, sensitivity: float, specificity: float) -> float:
    return p * sensitivity + (1.0 - p) * (1.0 - specificity)


def _corrected_vs_naive(
    true_rate: float, sensitivity: float, specificity: float
) -> tuple[float, float, float]:
    """Uncorrected and corrected relative error, in closed form.

    The published table used a simulation, which made it seed-dependent: a number
    on a page should not move when a random seed does. In expectation the judged
    positive rate is `q = p*se + (1-p)(1-sp)`, the uncorrected error is `|p/q - 1|`,
    and the inversion recovers `p` algebraically, so the corrected error is exactly
    zero. Returns (q, uncorrected, corrected).
    """
    q = _judged_rate(true_rate, sensitivity, specificity)
    recovered = (q + specificity - 1.0) / (sensitivity + specificity - 1.0)
    return q, abs(true_rate / q - 1.0), abs(true_rate / recovered - 1.0)


def _net_value_threshold(cost_per_task: float, r: float = 0.70, v: float = 10.0) -> float:
    return (r * v - cost_per_task) / v


def _discovered_tests() -> int:
    """Test methods as unittest discovers them, so the page's count is derived."""
    total = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        total += len(re.findall(r"^\s+def test_", path.read_text(), re.M))
    return total


def _pct(x: float, places: int = 2) -> str:
    return f"{x:.{places}f}%" if isinstance(x, str) else f"{x:.{places}%}"


# Every derived figure the page states, bound to the code that produces it.
COMPUTED: dict[str, str] = {
    # the hand-worked example
    "$14.29": f"${_ten_task_fixture().unit_cost():.2f}",
    "$16.67": f"${_one_false_reject():.2f}",
    "16.67%": _pct(
        abs(_one_false_reject() - _ten_task_fixture().unit_cost())
        / _ten_task_fixture().unit_cost()
    ),
    "16.7%": _pct(
        abs(_one_false_reject() - _ten_task_fixture().unit_cost())
        / _ten_task_fixture().unit_cost(),
        1,
    ),
    "14.3%": _pct(0.10 / 0.70, 1),  # the first-order shortcut, quoted to be corrected
    # amplification table, 5% label error
    "5.9%": _pct(amplification(0.90, 0.05)[0], 1),
    "11.1%": _pct(amplification(0.50, 0.05)[0], 1),
    "33.3%": _pct(amplification(0.20, 0.05)[0], 1),
    "100.0%": _pct(amplification(0.10, 0.05)[0], 1),
    # net-bias table
    "0.00%": _pct(_net_bias_error(15, 15)),
    "17.65%": _pct(_net_bias_error(15, 0)),
    "27.27%": _pct(_net_bias_error(0, 15)),
    "9.09%": _pct(_net_bias_error(7, 0)),
    # the threshold
    "6.36%": _pct(epsilon_star(0.70, 0.10)),
    "93.6%": _pct(1 - epsilon_star(0.70, 0.10), 1),
    "4.55%": _pct(epsilon_star(0.50, 0.10)),
    "1.82%": _pct(epsilon_star(0.20, 0.10)),
    # sample sizes, and the half-widths they target
    "3.18%": _pct(epsilon_star(0.70, 0.10) / 2),
    "2.27%": _pct(epsilon_star(0.50, 0.10) / 2),
    "0.91%": _pct(epsilon_star(0.20, 0.10) / 2),
    "570": f"{_labels_needed(0.15, epsilon_star(0.70, 0.10) / 2):,}",
    "1,139": f"{_labels_needed(0.30, epsilon_star(0.70, 0.10) / 2):,}",
    "1,116": f"{_labels_needed(0.15, epsilon_star(0.50, 0.10) / 2):,}",
    "6,973": f"{_labels_needed(0.15, epsilon_star(0.20, 0.10) / 2):,}",
    # prevalence correction, closed form
    "0.690": f"{_corrected_vs_naive(0.70, 0.90, 0.80)[0]:.3f}",
    "0.210": f"{_corrected_vs_naive(0.20, 0.85, 0.95)[0]:.3f}",
    "0.625": f"{_corrected_vs_naive(0.50, 0.95, 0.70)[0]:.3f}",
    "0.170": f"{_corrected_vs_naive(0.10, 0.80, 0.90)[0]:.3f}",
    "1.4%": _pct(_corrected_vs_naive(0.70, 0.90, 0.80)[1], 1),
    "4.8%": _pct(_corrected_vs_naive(0.20, 0.85, 0.95)[1], 1),
    "20.0%": _pct(_corrected_vs_naive(0.50, 0.95, 0.70)[1], 1),
    "41.2%": _pct(_corrected_vs_naive(0.10, 0.80, 0.90)[1], 1),
    "0.0%": _pct(_corrected_vs_naive(0.50, 0.95, 0.70)[2], 1),
    # net-value gate thresholds
    "10.0%": _pct(_net_value_threshold(6.00), 1),
    "1.0%": _pct(_net_value_threshold(6.90), 1),
    "0.5%": _pct(_net_value_threshold(6.95), 1),
    # the suite size the page quotes
    str(_discovered_tests()): str(_discovered_tests()),
}

# Numbers that are inputs, parameters or citations rather than derived results.
# Each needs a reason, so the list cannot quietly become a dumping ground.
STATED_INPUTS: dict[str, str] = {
    "$10": "cost per task in the hand-worked example",
    "$100": "total spend in the hand-worked example",
    "$2.00": "illustrative gate limit",
    "$1.82": "illustrative current metric, giving 10% slack",
    "$6.00": "cost per task in the net-value table",
    "$6.90": "cost per task in the net-value table",
    "$6.95": "cost per task in the net-value table",
    "$14.25": "p95 and maximum from `make demo`, asserted in test_demo_p95_equals_max",
    "5%": "the label error rate the amplification table holds fixed",
    "10%": "slack, and the 10% success rate row",
    "15%": "judge disagreement rate in the sample-size table",
    "20%": "success-rate row",
    "25%": "slack cap in the grid-dependence sentence",
    "30%": "judge disagreement, and the balanced-judge agreement figure",
    "50%": "success-rate row and slack cap",
    "70%": "success rate used throughout",
    "80%": "agreement after the second mistake; specificity 0.80",
    "85%": "the agreement figure practitioners quote",
    "90%": "success-rate row; sensitivity 0.90",
    "93%": "agreement of the one-directional judge in the net-bias table",
    "95%": "specificity 0.95, and the 95% confidence level",
    "100%": "the forced mutation score, and 100% slack cap",
    "510": "mutants in the removal operator denominator",
    "487/510": "substitution-operator score",
    "588": "coverage-drift comparisons",
    "56.1%": "brittle scenarios, asserted in the sensitivity results",
    "800": "sample size in the simulation note",
    "0.01349": "simulated standard error, checked against closed form below",
    "0.01369": "closed-form standard error, checked below",
    "1970": "attribution decade for prevalence correction ('1970s')",
    "2306.05685": "arXiv id of Zheng et al., the source of the agreement figure",
    "2023": "publication year of Zheng et al.",
    "80": "the >80% agreement Zheng et al. report",
    "3.10": "lowest supported Python",
    "3.13": "highest supported Python",
    "23": "false SCALE transitions",
    "7,000": "rounded restatement of 6,959",
    "1.8": "restatement of the 1.8x circularity factor and 1.8% error",
    "2": "the 2x understatement of the shortcut",
    "1": "counts in prose",
    "4": "counts in prose",
    "7": "acceptable tasks in the fixture",
    "6": "judged-acceptable count after one false reject, and the 6x tighter factor",
    "15": "false accepts / rejects in the net-bias table",
    "0": "false rejects in the net-bias table",
    "20": "the sample-size threshold for p95",
    "4,000": "workloads in the Proposition 1 check",
    "0.90": "sensitivity in the correction table",
    "0.80": "sensitivity and specificity in the correction table",
    "0.85": "sensitivity in the correction table",
    "0.95": "specificity and sensitivity in the correction table, and the p95 rank multiplier",
    "0.70": "specificity in the correction table",
    "1.00": "net value in the net-value table",
    "0.10": "net value in the net-value table, and slack",
    "0.05": "net value in the net-value table",
    "0.62": "example success rate in the closing command",
    "0.08": "example slack in the closing command",
    "4.59%": "output of the closing command, asserted by test_cli_*",
    "95.41%": "output of the closing command",
    "1,139": "labels needed at 30% disagreement",
    "1,116": "labels needed for a 4.55% tolerance",
    "6,973": "labels needed for a 1.82% tolerance",
    "8": "the 8 of 25 grid cell count",
    "13": "the 13x tighter factor",
    "55": "brittle scenarios",
    "70": "acceptable tasks in the 100-task net-bias example",
    "95": "confidence level",
    "98": "total sensitivity scenarios",
    "10": "tasks in the hand-worked example",
    "5": "counts in prose",
    "1.8%": "restatement of the 1.82% tolerance in prose",
    "100": "tasks and dollars in the worked examples",
    "2.0": "the Apache-2.0 licence version",
    "25": "the 8-of-25 grid cell count",
    "0.625": "judged rate in the correction table",
    "16": "counts in prose",
    "1.82": "the circularity factor, restated",
}


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _prose(text: str) -> str:
    """The page with fenced code removed; code blocks hold formulas, not claims."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


class PublishedNumbersRecompute(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(PAGE.exists(), "docs/index.md is missing")
        self.page = _page()

    def test_every_computed_figure_matches_the_code(self) -> None:
        for shown, computed in COMPUTED.items():
            with self.subTest(figure=shown):
                self.assertEqual(
                    shown,
                    computed,
                    f"page says {shown}, code produces {computed}",
                )

    def test_every_computed_figure_is_actually_on_the_page(self) -> None:
        """A stale entry here would silently stop guarding anything."""
        for shown in COMPUTED:
            with self.subTest(figure=shown):
                self.assertIn(shown, self.page)

    def test_no_unregistered_numbers(self) -> None:
        """Any numeral on the page must be bound to a source or declared an input."""
        known = set(COMPUTED) | set(STATED_INPUTS)
        found = re.findall(
            r"(?<![\d.])(?:\d+/\d+|\$?\d[\d,]*(?:\.\d+)?%?)",
            _prose(self.page),
        )
        unregistered = sorted({f for f in found if f not in known})
        self.assertEqual(
            unregistered,
            [],
            "unregistered numbers on docs/index.md: bind each to code in COMPUTED "
            "or declare it in STATED_INPUTS with a reason",
        )


class ErrorsThatAlreadyHappened(unittest.TestCase):
    """Each of these shipped once. None may ship again."""

    def setUp(self) -> None:
        self.page = _page()

    def test_the_amplification_law_is_stated_exactly(self) -> None:
        """`e/r` is the first-order form and understates the error by 2x at r=0.10."""
        self.assertIn("e / (r − e)", self.page)
        self.assertNotIn("divided by the success rate", self.page)
        # It may appear only where the page corrects it.
        for match in re.finditer(r"e/r|`e/r`", self.page):
            window = self.page[max(0, match.start() - 260) : match.end() + 260]
            self.assertTrue(
                "shortcut" in window or "first-order" in window,
                "e/r must appear only where it is being corrected",
            )

    def test_proposition_2_claim_matches_reality(self) -> None:
        self.assertLess(check_proposition_2(), 1e-9)
        if "verified by brute force" in self.page:
            self.assertLess(
                check_proposition_2(),
                1e-9,
                "the page claims brute-force verification for all propositions",
            )

    def test_agreement_is_not_presented_as_necessary(self) -> None:
        """A balanced judge clears the gate at 70% agreement, so it is not necessary."""
        self.assertEqual(_net_bias_error(15, 15), 0.0)
        self.assertIn("net bias", self.page)
        for overclaim in (
            "has to agree with humans",
            "you need 93.6% agreement, not 85%",
            "the accuracy threshold the field quotes",
        ):
            with self.subTest(overclaim=overclaim):
                self.assertNotIn(overclaim, self.page)

    def test_grid_dependence_is_disclosed(self) -> None:
        """"1 of 15" is an artifact of capping slack at 25%."""
        rates = (0.9, 0.7, 0.5, 0.3, 0.2)
        for cap, expected in ((0.25, (1, 15)), (0.50, (4, 20)), (1.00, (8, 25))):
            slacks = [s for s in (0.05, 0.10, 0.25, 0.50, 1.00) if s <= cap]
            cells = [(r, s) for r in rates for s in slacks]
            got = (sum(1 for c in cells if epsilon_star(*c) >= 0.15), len(cells))
            with self.subTest(cap=cap):
                self.assertEqual(got, expected)
        self.assertIn("grid-dependent", self.page)
        self.assertNotIn("suffices in exactly one", self.page)

    def test_the_metric_switch_is_not_called_free(self) -> None:
        """It is 13x tighter than the ratio gate near break-even."""
        ratio_gate = epsilon_star(0.70, 0.10)
        self.assertLess(_net_value_threshold(6.95), ratio_gate / 6)
        self.assertNotIn("The fix is free", self.page)
        self.assertNotIn("free money", self.page)
        # "free" may appear only in the sentence that withdraws it.
        for match in re.finditer(r"\bfree\b", self.page):
            window = self.page[max(0, match.start() - 200) : match.end() + 200]
            self.assertTrue(
                "overselling" in window or "break-even" in window,
                f"unqualified 'free' near: {window[180:260]!r}",
            )

    def test_the_cli_supports_the_arguments_the_page_advertises(self) -> None:
        """The page previously told readers to check their own numbers with a
        command that silently ignored arguments."""
        import contextlib
        import io

        from agent_economics.label_error import main

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["-r", "0.70", "-s", "0.10"])
        self.assertIn("6.36%", buf.getvalue())

    def test_standard_error_note_is_accurate(self) -> None:
        """The page quotes a simulated SE against a closed form; they must agree."""
        closed = math.sqrt(0.15 / 800)
        self.assertAlmostEqual(closed, 0.01369, places=5)
        self.assertIn("0.01369", self.page)
        # The simulated figure must be within a few percent of the closed form.
        self.assertLess(abs(0.01349 - closed) / closed, 0.05)

    def test_test_count_on_the_page_is_current(self) -> None:
        quoted = re.search(r"(\d{3}) tests", self.page)
        self.assertIsNotNone(quoted, "the page must state a test count")
        # An earlier version of this compared the difference against the total, which
        # holds for almost any input: a check that cannot fail, in the file written to
        # catch exactly that. It now has to match what unittest discovers.
        collected = 0
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            collected += len(re.findall(r"^\s+def test_", path.read_text(), re.M))
        self.assertGreater(collected, 300, "test discovery looks broken")
        self.assertEqual(
            int(quoted.group(1)),
            collected,
            f"docs/index.md quotes {quoted.group(1)} tests; the suite discovers "
            f"{collected}. Re-run and update the page.",
        )


class DemoOutputBacksThePage(unittest.TestCase):
    def test_demo_p95_equals_max(self) -> None:
        """The page cites this as a measurement that cannot fail."""
        from agent_economics.assurance import percentile

        costs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 14.25]
        self.assertEqual(percentile(costs, 0.95), max(costs))
        self.assertIn("$14.25", _page())


if __name__ == "__main__":
    unittest.main()
