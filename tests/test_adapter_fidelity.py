"""Conservation on the way in: nothing vanishes, and the spend reconciles.

The adapters were covered by byte-compared fixtures and a frozen count
inventory. Neither can see an adapter that reads half its input and always
has: the fixture matches its own output, and the inventory matches the
adapter's own count of what it decoded. These tests hold the property those
miss.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

import adapter_fidelity  # noqa: E402


class NothingIsOrphaned(unittest.TestCase):
    def test_every_source_unit_is_cited_or_named(self) -> None:
        for name, result in adapter_fidelity.measure().items():
            with self.subTest(path=name):
                self.assertEqual(
                    result["orphaned"], [],
                    f"{name} decoded neither cites nor accounts for these "
                    "source units; they would vanish from the evidence",
                )

    def test_the_partition_adds_up(self) -> None:
        for name, result in adapter_fidelity.measure().items():
            with self.subTest(path=name):
                self.assertEqual(
                    result["source"],
                    result["cited"] + result["accounted"] + len(result["orphaned"]),
                )

    def test_an_accounted_bucket_is_always_named(self) -> None:
        """A silent 'accounted' count is an orphan with better manners."""
        for name, result in adapter_fidelity.measure().items():
            with self.subTest(path=name):
                if result["accounted"]:
                    self.assertTrue(result["accounted_as"].strip())

    def test_the_orphan_check_fires_when_decoding_is_lossy(self) -> None:
        """Proven non-vacuous: drop each decoded class, see orphans appear."""
        import dataclasses
        from unittest import mock

        real = adapter_fidelity.inspect_claude_code_jsonl
        for field in ("model_calls", "tool_calls", "tasks"):
            with self.subTest(dropped=field):
                def lossy(path, field=field):
                    return dataclasses.replace(real(path), **{field: ()})

                with mock.patch.object(
                    adapter_fidelity, "inspect_claude_code_jsonl", lossy
                ):
                    result = adapter_fidelity._claude_code(
                        adapter_fidelity.EXAMPLES / "claude-code" / "session.jsonl"
                    )
                self.assertNotEqual(result["orphaned"], [])

    def test_a_single_co_cited_call_can_be_dropped_undetected(self) -> None:
        """The measurement's own limit, pinned so the page cannot overclaim.

        Records are cited redundantly - a model turn's uuid is often also
        named by the task boundary or a tool pair - so losing one call of
        several leaves every record still cited. Whole-class loss is caught;
        a single co-cited call is not.
        """
        import dataclasses
        from unittest import mock

        real = adapter_fidelity.inspect_claude_code_jsonl

        def lossy(path):
            session = real(path)
            return dataclasses.replace(session, model_calls=session.model_calls[1:])

        with mock.patch.object(adapter_fidelity, "inspect_claude_code_jsonl", lossy):
            result = adapter_fidelity._claude_code(
                adapter_fidelity.EXAMPLES / "claude-code" / "session.jsonl"
            )
        self.assertEqual(result["orphaned"], [])


class TheSpendReconciles(unittest.TestCase):
    def test_the_session_tree_residual_is_zero(self) -> None:
        r = adapter_fidelity.token_reconciliation()
        self.assertEqual(r["residual_in"], 0)
        self.assertEqual(r["residual_out"], 0)

    def test_the_transforms_are_non_trivial(self) -> None:
        """If the fixture stopped exercising de-duplication and stream
        merging, a residual of zero would prove nothing."""
        r = adapter_fidelity.token_reconciliation()
        self.assertGreater(r["bootstrap_in"], 0)
        self.assertGreater(r["merged_in"], 0)
        self.assertGreater(r["cache_read"], 0)


class ThePageRecomputes(unittest.TestCase):
    def test_committed_page_matches_render(self) -> None:
        committed = (ROOT / "research" / "ADAPTER_FIDELITY.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(committed, adapter_fidelity.render())


if __name__ == "__main__":
    unittest.main()
