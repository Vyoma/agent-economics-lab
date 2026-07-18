from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .adapters import load_normalized_json_bundle
from .assurance import evaluate_bundle
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
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
        return 0
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
