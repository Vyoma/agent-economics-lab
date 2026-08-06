"""Render the explainer video and poster still from live decisions.

    make video

Every number and every verdict shown is computed here, at render time, by calling
the same public API a user calls. Nothing in the video is typed in by hand, so it
cannot drift away from what the code actually does. If a decision changes, the
video changes with it, and `tests/test_videokit.py` fails if the committed asset
no longer matches what the code decides today.

Output, into --out-dir (default docs/assets):
    decision.gif     animated, loops, for sharing
    decision.png     the key still, for the README
    decision.json    the on-screen facts, so a test can detect a stale asset
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent_economics import (  # noqa: E402
    default_checks,
    evaluate_bundle,
    load_csv_bundle,
)
from videokit.raster import Canvas, Font, write_gif, write_png  # noqa: E402

WIDTH = HEIGHT = 900
MARGIN = 56
SMALL, BODY, HEAD = 18, 24, 44

REVEAL_CS = 14
HOLD_CS = 190
FINAL_HOLD_CS = 260

DEFAULT_OUT_DIR = ROOT / "docs" / "assets"

DISABLED_GATE = "gate.acceptable-rate"


# --------------------------------------------------------------------- live data


def gather() -> dict:
    """Run the real pipeline. Every string below is derived, never literal."""
    evidence = load_csv_bundle(
        traces=ROOT / "examples/support_trace.csv",
        outcomes=ROOT / "examples/outcomes.csv",
        rates=ROOT / "examples/rates.json",
        baseline=ROOT / "examples/baseline.json",
        policy=ROOT / "examples/policy.json",
    )
    checks = default_checks()
    full = evaluate_bundle(evidence, checks)
    reduced = evaluate_bundle(
        evidence, tuple(c for c in checks if c.id != DISABLED_GATE)
    )
    drift = json.loads(
        (ROOT / "research/results/decision-coverage-drift/summary.json").read_text()
    )
    return {
        "verdict": full.decision.value,
        "breaches": list(full.breaches),
        "reduced_verdict": reduced.decision.value,
        "missing": list(reduced.missing_coverage),
        "n_checks": len(checks),
        "drift": drift,
    }


# ----------------------------------------------------------------------- scenes


def scenes(data: dict) -> list[list[tuple[str, int, str]]]:
    d = data["drift"]
    breaches = data["breaches"][:3]

    intro = [
        ("AGENT ECONOMICS LAB", SMALL, "dim"),
        ("", BODY, "text"),
        ("Your agent passed", HEAD, "text"),
        ("every enabled check.", HEAD, "text"),
        ("", BODY, "text"),
        ("Did every required", HEAD, "cyan"),
        ("check run?", HEAD, "cyan"),
        ("", BODY, "text"),
        ("Those are different questions.", BODY, "dim"),
    ]

    demo = [
        ("$ make demo", BODY, "green"),
        ("", BODY, "text"),
        (f"{data['n_checks']} checks ran on bundled evidence.", BODY, "dim"),
        ("", BODY, "text"),
    ]
    for line in breaches:
        demo.append((f"  FAIL  {line}", BODY, "red"))
    demo += [
        ("", BODY, "text"),
        (f"DECISION: {data['verdict']}", HEAD, "amber"),
        ("The agent works. It is not yet", BODY, "dim"),
        ("cheap enough to expand.", BODY, "dim"),
    ]

    drift_scene = [
        ("$ make modularity", BODY, "green"),
        ("", BODY, "text"),
        (f"  removed  {DISABLED_GATE}", BODY, "dim"),
        ("  evidence unchanged", BODY, "dim"),
        ("", BODY, "text"),
        ("An engine that infers its", BODY, "text"),
        ("requirements shrinks its contract", BODY, "text"),
        ("and answers anyway:", BODY, "text"),
        (
            f"  {d['dynamic_false_scale_transitions']} false SCALE"
            f" in {d['comparisons']} comparisons",
            BODY,
            "red",
        ),
        ("", BODY, "text"),
        ("A fixed contract cannot:", BODY, "text"),
        (
            f"  {data['reduced_verdict']}"
            f"  ({d['fixed_contract_incomplete']}/{d['comparisons']})",
            HEAD,
            "cyan",
        ),
        (f"  missing: {', '.join(data['missing'])}", BODY, "dim"),
    ]

    closing = [
        ("A missing gate", HEAD, "text"),
        ("is not a passing gate.", HEAD, "text"),
        ("", BODY, "text"),
        (d["claim_boundary"], SMALL, "dim"),
        ("", BODY, "text"),
        ("github.com/Vyoma/agent-economics-lab", BODY, "cyan"),
        ("", SMALL, "text"),
        ("zero dependencies  ·  Apache-2.0", SMALL, "dim"),
    ]

    return [intro, demo, drift_scene, closing]


# ---------------------------------------------------------------------- drawing


def line_height(font: Font, size: int) -> int:
    return font.cell(size)[1] + (8 if size >= HEAD else 4)


def render(font: Font, data: dict) -> tuple[list[Canvas], list[int], Canvas]:
    frames: list[Canvas] = []
    delays: list[int] = []
    poster: Canvas | None = None

    all_scenes = scenes(data)
    for scene_index, lines in enumerate(all_scenes):
        canvas = Canvas(WIDTH, HEIGHT, font)
        total = sum(line_height(font, size) for _, size, _ in lines)
        if total + 2 * MARGIN > HEIGHT:
            raise SystemExit(
                f"scene {scene_index} is {total}px tall, too tall for {HEIGHT}px"
            )
        y = max(MARGIN, (HEIGHT - total) // 2)
        for text, size, color in lines:
            if text:
                # Fail loudly rather than clipping a live-derived string.
                span = canvas.measure(text, size)
                if MARGIN + span > WIDTH - 8:
                    raise SystemExit(
                        f"scene {scene_index}: line overflows by "
                        f"{MARGIN + span - (WIDTH - 8)}px: {text!r}"
                    )
                canvas.text(MARGIN, y, text, size, color)
            y += line_height(font, size)
            frames.append(canvas.clone())
            delays.append(REVEAL_CS)
        # Replace the last reveal delay with a hold on the finished scene.
        delays[-1] = FINAL_HOLD_CS if scene_index == len(all_scenes) - 1 else HOLD_CS
        if scene_index == 2:
            poster = frames[-1]

    assert poster is not None
    return frames, delays, poster


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=DEFAULT_OUT_DIR,
        help="where to write the assets (default: docs/assets). Tests render to a "
        "temporary directory so that a test run never rewrites tracked files.",
    )
    args = parser.parse_args(argv)
    out_dir: pathlib.Path = args.out_dir
    gif_path = out_dir / "decision.gif"
    png_path = out_dir / "decision.png"
    facts_path = out_dir / "decision.json"

    out_dir.mkdir(parents=True, exist_ok=True)
    font = Font()
    data = gather()

    print(f"  live verdict         {data['verdict']}")
    print(f"  with gate disabled   {data['reduced_verdict']}"
          f" (missing: {', '.join(data['missing'])})")
    print(f"  breaches shown       {len(data['breaches'][:3])}")

    frames, delays, poster = render(font, data)
    write_png(png_path, poster)
    write_gif(gif_path, frames, delays)

    # The facts the video asserts on screen, recorded so a test can recompute them
    # and fail if the committed asset has gone stale. Byte-comparing the PNG would
    # be flaky instead, because zlib output can differ between zlib versions.
    facts = {
        "verdict": data["verdict"],
        "reduced_verdict": data["reduced_verdict"],
        "missing_coverage": sorted(data["missing"]),
        "disabled_gate": DISABLED_GATE,
        "breaches_shown": data["breaches"][:3],
        "n_checks": data["n_checks"],
        "drift": {
            key: data["drift"][key]
            for key in (
                "comparisons",
                "dynamic_false_scale_transitions",
                "fixed_contract_incomplete",
                "claim_boundary",
            )
        },
        "frames": len(frames),
        "width": WIDTH,
        "height": HEIGHT,
    }
    facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

    seconds = sum(delays) / 100
    print(f"  frames               {len(frames)}  ({seconds:.1f}s loop)")
    for path in (gif_path, png_path, facts_path):
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path
        print(f"  {shown}  {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
