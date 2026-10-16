"""The static README figure must stay true to live decisions."""

from __future__ import annotations

import json
import pathlib
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import render_decision_figure  # noqa: E402
from videokit.raster import Canvas, Font, write_png  # noqa: E402

ASSETS = ROOT / "docs" / "assets"
PNG = ASSETS / "decision.png"
FACTS = ASSETS / "decision.json"
README = ROOT / "README.md"


def decode_indexed_png(path: pathlib.Path) -> tuple[int, int, bytes]:
    """Decode the filter-0 indexed PNG emitted by the local raster writer."""
    blob = path.read_bytes()
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("decision figure is not a PNG")
    pos = 8
    width = height = 0
    compressed = bytearray()
    while pos < len(blob):
        length = struct.unpack_from(">I", blob, pos)[0]
        kind = blob[pos + 4 : pos + 8]
        data = blob[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (depth, colour, compression, filtering, interlace) != (8, 3, 0, 0, 0):
                raise AssertionError("decision figure uses an unexpected PNG encoding")
        elif kind == b"IDAT":
            compressed += data
        elif kind == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    stride = width + 1
    rows = []
    for y in range(height):
        row = raw[y * stride : (y + 1) * stride]
        if not row or row[0] != 0:
            raise AssertionError("decision figure uses an unsupported PNG row filter")
        rows.append(row[1:])
    return width, height, b"".join(rows)


class FontAtlas(unittest.TestCase):
    def test_covers_every_character_the_figure_draws(self) -> None:
        font = Font()
        facts = json.loads(FACTS.read_text())
        drawn = "".join(
            [facts["verdict"], facts["reduced_verdict"], facts["disabled_gate"]]
            + facts["breaches_shown"]
            + facts["missing_coverage"]
        )
        self.assertEqual(font.missing(drawn), set())

    def test_unknown_glyph_raises_rather_than_drawing_blank(self) -> None:
        canvas = Canvas(40, 40, Font())
        with self.assertRaises(KeyError):
            canvas.text(0, 0, "中", 18, "text")


class FigureIsCurrent(unittest.TestCase):
    def test_front_door_uses_only_the_static_figure(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("](docs/assets/decision.png)", readme)
        for suffix in (".gif", ".mp4", ".webm", ".mov"):
            self.assertNotIn(suffix, readme.lower())
        self.assertFalse((ASSETS / "decision.gif").exists())

    def test_recorded_facts_match_live_decisions(self) -> None:
        recorded = json.loads(FACTS.read_text())
        live = render_decision_figure.recorded_facts(render_decision_figure.gather())
        self.assertEqual(recorded, live)
        self.assertEqual(recorded["reduced_verdict"], "INCOMPLETE")
        self.assertEqual(
            recorded["drift"]["fixed_contract_incomplete"],
            recorded["drift"]["comparisons"],
        )
        self.assertGreater(recorded["drift"]["dynamic_false_scale_transitions"], 0)

    def test_committed_pixels_match_the_renderer(self) -> None:
        width, height, pixels = decode_indexed_png(PNG)
        fresh = render_decision_figure.render()
        self.assertEqual((width, height), (fresh.width, fresh.height))
        self.assertEqual(pixels, bytes(fresh.px), "decision.png is stale; run: make figure")


class PngWriter(unittest.TestCase):
    def test_writes_a_valid_indexed_png(self) -> None:
        canvas = Canvas(12, 9, Font())
        canvas.fill_rect(2, 2, 5, 4, "amber")
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "probe.png"
            write_png(out, canvas)
            blob = out.read_bytes()
        self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n")
        width, height, depth, colour = struct.unpack_from(">IIBB", blob, 16)
        self.assertEqual((width, height, depth, colour), (12, 9, 8, 3))
        self.assertIn(b"PLTE", blob)
        self.assertTrue(blob.rstrip().endswith(b"IEND\xae\x42\x60\x82"))


if __name__ == "__main__":
    unittest.main()
