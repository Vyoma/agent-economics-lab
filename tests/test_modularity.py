from __future__ import annotations

import math
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from agent_economics import (
    evaluate_bundle,
    load_csv_bundle,
    make_evidence_bundle,
    normalized_json_bundle,
)
from agent_economics.report import render_markdown


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


class ModularityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.csv = load_csv_bundle(
            traces=EXAMPLES / "support_trace.csv",
            outcomes=EXAMPLES / "outcomes.csv",
            rates=EXAMPLES / "rates.json",
            baseline=EXAMPLES / "baseline.json",
            policy=EXAMPLES / "policy.json",
        )

    def test_normalized_json_adapter_is_economically_equivalent(self) -> None:
        raw = {
            "events": [asdict(event) for event in reversed(self.csv.events)],
            "outcomes": [
                asdict(self.csv.outcomes[task_id])
                for task_id in reversed(tuple(self.csv.outcomes))
            ],
            "rates": {
                name: asdict(rate) for name, rate in reversed(tuple(self.csv.rates.items()))
            },
            "baseline": asdict(self.csv.baseline),
            "policy": asdict(self.csv.policy),
        }
        normalized = normalized_json_bundle(raw)
        csv_case = evaluate_bundle(self.csv)
        normalized_case = evaluate_bundle(normalized)
        self.assertEqual(normalized.digest, self.csv.digest)
        self.assertEqual(normalized_case.decision, csv_case.decision)
        self.assertEqual(
            normalized_case.total_effective_cost_usd,
            csv_case.total_effective_cost_usd,
        )
        self.assertEqual(normalized_case.breaches, csv_case.breaches)

    def test_event_order_does_not_change_digest(self) -> None:
        reordered = make_evidence_bundle(
            events=tuple(reversed(self.csv.events)),
            outcomes=self.csv.outcomes,
            rates=self.csv.rates,
            baseline=self.csv.baseline,
            policy=self.csv.policy,
            source_id="source.in-memory",
        )
        self.assertEqual(reordered.digest, self.csv.digest)

    def test_duplicate_event_ids_fail_fast(self) -> None:
        duplicate = replace(self.csv.events[1], event_id=self.csv.events[0].event_id)
        with self.assertRaisesRegex(ValueError, "Duplicate event IDs"):
            make_evidence_bundle(
                events=self.csv.events + (duplicate,),
                outcomes=self.csv.outcomes,
                rates=self.csv.rates,
                baseline=self.csv.baseline,
                policy=self.csv.policy,
                source_id="source.test",
            )

    def test_duplicate_outcomes_fail_in_normalized_adapter(self) -> None:
        outcome = asdict(next(iter(self.csv.outcomes.values())))
        raw = {
            "events": [asdict(event) for event in self.csv.events],
            "outcomes": [outcome, outcome],
            "rates": {name: asdict(rate) for name, rate in self.csv.rates.items()},
            "baseline": asdict(self.csv.baseline),
            "policy": asdict(self.csv.policy),
        }
        with self.assertRaisesRegex(ValueError, "Duplicate outcome task ID"):
            normalized_json_bundle(raw)

    def test_normalized_adapter_rejects_non_finite_economics(self) -> None:
        events = [asdict(event) for event in self.csv.events]
        events[0]["direct_cost_usd"] = math.nan
        raw = {
            "events": events,
            "outcomes": [
                asdict(self.csv.outcomes[task_id]) for task_id in self.csv.outcomes
            ],
            "rates": {name: asdict(rate) for name, rate in self.csv.rates.items()},
            "baseline": asdict(self.csv.baseline),
            "policy": asdict(self.csv.policy),
        }
        with self.assertRaisesRegex(ValueError, "must be finite"):
            normalized_json_bundle(raw)

    def test_checked_in_report_is_reproducible(self) -> None:
        expected = (EXAMPLES / "assurance-case.md").read_text(encoding="utf-8")
        self.assertEqual(render_markdown(evaluate_bundle(self.csv)), expected)


if __name__ == "__main__":
    unittest.main()
