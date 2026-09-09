"""The standalone reproduction must stay standalone, and stay pointed at
the data the corpus froze.

`research/reproduce_hle.py` recomputes the headline grader result from the
public source in 148 lines that import nothing from this project. That is
the only artifact here a reader can audit end to end without taking the
repository on trust: `make verify-corpus` re-derives the frozen file using
this project's own extractor, which proves reproducibility but not
independence.

Running it needs an 83MB download and several minutes, so these check what
can be checked offline: that it is genuinely standalone, and that its pinned
revision and source hash still match the frozen evidence. A file that
quietly pointed at a different revision would agree with nothing and look
like it agreed with everything.
"""

from __future__ import annotations

import ast
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "reproduce_hle.py"
FROZEN = ROOT / "research" / "corpus" / "frozen" / "hle-verifiers.json"


def _constants() -> dict[str, str]:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.value.value
    return found


class ItIsGenuinelyStandalone(unittest.TestCase):
    def test_it_imports_nothing_from_this_project(self) -> None:
        """The moment it imports the package, it stops being an independent
        check and becomes another way of running the same code."""
        local = {
            "agent_economics", "corpus_report", "freeze", "verify_corpus",
            "freeze_hle_verifiers", "corpus_io", "patterns", "findings",
        }
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & local, set(), "reaches back into the project")

    def test_it_uses_the_standard_library_only(self) -> None:
        import sys

        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        imported.discard("__future__")
        outside = sorted(m for m in imported if m not in sys.stdlib_module_names)
        self.assertEqual(outside, [], "a dependency defeats the point")

    def test_it_is_short_enough_to_read(self) -> None:
        """The claim it makes is that you can check this yourself in one
        sitting. A file nobody reads is trusted, not checked."""
        lines = len(SCRIPT.read_text(encoding="utf-8").splitlines())
        self.assertLess(lines, 200, "no longer readable in one sitting")


class ItPointsAtTheEvidenceTheCorpusFroze(unittest.TestCase):
    def test_the_revision_matches_the_frozen_document(self) -> None:
        document = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(_constants()["REVISION"], document["revision"])

    def test_the_source_hash_matches_the_frozen_document(self) -> None:
        document = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(
            _constants()["EXPECTED_SHA256"], document["source_sha256"]
        )


if __name__ == "__main__":
    unittest.main()
