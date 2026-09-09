"""The scaffold must emit code that runs, and refuse what the contract bars.

Landing a corpus entry means a freeze spec, an extractor, a verifier, a
findings record and recomputation tests: roughly six hundred lines whose
shape the contract already fixes. That boilerplate is the distance between
someone noticing a defect in public data and a finding anyone can cite, and
it is the reason the registry has one contributor.

A scaffold that emits code which does not parse is worse than none, because
it costs the reader the time to find out. These run it against a schema
fixture, with no network, and check what it produced.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "corpus"))

#: A schema fixture, not a dataset. It describes the shape the scaffold
#: reads, so these tests never touch the network.
FIXTURE = {
    "dataset": "example-org/example-trajectories",
    "revision": "0123456789abcdef0123456789abcdef01234567",
    "license": "apache-2.0",
    "config": "default",
    "split": "train",
    "features": [
        {"name": "instance_id", "type": {"dtype": "string", "_type": "Value"}},
        {"name": "resolved", "type": {"dtype": "bool", "_type": "Value"}},
        {"name": "reward", "type": {"dtype": "float64", "_type": "Value"}},
        {"name": "messages", "type": {"dtype": "string", "_type": "Value"}},
    ],
    "row": {
        "instance_id": "example__repo-1",
        "resolved": True,
        "reward": 1.0,
        "messages": "a transcript the freeze must never copy",
    },
    "splits": [("default", "train")],
}


def _emitted(section: str, text: str) -> str:
    block = text.split(section)[1]
    return block[block.index("def _"):block.index("=== 3.")]


class TheScaffoldEmitsCodeThatRuns(unittest.TestCase):
    def setUp(self) -> None:
        import scaffold_entry

        self.text = scaffold_entry.render(FIXTURE, "example-trajectories")

    def test_the_extractor_parses(self) -> None:
        ast.parse(_emitted("=== 2. extractor", self.text))

    def test_the_extractor_runs_on_a_row_of_that_shape(self) -> None:
        namespace: dict = {}
        exec(_emitted("=== 2. extractor", self.text), namespace)
        function = namespace["_example_trajectories"]
        self.assertIsInstance(function(FIXTURE["row"]), dict)

    def test_what_it_emits_is_content_free(self) -> None:
        """The content sweep fails the build on a forbidden key, so a
        scaffold that proposes one hands the contributor a red build and no
        explanation."""
        namespace: dict = {}
        exec(_emitted("=== 2. extractor", self.text), namespace)
        produced = namespace["_example_trajectories"](FIXTURE["row"])
        forbidden = {
            "messages", "test_output", "output_patch", "patch",
            "trajectory", "problem_statement", "paths",
        }
        self.assertEqual(forbidden & set(produced), set())
        self.assertNotIn(
            FIXTURE["row"]["messages"], str(produced),
            "the scaffold copied transcript content into the frozen row",
        )

    def test_it_proposes_a_real_column_not_a_list_of_them(self) -> None:
        """The first run emitted `"outcome_field": "['correctness_count']"`,
        a spec naming a column that cannot exist."""
        self.assertNotIn("outcome_field\": \"[", self.text)
        self.assertIn('"outcome_field": "resolved"', self.text)

    def test_it_names_what_the_contributor_still_owes(self) -> None:
        for owed in ("base rate", "non-vacuous", "scope"):
            with self.subTest(owed=owed):
                self.assertIn(owed, self.text)


class TheScaffoldRefusesWhatTheContractBars(unittest.TestCase):
    def test_an_undeclared_licence_is_a_blocker(self) -> None:
        """The corpus cannot publish derived metadata from a dataset whose
        terms are unstated, so there is nothing to scaffold."""
        import scaffold_entry

        unlicensed = dict(FIXTURE, license=None)
        original = scaffold_entry.inspect
        scaffold_entry.inspect = lambda dataset: unlicensed
        try:
            self.assertEqual(scaffold_entry.main(["example-org/x"]), 1)
        finally:
            scaffold_entry.inspect = original


if __name__ == "__main__":
    unittest.main()
