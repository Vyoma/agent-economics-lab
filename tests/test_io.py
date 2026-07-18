from __future__ import annotations

import unittest
from pathlib import Path

from agent_economics import load_rates, load_traces


ROOT = Path(__file__).resolve().parents[1]


class IoTests(unittest.TestCase):
    def test_trace_cost_uses_rate_card_or_direct_cost(self) -> None:
        events = load_traces(ROOT / "examples" / "support_trace.csv")
        rates = load_rates(ROOT / "examples" / "rates.json")
        model_event = next(event for event in events if event.event_id == "e-003")
        tool_event = next(event for event in events if event.event_id == "e-002")
        self.assertAlmostEqual(model_event.cost(rates), 0.032, places=8)
        self.assertAlmostEqual(tool_event.cost(rates), 0.002, places=8)


if __name__ == "__main__":
    unittest.main()
