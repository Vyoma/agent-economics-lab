from __future__ import annotations

import unittest

from agent_economics.controls import argument_shape, find_directed_cycles


class ControlTests(unittest.TestCase):
    def test_argument_shape_discards_values_but_keeps_types(self) -> None:
        left = {"query": "alpha", "page": 1, "exact": True}
        right = {"query": "beta", "page": 9, "exact": False}
        self.assertEqual(argument_shape(left), argument_shape(right))
        self.assertNotEqual(argument_shape({"page": 1}), argument_shape({"page": "1"}))

    def test_cycle_detection_is_diagnostic(self) -> None:
        cycles = find_directed_cycles(
            [("agent-a", "tool-x"), ("tool-x", "agent-b"), ("agent-b", "agent-a")]
        )
        self.assertEqual(cycles, [("agent-a", "tool-x", "agent-b")])

    def test_acyclic_graph(self) -> None:
        self.assertEqual(find_directed_cycles([("a", "b"), ("b", "c")]), [])


if __name__ == "__main__":
    unittest.main()
