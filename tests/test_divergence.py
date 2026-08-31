"""The divergence detector, and the defect the held-out run found in it.

`research/divergence.py` is the tool lifted out of this repository so it could
be pointed at code it did not come from. The first held-out run found a defect
in the tool within a minute, which is the entire argument for running one.
"""

from __future__ import annotations

import pathlib
import tempfile
import textwrap
import unittest

from research.divergence import find_divergences, measure

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _package(source_by_name: dict[str, str]) -> pathlib.Path:
    directory = pathlib.Path(tempfile.mkdtemp())
    for name, source in source_by_name.items():
        (directory / name).write_text(textwrap.dedent(source), encoding="utf-8")
    return directory


class NamesMustResolveUnambiguously(unittest.TestCase):
    """The held-out defect.

    Matching call sites to definitions by name alone conflates every same-named
    method in a package. On asyncio this reported `__init__(..., stdout=)` as
    one function with 33 dissenting callers; it is 34 unrelated constructors.
    """

    def test_same_named_methods_on_different_classes_are_not_conflated(self) -> None:
        package = _package({"m.py": """
            class Alpha:
                def send(self, payload, *, retries=0):
                    return payload

            class Beta:
                def send(self, payload, *, retries=0):
                    return payload

            def use(a, b):
                a.send(1, retries=3)
                b.send(2)
        """})
        self.assertEqual(
            find_divergences(package), [],
            "two classes with a same-named method are not one function",
        )

    def test_dunders_are_excluded(self) -> None:
        package = _package({"m.py": """
            class Alpha:
                def __init__(self, *, extra=None):
                    self.extra = extra

            def build():
                return Alpha(extra=1), Alpha()
        """})
        self.assertEqual(find_divergences(package), [])

    def test_a_genuine_disagreement_is_still_reported(self) -> None:
        """The fix must not silence the signal it was narrowing."""
        package = _package({"m.py": """
            def resolve(address, *, flags=0):
                return address, flags

            def a():
                return resolve("x", flags=2)

            def b():
                return resolve("y", flags=3)

            def c():
                return resolve("z")
        """})
        found = find_divergences(package)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].function, "resolve")
        self.assertEqual(found[0].parameter, "flags")
        self.assertEqual(len(found[0].passes), 2)
        self.assertEqual(len(found[0].omits), 1)

    def test_lopsidedness_ranks_a_lone_dissenter_highest(self) -> None:
        package = _package({"m.py": """
            def wide(value, *, mode=None):
                return value, mode

            def narrow(value, *, mode=None):
                return value, mode

            def callers():
                wide(1, mode="a"); wide(2, mode="a"); wide(3, mode="a")
                wide(4, mode="a"); wide(5)
                narrow(1, mode="a"); narrow(2, mode="a")
                narrow(3); narrow(4)
        """})
        found = find_divergences(package)
        self.assertEqual([d.function for d in found], ["wide", "narrow"])
        self.assertGreater(found[0].lopsidedness, found[1].lopsidedness)


class TheDetectorRunsOnThisPackage(unittest.TestCase):
    def test_it_reports_a_list_short_enough_to_read(self) -> None:
        """A reading aid that emits hundreds of sites is not a reading aid."""
        report = measure(ROOT / "agent_economics")
        self.assertGreater(report["lines"], 5_000)
        self.assertLess(
            report["divergences"], 60,
            "the list must stay hand-readable or the tool is a firehose",
        )

    def test_it_reports_no_divergence_for_a_package_without_optional_arguments(self) -> None:
        package = _package({"m.py": """
            def add(a, b):
                return a + b

            def use():
                return add(1, 2), add(3, 4)
        """})
        self.assertEqual(find_divergences(package), [])


if __name__ == "__main__":
    unittest.main()
