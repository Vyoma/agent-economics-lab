"""Regenerate the checked-in bitmap font atlas. macOS only, run rarely.

The atlas exists so that `render_video.py` needs nothing but the Python standard
library. Drawing text normally means Pillow or a font shaper; this repository
declares zero runtime dependencies and that property is worth more than the
convenience. So the glyphs are rasterised once, here, from a real monospace font
via AppKit, and the grayscale cells are committed as `videokit/atlas.bin`.

    /usr/bin/python3 videokit/make_atlas.py

Only the system interpreter ships pyobjc. Note that this machine's pyobjc has no
Core Text bindings, hence AppKit rather than CTLine.

Format of atlas.bin, zlib-compressed:

    u32                  charset byte length
    utf-8 bytes          charset, in atlas order
    u16                  number of sizes
    per size: u16 px, u16 cell_w, u16 cell_h
    then, per size, per char, cell_w*cell_h bytes of 8-bit coverage
"""

from __future__ import annotations

import math
import pathlib
import struct
import sys
import zlib

try:
    import AppKit
    import Foundation
except ImportError:  # pragma: no cover - tool, not library
    sys.exit(
        "pyobjc is required and only ships with the system interpreter.\n"
        "Run:  /usr/bin/python3 videokit/make_atlas.py"
    )

FONT_NAME = "Menlo-Regular"
SIZES = (18, 24, 44)
CHARS = "".join(chr(c) for c in range(32, 127)) + "→·"

OUT = pathlib.Path(__file__).with_name("atlas.bin")


def font_for(size: int):
    font = AppKit.NSFont.fontWithName_size_(FONT_NAME, float(size))
    if font is None:
        sys.exit(f"font {FONT_NAME!r} not available on this machine")
    return font


def metrics(size: int) -> tuple[int, int]:
    font = font_for(size)
    advance = font.advancementForGlyph_(font.glyphWithName_("M")).width
    height = font.ascender() - font.descender()
    return int(math.ceil(advance)), int(math.ceil(height)) + 1


def raster(ch: str, size: int, w: int, h: int) -> bytes:
    font = font_for(size)
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 1, False, False, AppKit.NSDeviceWhiteColorSpace, w, 8
    )
    ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(ctx)
    AppKit.NSColor.blackColor().setFill()
    AppKit.NSBezierPath.fillRect_(((0, 0), (w, h)))
    Foundation.NSString.stringWithString_(ch).drawAtPoint_withAttributes_(
        (0, 0),
        {
            AppKit.NSFontAttributeName: font,
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor(),
        },
    )
    ctx.flushGraphics()
    AppKit.NSGraphicsContext.restoreGraphicsState()
    data = rep.bitmapData()
    return bytes(data[: w * h])


def main() -> int:
    header = bytearray(struct.pack("<H", len(SIZES)))
    payload = bytearray()
    for size in SIZES:
        w, h = metrics(size)
        header += struct.pack("<HHH", size, w, h)
        drawn = 0
        for ch in CHARS:
            cell = raster(ch, size, w, h)
            if len(cell) != w * h:
                sys.exit(f"bad cell for {ch!r} at {size}: {len(cell)} != {w * h}")
            if any(v > 40 for v in cell):
                drawn += 1
            payload += cell
        print(f"  size {size:>3}: cell {w}x{h}, {drawn}/{len(CHARS)} glyphs have ink")

    charset = CHARS.encode("utf-8")
    blob = (
        struct.pack("<I", len(charset)) + charset + bytes(header) + bytes(payload)
    )
    OUT.write_bytes(zlib.compress(blob, 9))
    print(f"  wrote {OUT.name}: {OUT.stat().st_size} bytes compressed ({len(blob)} raw)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
