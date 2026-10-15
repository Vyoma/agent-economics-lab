"""Render the repository's share card from checked-in source.

GitHub's social preview is a public interface: it is often the only part of the
project somebody sees before deciding whether to open the repository.  Keeping
that image as an opaque upload would make it the one important project claim
that could drift without review.  This renderer makes the copy, layout, and
pixels reproducible with the same zero-dependency raster stack as the demo.

    python render_social_preview.py

The resulting 1280 x 640 PNG is the size GitHub recommends for repository
previews.  ``tests/test_social_preview.py`` decodes the committed PNG and
compares its pixels with a fresh render, without depending on zlib producing
identical compressed bytes on every platform.
"""

from __future__ import annotations

import argparse
import pathlib

from videokit.raster import Canvas, Font, write_png

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "social-preview.png"

WIDTH = 1280
HEIGHT = 640
MARGIN = 72


def render(font: Font | None = None) -> Canvas:
    """Return the deterministic social-preview canvas."""
    font = font or Font()
    card = Canvas(WIDTH, HEIGHT, font)

    # A single restrained rule gives the card an identity without turning a
    # research artifact into a logo exercise.
    card.fill_rect(MARGIN, 68, 5, 504, "cyan")

    card.text(104, 72, "AGENT ECONOMICS LAB", 18, "dim")
    card.text(908, 72, "PRODUCTION AI", 18, "green")

    card.text(104, 154, "Your agent says it worked.", 44, "text")
    card.text(104, 220, "Prove it.", 44, "cyan")

    card.text(
        104,
        315,
        "Reproducible evidence for AI deployment decisions.",
        24,
        "text",
    )
    card.text(
        104,
        360,
        "Predictive ML / generative AI / agent systems",
        18,
        "dim",
    )

    card.fill_rect(104, 438, 1096, 1, "dim", level=8)
    card.text(104, 474, "EVIDENCE IN", 18, "green")
    card.text(104, 510, "traces + outcomes + full cost + baseline + policy", 18, "text")
    card.text(795, 474, "DECISION OUT", 18, "cyan")
    card.text(795, 510, "SCALE / ASSIST / STOP / INCOMPLETE", 18, "text")

    return card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help="output PNG (default: docs/assets/social-preview.png)",
    )
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_png(args.output, render())
    print(f"  {args.output}  {WIDTH}x{HEIGHT}  {args.output.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
