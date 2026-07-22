from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .adapters import load_normalized_json_bundle
from .assurance import evaluate_bundle
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .frontier import FrontierDecision, run_frontier
from .frontier_report import (
    render_frontier_json,
    render_frontier_markdown,
    render_frontier_svg,
)
from .io import load_csv_bundle
from .models import Decision
from .report import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-economics",
        description="Issue an economic assurance case from agent traces and outcomes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--bundle")
    evaluate_parser.add_argument("--traces")
    evaluate_parser.add_argument("--outcomes")
    evaluate_parser.add_argument("--rates")
    evaluate_parser.add_argument("--baseline")
    evaluate_parser.add_argument("--policy")
    evaluate_parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    evaluate_parser.add_argument(
        "--ci",
        action="store_true",
        help="Return decision-specific exit codes: 0 SCALE, 2 INCOMPLETE, 3 ASSIST, 4 STOP.",
    )
    evaluate_parser.add_argument("--output")
    frontier_parser = subparsers.add_parser(
        "frontier",
        help="Compare configurations on identical task input and rubric identities.",
    )
    frontier_parser.add_argument("plan")
    frontier_parser.add_argument("--output-dir", required=True)
    frontier_parser.add_argument(
        "--verify-dir",
        help="Fail if generated frontier artifacts differ from this directory.",
    )
    subparsers.add_parser("capabilities")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "capabilities":
        print("SOURCE ADAPTERS")
        print("source.csv@1")
        print("source.normalized-json@1")
        print("\nCHECKS")
        for check in default_checks():
            required = "required" if check.covers & DEFAULT_REQUIRED_COVERAGE else "optional"
            print(f"{check.manifest_id}  {check.mode.value}  {required}")
        print("\nRENDERERS")
        print("renderer.markdown@1")
        print("renderer.json@1")
        print("renderer.frontier-markdown@1")
        print("renderer.frontier-json@1")
        print("renderer.frontier-svg@1")
        print("\nEXPERIMENTS")
        print("experiment.paired-budget-frontier@1")
        return 0
    if args.command == "frontier":
        output_dir = Path(args.output_dir)
        if args.verify_dir and output_dir.resolve() == Path(args.verify_dir).resolve():
            print(
                "INCOMPLETE: --output-dir and --verify-dir must be different directories",
                file=sys.stderr,
            )
            return 2
        try:
            case = run_frontier(args.plan)
        except (OSError, ValueError) as error:
            print(f"INCOMPLETE: invalid frontier plan: {error}", file=sys.stderr)
            return 2
        artifacts = {
            "frontier.md": render_frontier_markdown(case),
            "frontier.json": render_frontier_json(case),
            "frontier.svg": render_frontier_svg(case),
        }
        if args.verify_dir:
            verify_dir = Path(args.verify_dir)
            mismatches = [
                name
                for name, content in artifacts.items()
                if not (verify_dir / name).exists()
                or (verify_dir / name).read_text(encoding="utf-8") != content
            ]
            if mismatches:
                print("Generated frontier artifacts differ: " + ", ".join(mismatches))
                return 1
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in artifacts.items():
            (output_dir / name).write_text(content, encoding="utf-8")
        print(artifacts["frontier.md"])
        return {
            FrontierDecision.ADOPT: 0,
            FrontierDecision.INCOMPLETE: 2,
            FrontierDecision.HOLD: 3,
        }[case.decision]
    if args.command == "evaluate":
        csv_paths = {
            "traces": args.traces,
            "outcomes": args.outcomes,
            "rates": args.rates,
            "baseline": args.baseline,
            "policy": args.policy,
        }
        supplied_csv = [name for name, value in csv_paths.items() if value]
        if args.bundle and supplied_csv:
            build_parser().error("--bundle cannot be combined with CSV input options")
        if args.bundle:
            evidence = load_normalized_json_bundle(args.bundle)
        elif len(supplied_csv) == len(csv_paths):
            evidence = load_csv_bundle(**csv_paths)
        else:
            missing = [name for name, value in csv_paths.items() if not value]
            build_parser().error(
                "provide --bundle or all CSV inputs; missing: " + ", ".join(missing)
            )
        case = evaluate_bundle(evidence)
        report = render_json(case) if args.format == "json" else render_markdown(case)
        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
        print(report)
        if args.ci:
            return {
                Decision.SCALE: 0,
                Decision.INCOMPLETE: 2,
                Decision.ASSIST: 3,
                Decision.STOP: 4,
            }[case.decision]
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
