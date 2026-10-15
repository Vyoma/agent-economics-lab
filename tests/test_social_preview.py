"""The public repository preview must remain reproducible and current."""

from __future__ import annotations

import pathlib
import struct
import sys
import zlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import render_social_preview  # noqa: E402

PREVIEW = ROOT / "docs" / "assets" / "social-preview.png"


def decode_indexed_png(path: pathlib.Path) -> tuple[int, int, bytes]:
    """Decode the filter-0 indexed PNG emitted by ``videokit.raster``."""
    blob = path.read_bytes()
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("social preview is not a PNG")

    pos = 8
    width = height = 0
    compressed = bytearray()
    while pos < len(blob):
        length = struct.unpack_from(">I", blob, pos)[0]
        kind = blob[pos + 4 : pos + 8]
        data = blob[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            if (depth, color_type, compression, filtering, interlace) != (8, 3, 0, 0, 0):
                raise AssertionError("social preview uses an unexpected PNG encoding")
        elif kind == b"IDAT":
            compressed += data
        elif kind == b"IEND":
            break

    raw = zlib.decompress(bytes(compressed))
    stride = width + 1
    if len(raw) != stride * height:
        raise AssertionError("social preview has an invalid pixel payload")
    rows = []
    for y in range(height):
        row = raw[y * stride : (y + 1) * stride]
        if row[0] != 0:
            raise AssertionError("social preview uses an unsupported PNG row filter")
        rows.append(row[1:])
    return width, height, b"".join(rows)


class SocialPreview(unittest.TestCase):
    def test_preview_is_github_share_size(self) -> None:
        self.assertTrue(PREVIEW.exists(), "run: make social-preview")
        width, height, _ = decode_indexed_png(PREVIEW)
        self.assertEqual((width, height), (1280, 640))

    def test_committed_pixels_match_the_renderer(self) -> None:
        width, height, pixels = decode_indexed_png(PREVIEW)
        fresh = render_social_preview.render()
        self.assertEqual((width, height), (fresh.width, fresh.height))
        self.assertEqual(
            pixels,
            bytes(fresh.px),
            "docs/assets/social-preview.png is stale; run: make social-preview",
        )


if __name__ == "__main__":
    unittest.main()
