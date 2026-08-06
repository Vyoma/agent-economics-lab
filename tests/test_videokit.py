"""The video must stay true to the code, and the GIF encoder must be correct.

Two separate risks are covered here.

The first is a stale asset: `docs/assets/decision.gif` shows verdicts and counts
on screen. If the decision logic changes and nobody re-renders, the video becomes
a confident lie. `test_committed_video_matches_live_decisions` recomputes every
fact the video asserts and fails if the committed sidecar disagrees.

The second is the GIF encoder itself. Its code-width rule is off-by-one sensitive
in a way no self-written decoder can catch: a wrong encoder paired with a wrong
decoder round-trips perfectly while every real viewer renders noise. A round-trip
test is therefore not sufficient evidence of correctness here, and `RealDecoder`
hands the output to the platform decoder instead, skipping where unavailable.
"""

from __future__ import annotations

import json
import pathlib
import random
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from videokit.raster import (  # noqa: E402
    PALETTE,
    PALETTE_BITS,
    Canvas,
    Font,
    _lzw,
    write_gif,
    write_png,
)

ASSETS = ROOT / "docs" / "assets"
GIF = ASSETS / "decision.gif"
PNG = ASSETS / "decision.png"
FACTS = ASSETS / "decision.json"


def reference_decode(data: bytes, min_code_size: int) -> bytes:
    """Independent GIF-LZW decoder.

    The code-width rule is the asymmetry worth spelling out. A decoder installs
    its dictionary entry one code later than the encoder, so at any point in the
    stream its `next_code` trails by exactly one. The encoder therefore widens at
    `(1 << width) + 1` and the decoder at `(1 << width)`. Pair them wrongly and
    the two still agree with each other while real viewers show noise, which is
    what `RealDecoder` below exists to catch.
    """
    clear = 1 << min_code_size
    eoi = clear + 1
    bits = [(byte >> i) & 1 for byte in data for i in range(8)]
    pos = 0

    def read(width: int) -> int | None:
        nonlocal pos
        if pos + width > len(bits):
            return None
        value = sum(bits[pos + i] << i for i in range(width))
        pos += width
        return value

    out = bytearray()
    table: dict[int, bytes] = {}
    width = min_code_size + 1
    next_code = eoi + 1
    prev: bytes | None = None
    while True:
        code = read(width)
        if code is None or code == eoi:
            break
        if code == clear:
            table, width, next_code, prev = {}, min_code_size + 1, eoi + 1, None
            continue
        if code < clear:
            entry = bytes([code])
        elif code in table:
            entry = table[code]
        elif prev is not None:
            entry = prev + prev[:1]
        else:
            raise AssertionError(f"undecodable code {code}")
        out += entry
        if prev is not None:
            table[next_code] = prev + entry[:1]
            next_code += 1
            if next_code == (1 << width) and width < 12:
                width += 1
        prev = entry
    return bytes(out)


