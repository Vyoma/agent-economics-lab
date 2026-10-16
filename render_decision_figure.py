"""Render the README evidence figure from live decisions.

    make figure

Every number and verdict is computed through the same public API a user calls.
The output is deliberately static: a repository front door should be scannable,
motion-free by default, and useful when copied into a review or issue.

Output, into --out-dir (default docs/assets):
    decision.png     the README evidence figure
    decision.json    the displayed facts, for independent freshness checks
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
from videokit.raster import Canvas, Font, write_png  # noqa: E402

WIDTH = 1200
HEIGHT = 675
MARGIN = 64
DEFAULT_OUT_DIR = ROOT / "docs" / "assets"
DISABLED_GATE = "gate.acceptable-rate"


def gather() -> dict:
    """Run the real pipeline; do not hand-type claims into the figure."""
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
        evidence, tuple(check for check in checks if check.id != DISABLED_GATE)
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


def render(data: dict | None = None, font: Font | None = None) -> Canvas:
    """Return a compact, deterministic comparison that survives a quick scan."""
    data = data or gather()
    font = font or Font()
    drift = data["drift"]
    comparisons = drift["comparisons"]
    false_scales = drift["dynamic_false_scale_transitions"]
    incomplete = drift["fixed_contract_incomplete"]

    card = Canvas(WIDTH, HEIGHT, font)
    card.fill_rect(MARGIN, 54, 5, 567, "cyan")

    card.text(96, 58, "EVIDENCE CONTRACT DRIFT", 18, "dim")
    card.text(96, 112, "One required gate removed.", 44, "text")
    card.text(96, 176, f"evidence unchanged / removed: {DISABLED_GATE}", 18, "dim")

    card.fill_rect(96, 230, 1018, 1, "dim", level=8)
    card.fill_rect(600, 260, 1, 216, "dim", level=6)

    card.text(96, 270, "INFERRED CONTRACT", 18, "dim")
    card.text(96, 324, f"{false_scales} false SCALE", 44, "red")
    card.text(96, 386, f"in {comparisons} comparisons", 24, "text")
    card.text(96, 430, "answered without required evidence", 18, "dim")

    card.text(648, 270, "FIXED CONTRACT", 18, "dim")
    card.text(648, 324, f"{incomplete} INCOMPLETE", 44, "cyan")
    card.text(648, 386, f"in {comparisons} comparisons", 24, "text")
    card.text(648, 430, f"missing: {', '.join(data['missing'])}", 18, "dim")

    card.fill_rect(96, 508, 1018, 1, "dim", level=8)
    card.text(96, 548, "A missing gate is not a passing gate.", 24, "text")
    card.text(
        96, 594, "Synthetic intervention; not a production failure-rate estimate.", 18, "green"
    )
    return card


def recorded_facts(data: dict) -> dict:
    """Return the exact claims carried by the committed figure."""
    return {
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
        "width": WIDTH,
        "height": HEIGHT,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=DEFAULT_OUT_DIR,
        help="where to write the assets (default: docs/assets)",
    )
    args = parser.parse_args(argv)
    out_dir: pathlib.Path = args.out_dir
    png_path = out_dir / "decision.png"
    facts_path = out_dir / "decision.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = gather()
    write_png(png_path, render(data))
    facts_path.write_text(json.dumps(recorded_facts(data), indent=2, sort_keys=True) + "\n")

    print(f"  live verdict         {data['verdict']}")
    print(
        f"  with gate disabled   {data['reduced_verdict']}"
        f" (missing: {', '.join(data['missing'])})"
    )
    for path in (png_path, facts_path):
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path
        print(f"  {shown}  {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
