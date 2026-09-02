"""Rewrite the test count on the published page from live discovery.

docs/index.md quotes the suite size in two sentences, and three guards hold
the page to the real number. Every added test used to mean a hand-edited
sed and, when forgotten, a full CI round-trip; six of this repository's CI
failures were exactly that. The count is now written by this script, which
`make docs-sync` runs, so the page follows the suite instead of chasing it.
"""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def discovered() -> int:
    """Count exactly what `python -m unittest discover -s tests` counts.

    Discovery must run with the repository root as CWD and on sys.path, or
    modules that import the package fail to load and the count silently
    shrinks; the first run of this script wrote 510 where the suite has
    698. A load error is therefore fatal, never a smaller number.
    """
    import os

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    loader = unittest.defaultTestLoader
    suite = loader.discover("tests")
    if loader.errors:
        raise SystemExit(
            "test discovery failed to import modules; refusing to write a "
            "count derived from a partial suite:\n" + "\n".join(loader.errors)
        )
    return suite.countTestCases()


def main() -> int:
    count = discovered()
    page = ROOT / "docs" / "index.md"
    text = page.read_text(encoding="utf-8")
    updated = re.sub(r"\b\d{3,4}(?= tests on Python 3\.10)", str(count), text)
    updated = re.sub(
        r"(?<=Neither was caught by )\d{3,4}(?= tests)", str(count), updated
    )
    if updated != text:
        page.write_text(updated, encoding="utf-8")
        print(f"docs/index.md test count -> {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
