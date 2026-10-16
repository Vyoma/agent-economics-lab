"""Indexed-colour raster canvas and deterministic PNG writer.

Standard library only. This exists because the repository declares zero runtime
dependencies and generated public figures must not be the thing that breaks that.

Colour is handled with *ramps* rather than quantisation. Each text colour gets a
fixed 16-step ramp blended from the background, so antialiased glyph coverage maps
straight onto a palette index and no quantiser is ever needed.
"""

from __future__ import annotations

import pathlib
import struct
import zlib

ATLAS = pathlib.Path(__file__).with_name("atlas.bin")

RAMP_STEPS = 16

# name -> (r, g, b) at full coverage
COLORS: dict[str, tuple[int, int, int]] = {
    "bg": (0x0B, 0x0F, 0x14),
    "dim": (0x5C, 0x6B, 0x7A),
    "text": (0xE6, 0xED, 0xF3),
    "green": (0x3F, 0xD6, 0x8C),
    "amber": (0xF2, 0xB2, 0x4B),
    "red": (0xF2, 0x6D, 0x6D),
    "cyan": (0x5C, 0xC8, 0xF5),
}


class Font:
    """Glyph cells parsed from the checked-in atlas."""

    def __init__(self, path: pathlib.Path = ATLAS) -> None:
        blob = zlib.decompress(path.read_bytes())
        (n,) = struct.unpack_from("<I", blob, 0)
        off = 4
        self.charset = blob[off : off + n].decode("utf-8")
        off += n
        (nsizes,) = struct.unpack_from("<H", blob, off)
        off += 2
        self._sizes: dict[int, tuple[int, int, int]] = {}
        cursor_specs = []
        for _ in range(nsizes):
            px, w, h = struct.unpack_from("<HHH", blob, off)
            off += 6
            cursor_specs.append((px, w, h))
        for px, w, h in cursor_specs:
            self._sizes[px] = (w, h, off)
            off += w * h * len(self.charset)
        self._blob = blob
        self._index = {ch: i for i, ch in enumerate(self.charset)}

    @property
    def sizes(self) -> tuple[int, ...]:
        return tuple(sorted(self._sizes))

    def cell(self, size: int) -> tuple[int, int]:
        w, h, _ = self._sizes[size]
        return w, h

    def glyph(self, ch: str, size: int) -> tuple[bytes, int, int]:
        w, h, base = self._sizes[size]
        idx = self._index.get(ch)
        if idx is None:
            raise KeyError(f"glyph {ch!r} is not in the atlas charset")
        start = base + idx * w * h
        return self._blob[start : start + w * h], w, h

    def missing(self, text: str) -> set[str]:
        return {ch for ch in text if ch not in self._index and ch != "\n"}


def build_palette() -> tuple[bytes, dict[str, int]]:
    """Palette bytes plus the base index of each colour's ramp."""
    bg = COLORS["bg"]
    entries: list[tuple[int, int, int]] = [bg]
    ramp_base: dict[str, int] = {}
    for name, rgb in COLORS.items():
        if name == "bg":
            continue
        ramp_base[name] = len(entries)
        for step in range(RAMP_STEPS):
            t = step / (RAMP_STEPS - 1)
            entries.append(
                tuple(round(bg[i] + (rgb[i] - bg[i]) * t) for i in range(3))  # type: ignore[misc]
            )
    table = bytearray()
    for r, g, b in entries:
        table += bytes((r, g, b))
    # Keep a stable power-of-two indexed palette across generated PNGs.
    size = 1
    while size < len(entries):
        size <<= 1
    table += bytes(3 * (size - len(entries)))
    return bytes(table), ramp_base


PALETTE, RAMP_BASE = build_palette()


class Canvas:
    """Indexed-colour framebuffer. Index 0 is the background."""

    def __init__(self, width: int, height: int, font: Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.px = bytearray(width * height)

    def fill_rect(self, x: int, y: int, w: int, h: int, color: str, level: int = RAMP_STEPS - 1) -> None:
        idx = 0 if color == "bg" else RAMP_BASE[color] + level
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes([idx]) * (x1 - x0)
        for yy in range(y0, y1):
            start = yy * self.width + x0
            self.px[start : start + (x1 - x0)] = row

    def text(self, x: int, y: int, s: str, size: int, color: str) -> int:
        """Draw `s` with its top-left at (x, y). Returns the advance in pixels."""
        missing = self.font.missing(s)
        if missing:
            raise KeyError(f"atlas is missing glyphs {sorted(missing)!r} for {s!r}")
        base = RAMP_BASE[color]
        cw, _cell_h = self.font.cell(size)
        pen = x
        for character in s:
            cell, w, h = self.font.glyph(character, size)
            for row in range(h):
                ty = y + row
                if not (0 <= ty < self.height):
                    continue
                rowoff = ty * self.width
                celloff = row * w
                for col in range(w):
                    cov = cell[celloff + col]
                    if cov < 8:
                        continue
                    tx = pen + col
                    if not (0 <= tx < self.width):
                        continue
                    level = cov * (RAMP_STEPS - 1) // 255
                    if level:
                        self.px[rowoff + tx] = base + level
            pen += cw
        return pen - x

    def measure(self, s: str, size: int) -> int:
        cw, _ = self.font.cell(size)
        return cw * len(s)


# --------------------------------------------------------------------------- PNG


def write_png(path: pathlib.Path, canvas: Canvas) -> None:
    """Indexed PNG. Simple enough to trust, which makes it the verification path."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 3, 0, 0, 0)
    raw = bytearray()
    for y in range(canvas.height):
        raw += b"\x00"
        raw += canvas.px[y * canvas.width : (y + 1) * canvas.width]
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"PLTE", PALETTE)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
