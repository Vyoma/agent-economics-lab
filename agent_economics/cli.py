from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, kimi_client
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
from .claude_code_tree import (
    SOURCE_ID as CLAUDE_CODE_TREE_SOURCE_ID,
    SOURCE_VERSION as CLAUDE_CODE_TREE_SOURCE_VERSION,
    claude_code_tree_bundle_from_session,
    inspect_claude_code_session_tree,
)
from .delegation import assess_bundle_closure
from .frontier import FrontierDecision, run_frontier
from .frontier_report import (
    render_frontier_json,
    render_frontier_markdown,
)
from .io import load_csv_bundle
from .kimi_analyst import analyse_report
from .kimi_judge import judge as kimi_judge
from .models import Decision
from .mutation import mutate, render_markdown as render_mutation_markdown
from .otel_genai import (
    SOURCE_ID as OTEL_GENAI_SOURCE_ID,
    SOURCE_VERSION as OTEL_GENAI_SOURCE_VERSION,
    conversion_contract_template as otel_genai_conversion_contract_template,
    conversion_receipt as otel_genai_conversion_receipt,
    inspect_otel_genai_json,
    otel_genai_bundle_from_session,
)
from .report import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-economics",
        description="Issue an economic assurance case from agent traces and outcomes.",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"agent-economics {__version__}",
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
        choices=("claude-code", "claude-code-tree", "otel-genai"),
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
    mutate_parser = subparsers.add_parser(
        "mutate",
        help="Remove each required gate in turn and report what the engine does.",
    )
    mutate_parser.add_argument("--bundle", required=True)
    mutate_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    mutate_parser.add_argument("--output")
    mutate_parser.add_argument(
        "--ci", action="store_true",
        help="Exit 1 if any required coverage dimension has no enabled provider, "
             "or if the fail-closed invariant is broken.",
    )

    closure_parser = subparsers.add_parser(
        "closure",
        help="Report how much delegated agent work the contract accounts for.",
    )
    closure_parser.add_argument("--bundle", required=True)
    closure_parser.add_argument("--declared", nargs="*", default=None)
    closure_parser.add_argument(
        "--ci", action="store_true",
        help="Exit 1 if any delegated work is unaccounted for.",
    )

    subparsers.add_parser("capabilities")

    judge_parser = subparsers.add_parser(
        "judge",
        help="Label agent task outcomes using Kimi. Writes outcomes.csv + audit sidecar.",
    )
    judge_parser.add_argument("--task-results", required=True,
                              help="CSV with columns: task_id, output, context (optional)")
    judge_parser.add_argument("--rubric", required=True, help="rubric.json path")
    judge_parser.add_argument("--out", required=True, help="Output outcomes.csv path")
    judge_parser.add_argument("--model", default="kimi-k3")
    judge_parser.add_argument("--rate-limit", type=int, default=5,
                              help="Max Kimi API calls per second (0 = unlimited)")
    judge_parser.add_argument("--reasoning-effort",
                              choices=("low", "high", "max"), default="max",
                              help="Kimi K3 reasoning depth (default: max)")

    analyse_parser = subparsers.add_parser(
        "analyse",
        help="Get Kimi recommendations from an evaluate --format json report.",
    )
    analyse_parser.add_argument("--case", required=True,
                                help="JSON report from `evaluate --format json`")
    analyse_parser.add_argument("--policy", help="policy.json for precise threshold gaps")
    analyse_parser.add_argument("--baseline", help="baseline.json for counterfactual context")
    analyse_parser.add_argument("--model", default="kimi-k3")
    analyse_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    analyse_parser.add_argument("--out", help="Output path (default: stdout)")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"mutate", "closure"}:
        try:
            bundle = load_normalized_json_bundle(Path(args.bundle))
        except (OSError, ValueError) as error:
            print(f"INCOMPLETE: invalid evidence: {error}", file=sys.stderr)
            return 2
        if args.command == "closure":
            declared = None if args.declared is None else tuple(args.declared)
            report = assess_bundle_closure(bundle, declared=declared)
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
            return 1 if args.ci and report.unaccounted else 0
        report = mutate(bundle)
        rendered = (
            json.dumps(report.to_dict(), indent=2, sort_keys=True)
            if args.format == "json"
            else render_mutation_markdown(report)
        )
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        print(rendered)
        # Gate on the harness properties, not the dynamic-coverage comparison.
        if args.ci and (
            report.unprovided_coverage or not report.fail_closed_conformance
        ):
            return 1
        return 0
    if args.command == "capabilities":
        print("SOURCE ADAPTERS")
        print("source.csv@1")
        print("source.normalized-json@1")
        print(f"{CLAUDE_CODE_SOURCE_ID}@{CLAUDE_CODE_SOURCE_VERSION}")
        print(
            f"{CLAUDE_CODE_TREE_SOURCE_ID}@{CLAUDE_CODE_TREE_SOURCE_VERSION}"
        )
        print(f"{OTEL_GENAI_SOURCE_ID}@{OTEL_GENAI_SOURCE_VERSION}")
        print("\nCONVERTERS")
        print("converter.claude-code-jsonl@1")
        print("converter.claude-code-session-tree@1")
        print("converter.otel-genai@1")
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
        print("\nINFERENCE")
        print(
            f"provider  {kimi_client.PROVIDER}  "
            f"({kimi_client.API_KEY_ENV_VAR} required)"
        )
        print(
            f"model     {kimi_client.DEFAULT_MODEL}  "
            f"reasoning_effort={kimi_client.DEFAULT_REASONING_EFFORT}"
        )
        print("egress    agent_economics.kimi_client  (single call path)")
        print("kimi-judge@1    label outcomes against a frozen rubric")
        print("kimi-analyst@1  recommend fixes from a decided case")
        print("The decision kernel performs no inference and stays deterministic.")
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
        if args.source == "claude-code-tree":
            subagent_dir = source_path.with_suffix("") / "subagents"
            if subagent_dir.is_dir():
                protected_paths.extend(
                    path
                    for path in subagent_dir.rglob("*")
                    if path.is_file()
                )
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
            if args.source == "claude-code":
                session = inspect_claude_code_jsonl(source_path)
                template = conversion_contract_template(session)
                if not template_mode:
                    contract = load_conversion_contract(args.contract)
                    bundle = claude_code_bundle_from_session(session, contract)
                    receipt = conversion_receipt(session, contract, bundle)
            elif args.source == "claude-code-tree":
                session = inspect_claude_code_session_tree(source_path)
                template = conversion_contract_template(session)
                if not template_mode:
                    contract = load_conversion_contract(args.contract)
                    bundle = claude_code_tree_bundle_from_session(
                        session,
                        contract,
                    )
                    receipt = conversion_receipt(session, contract, bundle)
            else:
                session = inspect_otel_genai_json(source_path)
                template = otel_genai_conversion_contract_template(session)
                if not template_mode:
                    contract = load_conversion_contract(args.contract)
                    bundle = otel_genai_bundle_from_session(session, contract)
                    receipt = otel_genai_conversion_receipt(
                        session, contract, bundle
                    )
            if template_mode:
                content = (
                    json.dumps(
                        template,
                        sort_keys=True,
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            else:
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
    if args.command == "judge":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        try:
            kimi_judge(
                args.task_results, args.rubric, args.out,
                model=args.model, rate_limit=args.rate_limit,
                reasoning_effort=args.reasoning_effort,
            )
            return 0
        except (RuntimeError, ValueError, OSError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
    if args.command == "analyse":
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        try:
            report = json.loads(Path(args.case).read_text())
            policy = json.loads(Path(args.policy).read_text()) if args.policy else None
            baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else None
            result = analyse_report(report, policy, baseline, model=args.model)
        except (RuntimeError, ValueError, KeyError, OSError, json.JSONDecodeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        output = (
            json.dumps(result.to_dict(), indent=2)
            if args.format == "json"
            else result.render_markdown()
        )
        if args.out:
            Path(args.out).write_text(output)
        print(output)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
