"""The upstream spot-check: deterministic selection, honest failure, no network.

The script exists to close a stated hole: offline, the wild finding verified
only against this repository's own frozen file. These tests cover everything
that does not require the network — the selection is deterministic and always
includes the load-bearing rows, the hash recipe matches the freeze's, and a
fetch that fails or a hash that mismatches is a failure, never a silent skip.
The one network path is exercised by `make verify-upstream`, deliberately not
by the suite.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

import verify_upstream  # noqa: E402


def _row(task_id: str, seed: str, api_calls: int = 5, cost: float = 0.1) -> dict:
    return {
        "task_id": task_id,
        "trajectory_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "messages_sha256": hashlib.sha256((seed + "m").encode()).hexdigest(),
        "api_calls": api_calls,
        "instance_cost_usd": cost,
        "resolved": True,
        "scores_resolved": 1,
    }


def _arms() -> dict:
    arms = {
        arm: [_row(f"t-{i}", f"{arm}-{i}") for i in range(4)]
        for arm in ("alpha", "gemini-3-pro", *verify_upstream.TWINS)
    }
    arms["gemini-3-pro"][3] = _row("t-idle", "idle", api_calls=1, cost=0.0)
    return arms


class SelectionIsDeterministicAndLoadBearing(unittest.TestCase):
    def test_same_input_same_worklist(self) -> None:
        self.assertEqual(
            verify_upstream.select(_arms(), 2, None, False),
            verify_upstream.select(_arms(), 2, None, False),
        )

    def test_widening_the_sample_only_appends(self) -> None:
        small = {key for key, _ in verify_upstream.select(_arms(), 1, None, False)}
        large = {key for key, _ in verify_upstream.select(_arms(), 3, None, False)}
        self.assertLessEqual(small, large)

    def test_the_idle_runs_are_always_selected(self) -> None:
        """The nine one-call zero-spend rows carry the published finding."""
        keys = {key for key, _ in verify_upstream.select(_arms(), 1, None, False)}
        self.assertIn(("gemini-3-pro", "t-idle"), keys)

    def test_a_twin_pair_row_is_always_selected_for_both_arms(self) -> None:
        keys = {key for key, _ in verify_upstream.select(_arms(), 1, None, False)}
        twin_task = min(r["task_id"] for r in _arms()[verify_upstream.TWINS[0]])
        for arm in verify_upstream.TWINS:
            self.assertIn((arm, twin_task), keys)

    def test_the_real_frozen_evidence_selects_nine_idle_rows(self) -> None:
        arms = json.loads(verify_upstream.AUDIT.read_text(encoding="utf-8"))["arms"]
        keys = {key for key, _ in verify_upstream.select(arms, 0, None, False)}
        idle = {k for k in keys if k[0] == "gemini-3-pro"}
        self.assertEqual(len(idle), 9)


class TheHashRecipeMatchesTheFreeze(unittest.TestCase):
    def test_rehash_reproduces_both_frozen_hashes(self) -> None:
        raw = json.dumps(
            {"instance_id": "t", "messages": [{"role": "user", "content": "x"}]}
        ).encode()
        whole, transcript = verify_upstream.rehash(raw)
        self.assertEqual(whole, hashlib.sha256(raw).hexdigest())
        self.assertEqual(
            transcript,
            hashlib.sha256(
                json.dumps(
                    [{"role": "user", "content": "x"}], sort_keys=True
                ).encode("utf-8")
            ).hexdigest(),
        )

    def test_the_upstream_path_template(self) -> None:
        self.assertEqual(
            verify_upstream.upstream_path("gemini-3-pro", "astropy__astropy-12907"),
            "swebench_verified_raw/gemini-3-pro/astropy__astropy-12907/"
            "astropy__astropy-12907.traj.json",
        )


class FailureIsNeverSilent(unittest.TestCase):
    """'Could not check' must never read as 'checked'."""

    def _run(self, fetcher) -> int:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"arms": _arms()}, f)
        audit = pathlib.Path(f.name)
        try:
            with mock.patch.object(verify_upstream, "fetch", fetcher), \
                 mock.patch.object(verify_upstream, "AUDIT", audit):
                return verify_upstream.main(["--sample", "1"])
        finally:
            audit.unlink()

    def test_an_unfetchable_row_fails_the_run(self) -> None:
        def fetcher(url):
            raise RuntimeError("gave up")

        self.assertEqual(self._run(fetcher), 1)

    def test_a_hash_mismatch_fails_the_run(self) -> None:
        def fetcher(url):
            return json.dumps({"instance_id": "t", "messages": []}).encode()

        self.assertEqual(self._run(fetcher), 1)

    def test_matching_bytes_pass(self) -> None:
        """Build arms whose frozen hashes were derived from the served bytes."""
        served = {}
        arms = {}
        for arm in ("alpha", "gemini-3-pro", *verify_upstream.TWINS):
            rows = []
            for i in range(2):
                # The twin arms must share a transcript while differing as
                # files, exactly as the frozen evidence records upstream.
                body = {
                    "instance_id": f"t-{i}",
                    "messages": [{"i": i}],
                    "label": arm if arm not in verify_upstream.TWINS else f"twin-{arm}",
                }
                raw = json.dumps(body).encode()
                row = {
                    "task_id": f"t-{i}",
                    "trajectory_sha256": hashlib.sha256(raw).hexdigest(),
                    "messages_sha256": hashlib.sha256(
                        json.dumps([{"i": i}], sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "api_calls": 5,
                    "instance_cost_usd": 0.1,
                }
                rows.append(row)
                served[verify_upstream.upstream_url(arm, f"t-{i}")] = raw
            arms[arm] = rows

        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"arms": arms}, f)
        audit = pathlib.Path(f.name)
        try:
            with mock.patch.object(verify_upstream, "fetch", served.__getitem__), \
                 mock.patch.object(verify_upstream, "AUDIT", audit):
                self.assertEqual(verify_upstream.main(["--sample", "2"]), 0)
        finally:
            audit.unlink()


if __name__ == "__main__":
    unittest.main()