class LzwEncoder(unittest.TestCase):
    def test_round_trips_including_table_resets(self) -> None:
        random.seed(7)
        top = 1 << PALETTE_BITS
        cases = {
            "empty": b"",
            "single": b"\x05",
            "long run": bytes([3]) * 5000,
            "alternating": bytes([0, 9] * 4000),
            "ramp": bytes(i % top for i in range(30_000)),
            "random forces resets": bytes(
                random.randrange(top) for _ in range(200_000)
            ),
        }
        for name, payload in cases.items():
            with self.subTest(case=name):
                encoded = _lzw(payload, PALETTE_BITS)
                self.assertEqual(reference_decode(encoded, PALETTE_BITS), payload)

    def test_run_of_identical_pixels_compresses(self) -> None:
        payload = bytes([1]) * 20_000
        self.assertLess(len(_lzw(payload, PALETTE_BITS)), len(payload) // 20)


class GifStructure(unittest.TestCase):
    def setUp(self) -> None:
        self.font = Font()

    def test_header_palette_and_trailer(self) -> None:
        canvas = Canvas(16, 8, self.font)
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "probe.gif"
            write_gif(out, [canvas, canvas], [10, 10])
            blob = out.read_bytes()
        self.assertEqual(blob[:6], b"GIF89a")
        self.assertEqual(struct.unpack_from("<HH", blob, 6), (16, 8))
        self.assertTrue(blob[10] & 0x80, "global colour table flag must be set")
        self.assertEqual(1 << ((blob[10] & 0x07) + 1), len(PALETTE) // 3)
        self.assertIn(b"NETSCAPE2.0", blob, "loop extension missing")
        self.assertEqual(blob[-1], 0x3B, "missing GIF trailer")
        self.assertEqual(blob.count(b"\x21\xf9\x04"), 2, "one GCE per frame")

    def test_mismatched_frame_sizes_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            write_gif(
                pathlib.Path(tempfile.gettempdir()) / "never.gif",
                [Canvas(4, 4, self.font), Canvas(5, 4, self.font)],
                [10, 10],
            )

    def test_delays_must_match_frames(self) -> None:
        with self.assertRaises(ValueError):
            write_gif(
                pathlib.Path(tempfile.gettempdir()) / "never.gif",
                [Canvas(4, 4, self.font)],
                [10, 10],
            )


class FontAtlas(unittest.TestCase):
    def test_covers_every_character_the_video_draws(self) -> None:
        font = Font()
        facts = json.loads(FACTS.read_text())
        drawn = "".join(
            [facts["verdict"], facts["reduced_verdict"], facts["disabled_gate"]]
            + facts["breaches_shown"]
            + facts["missing_coverage"]
            + [facts["drift"]["claim_boundary"]]
        )
        self.assertEqual(font.missing(drawn), set())

    def test_unknown_glyph_raises_rather_than_drawing_blank(self) -> None:
        canvas = Canvas(40, 40, Font())
        with self.assertRaises(KeyError):
            canvas.text(0, 0, "中", 18, "text")


class VideoIsCurrent(unittest.TestCase):
    """The asset on disk must agree with what the code decides today."""

    def test_assets_exist_and_are_non_trivial(self) -> None:
        for path in (GIF, PNG, FACTS):
            self.assertTrue(path.exists(), f"{path.name} is missing; run: make video")
        self.assertGreater(GIF.stat().st_size, 20_000)
        self.assertGreater(PNG.stat().st_size, 2_000)

    def test_committed_video_matches_live_decisions(self) -> None:
        import render_video

        facts = json.loads(FACTS.read_text())
        live = render_video.gather()

        self.assertEqual(facts["verdict"], live["verdict"])
        self.assertEqual(facts["reduced_verdict"], live["reduced_verdict"])
        self.assertEqual(facts["missing_coverage"], sorted(live["missing"]))
        self.assertEqual(facts["n_checks"], live["n_checks"])
        self.assertEqual(facts["breaches_shown"], live["breaches"][:3])
        for key, value in facts["drift"].items():
            self.assertEqual(value, live["drift"][key], f"drift[{key}] is stale")

    def test_the_video_asserts_the_claim_it_is_built_to_assert(self) -> None:
        """A regression here means the video would show a false headline."""
        facts = json.loads(FACTS.read_text())
        self.assertEqual(facts["reduced_verdict"], "INCOMPLETE")
        self.assertEqual(
            facts["drift"]["fixed_contract_incomplete"], facts["drift"]["comparisons"]
        )
        self.assertGreater(facts["drift"]["dynamic_false_scale_transitions"], 0)

    def test_committed_gif_matches_a_fresh_render(self) -> None:
        """Renders into a temp directory: a test run must not rewrite tracked files.

        Only the GIF is byte-compared. The PNG goes through `zlib.compress`, whose
        output may legitimately differ between zlib versions, so comparing it would
        make this fail on a different platform for no real reason.
        """
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, "render_video.py", "--out-dir", tmp],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )
            fresh = pathlib.Path(tmp) / "decision.gif"
            self.assertEqual(
                GIF.read_bytes(),
                fresh.read_bytes(),
                "docs/assets/decision.gif is stale; run: make video",
            )


@unittest.skipUnless(sys.platform == "darwin", "system GIF decoder is macOS-only")
class RealDecoder(unittest.TestCase):
    """Decode the output with a production decoder rather than a local one.

    This is the only check that can catch an LZW code-width error, because a
    matching pair of wrong encoder and wrong decoder round-trips cleanly.
    """

    def test_system_decoder_reproduces_our_pixels(self) -> None:
        font = Font()
        frames = []
        for f in range(2):
            canvas = Canvas(90, 60, font)
            for y in range(60):
                for x in range(90):
                    canvas.px[y * 90 + x] = (x // 5 + y // 3 + f * 7) % (
                        len(PALETTE) // 3
                    )
            canvas.text(4, 30, f"f{f}", 18, "green")
            frames.append(canvas)

        expected = [bytes(c.px) for c in frames]
        tmpdir = tempfile.TemporaryDirectory()
        gif = pathlib.Path(tmpdir.name) / "realdecoder.gif"
        try:
            write_gif(gif, frames, [10, 10])
            script = r"""
import sys, pathlib, AppKit
gif = pathlib.Path(sys.argv[1])
data = AppKit.NSData.dataWithContentsOfFile_(str(gif))
reps = AppKit.NSBitmapImageRep.imageRepsWithData_(data)
rep = reps[0]
n = int(rep.valueForProperty_(AppKit.NSImageFrameCount))
rows = [str(n)]
for f in range(n):
    rep.setProperty_withValue_(AppKit.NSImageCurrentFrame, f)
    px = []
    for y in range(int(rep.pixelsHigh())):
        for x in range(int(rep.pixelsWide())):
            c = rep.colorAtX_y_(x, y)
            px.append("%d,%d,%d" % (round(c.redComponent()*255),
                                    round(c.greenComponent()*255),
                                    round(c.blueComponent()*255)))
    rows.append(" ".join(px))
print("\n".join(rows))
"""
            proc = subprocess.run(
                ["/usr/bin/python3", "-c", script, str(gif)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                self.skipTest(f"system pyobjc unavailable: {proc.stderr.strip()[:120]}")
            lines = proc.stdout.strip().splitlines()
            self.assertEqual(int(lines[0]), 2, "system decoder saw the wrong frame count")
            for f, row in enumerate(lines[1:]):
                got = row.split()
                want = [
                    ",".join(str(v) for v in PALETTE[i * 3 : i * 3 + 3])
                    for i in expected[f]
                ]
                self.assertEqual(
                    got, want, f"frame {f} differs from what the system decoder read"
                )
        finally:
            tmpdir.cleanup()


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
