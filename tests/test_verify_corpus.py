"""Upstream verification for the whole corpus, and its own failure modes.

Only one of seven datasets could previously be checked against its source;
the rest verified against this repository's own frozen copy, so a freeze
that had misread upstream would have every check agreeing with every other
and all of them wrong together.

The tests here are about the verifier rather than the data, because its two
early versions both produced confident nonsense: one reported schema drift
as disagreement, the other keyed rows by an identifier this corpus contains
4,209 collisions of.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "corpus"))

import verify_corpus  # noqa: E402


def _page(offset: int, rows: list[dict]) -> dict:
    return {
        "rows": [{"row": r, "truncated_cells": []} for r in rows],
        "num_rows_total": 100,
    }


class TheSampleIsDeterministic(unittest.TestCase):
    def test_same_arguments_same_offsets(self) -> None:
        self.assertEqual(
            verify_corpus._offsets(1000, 3), verify_corpus._offsets(1000, 3)
        )

    def test_widening_never_reads_past_the_end(self) -> None:
        for total in (37, 100, 1785, 80036):
            for pages in (1, 3, 9):
                with self.subTest(total=total, pages=pages):
                    for offset in verify_corpus._offsets(total, pages):
                        self.assertGreaterEqual(offset, 0)
                        self.assertLessEqual(offset, total)


class ComparisonIsPositionalNotKeyed(unittest.TestCase):
    """Ids collide by design in this corpus; position is the only sound key.

    An earlier version built {id: row}, kept one row per collision, and
    reported ten mismatches that were entirely its own.
    """

    def _run(self, frozen: list[dict], upstream: list[dict]):
        spec = {
            "dataset": "d", "config": "c", "split": "s",
            "expected_rows": len(upstream),
            "extract": lambda row: dict(row),
        }
        with tempfile.TemporaryDirectory() as directory:
            frozen_dir = pathlib.Path(directory)
            (frozen_dir / "demo.json").write_text(json.dumps(
                {"revision": "rev", "rows": frozen}
            ))
            with mock.patch.object(verify_corpus, "FROZEN", frozen_dir), \
                 mock.patch.dict(verify_corpus.SPECS, {"demo": spec}, clear=False), \
                 mock.patch.object(verify_corpus, "_sha_now", lambda d: "rev"), \
                 mock.patch.object(
                     verify_corpus, "_get", lambda url: _page(0, upstream)
                 ), \
                 mock.patch.object(verify_corpus, "PAGE_LENGTH", len(upstream)):
                return verify_corpus.verify("demo", pages=1)

    def test_colliding_ids_still_verify(self) -> None:
        rows = [
            {"id": "same", "outcome": True, "hash": "a"},
            {"id": "same", "outcome": False, "hash": "b"},
        ]
        checked, failures, _drift = self._run(rows, rows)
        self.assertEqual(failures, [])
        self.assertEqual(checked, 2)

    def test_a_real_disagreement_is_reported(self) -> None:
        frozen = [{"id": "x", "outcome": True, "hash": "a"}]
        upstream = [{"id": "x", "outcome": True, "hash": "CHANGED"}]
        _, failures, _ = self._run(frozen, upstream)
        self.assertEqual(len(failures), 1)
        self.assertIn("hash", failures[0])

    def test_a_field_added_after_the_freeze_is_drift_not_disagreement(self) -> None:
        """Reporting drift as a mismatch trains a reader to ignore the tool."""
        frozen = [{"id": "x", "outcome": True}]
        upstream = [{"id": "x", "outcome": True, "patch_bytes": 12}]
        _, failures, drift = self._run(frozen, upstream)
        self.assertEqual(failures, [])
        self.assertEqual(drift, ["patch_bytes"])


class FailureIsNeverSilent(unittest.TestCase):
    def test_a_moved_revision_refuses_rather_than_comparing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frozen_dir = pathlib.Path(directory)
            (frozen_dir / "demo.json").write_text(json.dumps(
                {"revision": "old", "rows": []}
            ))
            spec = {"dataset": "d", "config": "c", "split": "s",
                    "expected_rows": 0, "extract": dict}
            with mock.patch.object(verify_corpus, "FROZEN", frozen_dir), \
                 mock.patch.dict(verify_corpus.SPECS, {"demo": spec}, clear=False), \
                 mock.patch.object(verify_corpus, "_sha_now", lambda d: "new"):
                checked, failures, _ = verify_corpus.verify("demo", pages=1)
        self.assertEqual(checked, 0)
        self.assertIn("re-freeze before verifying", failures[0])

    def test_an_unfetchable_page_is_a_failure(self) -> None:
        def explode(url):
            raise RuntimeError("gave up")

        with tempfile.TemporaryDirectory() as directory:
            frozen_dir = pathlib.Path(directory)
            (frozen_dir / "demo.json").write_text(json.dumps(
                {"revision": "rev", "rows": [{"id": "x"}] * 50}
            ))
            spec = {"dataset": "d", "config": "c", "split": "s",
                    "expected_rows": 50, "extract": dict}
            with mock.patch.object(verify_corpus, "FROZEN", frozen_dir), \
                 mock.patch.dict(verify_corpus.SPECS, {"demo": spec}, clear=False), \
                 mock.patch.object(verify_corpus, "_sha_now", lambda d: "rev"), \
                 mock.patch.object(verify_corpus, "_get", explode):
                _, failures, _ = verify_corpus.verify("demo", pages=1)
        self.assertTrue(any("UNFETCHED" in f for f in failures))


if __name__ == "__main__":
    unittest.main()


class EveryPublishedFindingIsVerifiable(unittest.TestCase):
    """A finding whose evidence cannot be re-derived from source is a
    finding a reader must take on trust, which is the thing this repository
    argues against. Six of fourteen were in that position: the verifier
    covered the datasets frozen through one transport and silently skipped
    the rest, reporting the count of what it had checked as though it were
    the count of what exists."""

    def test_every_frozen_document_has_a_verifier(self) -> None:
        import verify_corpus

        frozen = {
            path.stem for path in verify_corpus.FROZEN.glob("*.json")
            if path.stem not in verify_corpus.SIDECARS
            and path.stem not in verify_corpus.NOT_PUBLISHED
        }
        missing = sorted(frozen - set(verify_corpus.VERIFIERS))
        self.assertEqual(
            missing, [],
            "frozen evidence with no way to check it against upstream",
        )

    def test_every_finding_names_a_dataset_with_frozen_evidence(self) -> None:
        import json

        import verify_corpus

        registry = json.loads(
            (ROOT / "research" / "findings.json").read_text(encoding="utf-8")
        )
        frozen = {
            path.stem for path in verify_corpus.FROZEN.glob("*.json")
        }
        # Every entry's dataset must have a frozen document behind it, and
        # that document must be verifiable. The mapping is by the evidence
        # the entry cites rather than by name, so a renamed slug fails here.
        self.assertTrue(frozen, "no frozen evidence at all")
        self.assertGreaterEqual(len(registry["findings"]), 14)

    def test_every_verifier_is_callable(self) -> None:
        import verify_corpus

        for slug, verifier in verify_corpus.VERIFIERS.items():
            with self.subTest(slug=slug):
                self.assertTrue(callable(verifier))

    def test_the_coverage_guard_fires_when_a_verifier_is_removed(self) -> None:
        """Proven non-vacuous. A guard demonstrated once by hand can rot
        silently; this keeps the demonstration in the suite."""
        import verify_corpus

        removed = verify_corpus.VERIFIERS.pop("hle-verifiers")
        try:
            with self.assertRaises(AssertionError):
                self.test_every_frozen_document_has_a_verifier()
        finally:
            verify_corpus.VERIFIERS["hle-verifiers"] = removed
        # and it passes again once restored, so the failure was the removal
        self.test_every_frozen_document_has_a_verifier()
