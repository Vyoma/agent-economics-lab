"""Interpreter drift must not hide drift in this repository's measurements."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import held_out


REPORT = """| package | files | lines |
| `agent_economics` | 31 | 14914 |

## agent_economics: most lopsided divergences

```
example(..., flag=)  2 pass / 1 omit
```
"""


class HeldOutGateTests(unittest.TestCase):
    def check_report(self, report):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(report, encoding="utf-8")
            with patch.object(held_out.sys, "version_info", (3, 12, 99)):
                with patch.object(held_out, "divergence_main",
                                  side_effect=lambda args: print(REPORT)):
                    return held_out.check(path)

    def test_other_interpreter_still_rejects_repository_table_drift(self):
        self.assertEqual(self.check_report(
            "Generated on CPython 3.12.13.\n" + REPORT.replace("14914", "1")), 1)

    def test_other_interpreter_still_rejects_repository_finding_drift(self):
        self.assertEqual(self.check_report(
            "Generated on CPython 3.12.13.\n" + REPORT.replace("2 pass", "3 pass")), 1)

    def test_other_interpreter_allows_matching_repository_evidence(self):
        self.assertEqual(self.check_report(
            "Generated on CPython 3.12.13.\n" + REPORT
            + "\n## json: most lopsided divergences\nVersion-specific text\n"), 0)

    def test_missing_version_is_not_a_successful_skip(self):
        self.assertEqual(self.check_report(REPORT), 1)

    def test_missing_repository_evidence_is_rejected(self):
        self.assertEqual(self.check_report("Generated on CPython 3.12.13.\n"), 1)

    def test_duplicate_repository_evidence_is_rejected(self):
        self.assertEqual(self.check_report(
            "Generated on CPython 3.12.13.\n" + REPORT + REPORT), 1)

    def test_same_interpreter_compares_the_entire_artifact(self):
        original = "Generated on CPython 3.12.99.\n" + REPORT
        with patch.object(held_out, "_emit", side_effect=lambda: print(original, end="")):
            self.assertEqual(self.check_report(original), 0)
            self.assertEqual(self.check_report(original + "changed stdlib result\n"), 1)
