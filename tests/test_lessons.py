"""
Executable lessons: count and exit status.

Two gaps met here. The README publishes "five executable lessons" and nothing
asserted the count. And nothing in tests/ referenced lessons/ at all, so
`make lessons` was their only exercise, which is what let a failure-masking
loop in that target go unnoticed (see research/SELF_AUDIT.md, finding 1).

Running them here means the test suite alone catches a broken lesson, rather
than depending on the make target being written correctly. All five together
take well under a second.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LESSONS = sorted((ROOT / "lessons").glob("*.py"))


class LessonInventoryTest(unittest.TestCase):
    def test_readme_publishes_five_lessons(self) -> None:
        self.assertEqual(len(LESSONS), 5, [p.name for p in LESSONS])

    def test_lessons_are_numbered_in_sequence(self) -> None:
        self.assertEqual([p.name[:2] for p in LESSONS], ["00", "01", "02", "03", "04"])


class LessonExecutionTest(unittest.TestCase):
    """A lesson that stops working must fail the test suite, not just the target."""

    def test_every_lesson_exits_zero(self) -> None:
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.name):
                result = subprocess.run(
                    [sys.executable, str(lesson)],
                    cwd=ROOT,
                    env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode, 0, f"{lesson.name}\n{result.stderr[-2000:]}"
                )


if __name__ == "__main__":
    unittest.main()
