"""Regenerate the held-out evaluation of the divergence detector.

Measures this repository's package alongside six standard-library packages,
using the running interpreter's own stdlib. The numbers therefore move with the
Python version, which is why this is not part of `make reproduce`: the CI
matrix spans four versions and a byte-comparison would fail on three of them
for a reason that is not a defect.
"""

from __future__ import annotations

import json as _json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from research.divergence import main as divergence_main

STDLIB = pathlib.Path(_json.__file__).parent.parent
HELD_OUT = ("json", "logging", "email", "http", "asyncio", "unittest")

HEADER = """# The detector on code it has never seen

The rule was abstracted from five defects in `agent_economics` and then
evaluated on `agent_economics`. That is fitting to your own training set, and
no claim survives it. This is the held-out run: the same detector, unchanged,
pointed at six mature standard-library packages.

Read the negative result first.

## What it did not do

**It found no defect in any standard-library package.** The divergences below
are real -- these call sites genuinely disagree -- and every one inspected was
deliberate. `asyncio._ensure_resolved(..., flags=)` is passed by four callers
and omitted by `selector_events.py:642`, because that path connects to an
already-resolved address where lookup flags do not apply and `flags=0` is
correct.

So the honest claim is not "a defect detector that works on any codebase". On
mature code this produces a short, readable list of intentional design
decisions. Converting a divergence into a defect took domain knowledge in every
case where it worked.

## What it did do

It found a defect in **itself**, immediately, which is the reason to run
held-out evaluations at all. The first run reported `__init__(..., stdout=)` as
"1 caller passes, 33 omit" across asyncio. That is not one function with
disagreeing callers; it is 34 unrelated constructors conflated by name. The
detector matched call sites to definitions by name alone, which happened to be
safe in a package of unique module-level functions and is garbage anywhere
else. Names that resolve ambiguously are now dropped entirely, and dunders with
them. Before that fix the six standard-library packages reported 78
divergences; after it, 34.

## The measurement

"""

FOOTER = """
## Reading the table honestly

After the conflation fix, the four most mature packages sit well below one
divergence per kLOC. `agent_economics` and `unittest` sit above it.

That separation is suggestive and it is not evidence. "Maturity" is not
measured here, the sample is six packages, `json` is small enough that its rate
rests on seven divergences, and nothing establishes that divergence density
tracks defect density in either direction. A reader who concludes "this repo is
three times buggier than asyncio" has read something that was not written.

What the table supports is narrower: the detector emits a list short enough to
read by hand on every package tried, which is the minimum bar for a reading
aid, and the density is not so uniform that it is obviously measuring nothing.

## What this settles about the method

The compounding claim was that each defect yields a shape, each shape
enumerates sites, so the detector improves with use. This run is evidence for
the loop and against the strong form of the claim.

For: the loop ran, on the tool itself, and produced a real correction that no
amount of staring at `agent_economics` would have surfaced.

Against: enumeration without domain knowledge did not convert into defects on
unfamiliar code. The three prospective findings in this repository were found
because the author knew which of eighteen divergences would matter. That is a
reading aid for an expert, not an oracle, and the difference is the whole
distance between a tool and a moat.
"""


def check(existing: pathlib.Path) -> int:
    """Compare against the committed artifact, but only on its own interpreter.

    The table measures the running interpreter's own standard library, so it
    moves with the Python version and the CI matrix spans four. Asserting
    across versions would fail for a reason that is not a defect. Asserting on
    the *same* version is exactly right, and the previous recipe did neither:
    `|| echo` swallowed every difference, so the gate could not fail at all.
    """
    version = ".".join(str(part) for part in sys.version_info[:3])
    text = existing.read_text(encoding="utf-8")
    recorded = ""
    for line in text.splitlines():
        if line.startswith("Generated on CPython "):
            recorded = line.removeprefix("Generated on CPython ").rstrip(".")
            break
    if recorded != version:
        print(
            f"held-out artifact was generated on CPython {recorded or '?'}; "
            f"running {version}. Skipping the comparison, which would differ "
            "for a reason that is not a defect.",
            file=sys.stderr,
        )
        return 0
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        _emit()
    if buffer.getvalue() != text:
        print(
            f"held-out table drifted on CPython {version}. Regenerate with "
            "`python research/held_out.py > research/HELD_OUT.md`.",
            file=sys.stderr,
        )
        return 1
    return 0


def _emit() -> None:
    version = ".".join(str(part) for part in sys.version_info[:3])
    print(HEADER, end="")
    print(f"Generated on CPython {version}.\n")
    roots = ["agent_economics"] + [str(STDLIB / name) for name in HELD_OUT]
    divergence_main([*roots, "--show", "5"])
    print(FOOTER, end="")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--check":
        return check(pathlib.Path(argv[1]))
    _emit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
