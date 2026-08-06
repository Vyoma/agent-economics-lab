"""Indexed-colour raster canvas, PNG writer and animated GIF writer.

Standard library only. This exists because the repository declares zero runtime
dependencies and `make video` must not be the thing that breaks that.

Colour is handled with *ramps* rather than quantisation. Each text colour gets a
fixed 16-step ramp blended from the background, so antialiased glyph coverage maps
straight onto a palette index and no quantiser is ever needed. A handful of ramps
keeps the palette near 100 entries, which also makes the GIF's LZW stream compress
well.
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
    # Pad to the next power of two, as the GIF spec requires.
    size = 1
    while size < len(entries):
        size <<= 1
    table += bytes(3 * (size - len(entries)))
    return bytes(table), ramp_base


PALETTE, RAMP_BASE = build_palette()
PALETTE_BITS = max(2, (len(PALETTE) // 3 - 1).bit_length())


class Canvas:
    """Indexed-colour framebuffer. Index 0 is the background."""

    def __init__(self, width: int, height: int, font: Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.px = bytearray(width * height)

    def clone(self) -> "Canvas":
        other = Canvas(self.width, self.height, self.font)
        other.px[:] = self.px
        return other

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


# --------------------------------------------------------------------------- GIF


class _BitWriter:
    """LSB-first bit packing, as GIF requires."""

    def __init__(self) -> None:
        self.out = bytearray()
        self._acc = 0
        self._nbits = 0

    def write(self, code: int, width: int) -> None:
        self._acc |= code << self._nbits
        self._nbits += width
        while self._nbits >= 8:
            self.out.append(self._acc & 0xFF)
            self._acc >>= 8
            self._nbits -= 8

    def flush(self) -> None:
        if self._nbits:
            self.out.append(self._acc & 0xFF)
            self._acc = 0
            self._nbits = 0


def _lzw(indices: bytes, min_code_size: int) -> bytes:
    """GIF-variant LZW. The dictionary is keyed on (prefix_code, byte).

    Single bytes are their own codes, so the dictionary only ever holds the
    concatenations. The table is reset with a clear code at 4096 entries.

    The code-width rule is the one detail worth stating, because getting it wrong
    produces a stream that a self-written decoder still round-trips while every
    real decoder renders as garbage. A GIF decoder installs its dictionary entry
    one code later than the encoder does, so it always trails by one. The encoder
    must therefore widen at `next_code == (1 << width) + 1`, not at
    `(1 << width)`. Verified against the system GIF decoder in
    `tests/test_videokit.py`, which is the only check that can catch this.
    """
    clear = 1 << min_code_size
    eoi = clear + 1
    writer = _BitWriter()

    table: dict[tuple[int, int], int] = {}
    width = min_code_size + 1
    next_code = eoi + 1

    writer.write(clear, width)
    if not indices:
        writer.write(eoi, width)
        writer.flush()
        return bytes(writer.out)

    prefix = indices[0]
    for value in indices[1:]:
        key = (prefix, value)
        found = table.get(key)
        if found is not None:
            prefix = found
            continue
        writer.write(prefix, width)
        table[key] = next_code
        next_code += 1
        if next_code == 4096:
            writer.write(clear, width)
            table.clear()
            width = min_code_size + 1
            next_code = eoi + 1
        elif next_code == (1 << width) + 1 and width < 12:
            width += 1
        prefix = value
    writer.write(prefix, width)
    writer.write(eoi, width)
    writer.flush()
    return bytes(writer.out)


def _sub_blocks(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 255):
        piece = data[i : i + 255]
        out.append(len(piece))
        out += piece
    out.append(0)
    return bytes(out)


def write_gif(
    path: pathlib.Path,
    frames: list[Canvas],
    delays_cs: list[int],
    loop: int = 0,
) -> None:
    if len(frames) != len(delays_cs):
        raise ValueError("frames and delays must be the same length")
    if not frames:
        raise ValueError("no frames")
    w, h = frames[0].width, frames[0].height
    min_code_size = PALETTE_BITS

    out = bytearray(b"GIF89a")
    out += struct.pack("<HH", w, h)
    out += bytes((0x80 | (PALETTE_BITS - 1), 0, 0))
    out += PALETTE
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"

    for canvas, delay in zip(frames, delays_cs):
        if canvas.width != w or canvas.height != h:
            raise ValueError("all frames must share dimensions")
        out += b"\x21\xf9\x04\x04" + struct.pack("<H", delay) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHH", 0, 0, w, h) + b"\x00"
        out += bytes((min_code_size,))
        out += _sub_blocks(_lzw(bytes(canvas.px), min_code_size))
    out += b"\x3b"
    path.write_bytes(bytes(out))
