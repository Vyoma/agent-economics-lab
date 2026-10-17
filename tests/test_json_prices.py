"""Pricing and policy JSON must not silently overwrite declared values."""
import io
import unittest
from unittest.mock import patch

from agent_economics.io import load_baseline, load_policy, load_rates


class JsonPriceTests(unittest.TestCase):
    def test_duplicate_keys_are_rejected_at_every_depth(self):
        cases = [
            (load_rates, '{"m":{"input_per_million_usd":1000,'
             '"input_per_million_usd":0,"output_per_million_usd":0}}'),
            (load_rates, '{"m":{},"m":{"input_per_million_usd":0,'
             '"output_per_million_usd":0}}'),
            (load_baseline, '{"name":"human","cost_per_attempt_usd":10,'
             '"cost_per_attempt_usd":0,"acceptable_rate":1,'
             '"value_per_acceptable_outcome_usd":10}'),
            (load_policy, '{"max_calls_per_task":1,"max_calls_per_task":100,'
             '"human_hourly_cost_usd":20,"min_acceptable_rate":0.9,'
             '"max_cost_per_acceptable_outcome_usd":5,"max_p95_task_cost_usd":10,'
             '"max_trace_cost_per_task_usd":10}'),
        ]
        for loader, raw in cases:
            with self.subTest(loader=loader.__name__, raw=raw):
                with patch("pathlib.Path.open", return_value=io.StringIO(raw)):
                    with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                        loader("input.json")

    def test_valid_rate_card_is_unchanged(self):
        raw = '{"m":{"input_per_million_usd":2,"output_per_million_usd":8}}'
        with patch("pathlib.Path.open", return_value=io.StringIO(raw)):
            rate = load_rates("input.json")["m"]
        self.assertEqual(rate.input_per_million_usd, 2)
        self.assertEqual(rate.output_per_million_usd, 8)
