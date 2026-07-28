from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .adapters import load_normalized_json_bundle, render_normalized_json
from .assurance import evaluate_bundle
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .claude_code import (
    SOURCE_ID as CLAUDE_CODE_SOURCE_ID,
    SOURCE_VERSION as CLAUDE_CODE_SOURCE_VERSION,
    claude_code_bundle_from_session,
    conversion_contract_template,
    conversion_receipt,
    inspect_claude_code_jsonl,
    load_conversion_contract,
)
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
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert a pinned offline source export into normalized JSON.",
    )
    convert_parser.add_argument(
        "--from",
        dest="source",
        choices=("claude-code",),
        required=True,
    )
    convert_parser.add_argument("--in", dest="input_path", required=True)
    convert_parser.add_argument(
        "--template",
        help="Write a privacy-preserving conversion-contract template.",
    )
    convert_parser.add_argument(
        "--contract",
        help="Completed conversion contract with outcomes, prices, baseline, and policy.",
    )
    convert_parser.add_argument("--out", help="Normalized JSON output path.")
    subparsers.add_parser("capabilities")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "capabilities":
        print("SOURCE ADAPTERS")
        print("source.csv@1")
        print("source.normalized-json@1")
        print(f"{CLAUDE_CODE_SOURCE_ID}@{CLAUDE_CODE_SOURCE_VERSION}")
        print("\nCONVERTERS")
        print("converter.claude-code-jsonl@1")
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
    if args.command == "convert":
        parser = build_parser()
        template_mode = bool(args.template)
        conversion_mode = bool(args.contract or args.out)
        if template_mode and conversion_mode:
            parser.error("--template cannot be combined with --contract or --out")
        if not template_mode and not (args.contract and args.out):
            parser.error("provide --template or both --contract and --out")
        source_path = Path(args.input_path)
        target_path = Path(args.template if template_mode else args.out)
        protected_paths = [source_path]
        if args.contract:
            protected_paths.append(Path(args.contract))
        if any(
            target_path.resolve() == protected.resolve()
            for protected in protected_paths
        ):
            print(
                "INCOMPLETE: conversion output cannot overwrite its input or contract",
                file=sys.stderr,
            )
            return 2
        try:
            session = inspect_claude_code_jsonl(source_path)
            if template_mode:
                content = (
                    json.dumps(
                        conversion_contract_template(session),
                        sort_keys=True,
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            else:
                contract = load_conversion_contract(args.contract)
                bundle = claude_code_bundle_from_session(session, contract)
                receipt = conversion_receipt(session, contract, bundle)
                content = render_normalized_json(bundle, conversion=receipt)
            target_path.write_text(content, encoding="utf-8")
        except (
            ArithmeticError,
            AttributeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            print(f"INCOMPLETE: conversion failed: {error}", file=sys.stderr)
            return 2
        print(f"Wrote {target_path}")
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
        if not args.bundle and len(supplied_csv) != len(csv_paths):
            missing = [name for name, value in csv_paths.items() if not value]
            build_parser().error(
                "provide --bundle or all CSV inputs; missing: " + ", ".join(missing)
            )
        try:
            evidence = (
                load_normalized_json_bundle(args.bundle)
                if args.bundle
                else load_csv_bundle(**csv_paths)
            )
            case = evaluate_bundle(evidence)
        except (
            ArithmeticError,
            AttributeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            print(f"INCOMPLETE: invalid evidence: {error}", file=sys.stderr)
            return 2
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
