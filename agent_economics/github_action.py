from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .cli import main as cli_main


CI_DECISIONS = {
    0: "SCALE",
    2: "INCOMPLETE",
    3: "ASSIST",
    4: "STOP",
}


@dataclass(frozen=True)
class ActionInputs:
    bundle: str = ""
    traces: str = ""
    outcomes: str = ""
    rates: str = ""
    baseline: str = ""
    policy: str = ""
    adapter: str = ""
    session: str = ""
    contract: str = ""


@dataclass(frozen=True)
class ActionResult:
    decision: str
    exit_code: int
    report_path: Path
    stdout: str = ""
    stderr: str = ""


def _present(value: str) -> bool:
    return bool(value.strip())


def _select_mode(inputs: ActionInputs) -> str:
    csv_values = {
        "traces": inputs.traces,
        "outcomes": inputs.outcomes,
        "rates": inputs.rates,
        "baseline": inputs.baseline,
        "policy": inputs.policy,
    }
    adapter_values = {
        "adapter": inputs.adapter,
        "session": inputs.session,
        "contract": inputs.contract,
    }
    active_modes = [
        name
        for name, active in (
            ("bundle", _present(inputs.bundle)),
            ("csv", any(_present(value) for value in csv_values.values())),
            ("adapter", any(_present(value) for value in adapter_values.values())),
        )
        if active
    ]
    if len(active_modes) != 1:
        rendered = ", ".join(active_modes) if active_modes else "none"
        raise ValueError(
            "provide exactly one input mode: bundle, all five CSV inputs, or "
            f"adapter + session + contract; active modes: {rendered}"
        )
    mode = active_modes[0]
    if mode == "csv":
        missing = [
            name for name, value in csv_values.items() if not _present(value)
        ]
        if missing:
            raise ValueError(
                "CSV mode requires traces, outcomes, rates, baseline, and policy; "
                "missing: " + ", ".join(missing)
            )
    if mode == "adapter":
        missing = [
            name for name, value in adapter_values.items() if not _present(value)
        ]
        if missing:
            raise ValueError(
                "adapter mode requires adapter, session, and contract; missing: "
                + ", ".join(missing)
            )
        if inputs.adapter != "claude-code":
            raise ValueError(
                f"unsupported adapter {inputs.adapter!r}; supported: claude-code"
            )
    return mode


def _invoke_cli(arguments: Sequence[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli_main(arguments)
    except SystemExit as error:
        exit_code = int(error.code) if isinstance(error.code, int) else 2
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _incomplete_report(reason: str) -> str:
    rendered_reason = reason.strip() or "The action runner returned no diagnostic."
    return (
        "# Agent Economic Assurance Case\n\n"
        "**Decision: INCOMPLETE**\n\n"
        "The GitHub Action refused to evaluate because its input contract was "
        "incomplete or invalid.\n\n"
        "## Refusal reason\n\n"
        f"{rendered_reason}\n"
    )


def _write_incomplete(report_path: Path, reason: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_incomplete_report(reason), encoding="utf-8")


def run_action(inputs: ActionInputs, report_path: Path) -> ActionResult:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = _select_mode(inputs)
    except ValueError as error:
        _write_incomplete(report_path, str(error))
        return ActionResult("INCOMPLETE", 2, report_path, stderr=str(error) + "\n")

    conversion_stdout = ""
    conversion_stderr = ""
    with tempfile.TemporaryDirectory(prefix="agent-economics-action-") as directory:
        if mode == "bundle":
            evaluate_arguments = ["evaluate", "--bundle", inputs.bundle]
        elif mode == "csv":
            evaluate_arguments = [
                "evaluate",
                "--traces",
                inputs.traces,
                "--outcomes",
                inputs.outcomes,
                "--rates",
                inputs.rates,
                "--baseline",
                inputs.baseline,
                "--policy",
                inputs.policy,
            ]
        else:
            bundle_path = Path(directory) / "converted-bundle.json"
            conversion_code, conversion_stdout, conversion_stderr = _invoke_cli(
                [
                    "convert",
                    "--from",
                    inputs.adapter,
                    "--in",
                    inputs.session,
                    "--contract",
                    inputs.contract,
                    "--out",
                    str(bundle_path),
                ]
            )
            if conversion_code != 0:
                reason = conversion_stderr or conversion_stdout
                _write_incomplete(report_path, reason)
                return ActionResult(
                    "INCOMPLETE",
                    2,
                    report_path,
                    stdout=conversion_stdout,
                    stderr=conversion_stderr,
                )
            evaluate_arguments = ["evaluate", "--bundle", str(bundle_path)]

        exit_code, evaluation_stdout, evaluation_stderr = _invoke_cli(
            evaluate_arguments
            + [
                "--format",
                "markdown",
                "--ci",
                "--output",
                str(report_path),
            ]
        )

    stdout = conversion_stdout + evaluation_stdout
    stderr = conversion_stderr + evaluation_stderr
    if exit_code not in CI_DECISIONS:
        _write_incomplete(
            report_path,
            stderr or stdout or f"unexpected evaluator exit code: {exit_code}",
        )
        return ActionResult(
            "INCOMPLETE",
            2,
            report_path,
            stdout=stdout,
            stderr=stderr,
        )
    if not report_path.is_file() or not report_path.read_text(
        encoding="utf-8"
    ).strip():
        _write_incomplete(
            report_path,
            stderr or stdout or "the evaluator did not write a report",
        )
        return ActionResult(
            "INCOMPLETE",
            2,
            report_path,
            stdout=stdout,
            stderr=stderr,
        )
    return ActionResult(
        CI_DECISIONS[exit_code],
        exit_code,
        report_path,
        stdout=stdout,
        stderr=stderr,
    )


def _write_github_outputs(path: Path, result: ActionResult) -> None:
    values = {
        "decision": result.decision,
        "exit-code": str(result.exit_code),
        "report": str(result.report_path),
    }
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            delimiter = "AGENT_ECONOMICS_OUTPUT"
            while delimiter in value:
                delimiter += "_X"
            stream.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Internal fail-closed runner for the composite GitHub Action."
    )
    for name in (
        "bundle",
        "traces",
        "outcomes",
        "rates",
        "baseline",
        "policy",
        "adapter",
        "session",
        "contract",
    ):
        parser.add_argument(f"--{name}", default="")
    parser.add_argument("--report")
    parser.add_argument("--report-dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if bool(args.report) == bool(args.report_dir):
        raise SystemExit("provide exactly one of --report or --report-dir")
    if args.report:
        report_path = Path(args.report)
    else:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix="agent-economics-",
            suffix=".md",
            dir=report_dir,
        )
        os.close(descriptor)
        report_path = Path(name)
    result = run_action(
        ActionInputs(
            bundle=args.bundle,
            traces=args.traces,
            outcomes=args.outcomes,
            rates=args.rates,
            baseline=args.baseline,
            policy=args.policy,
            adapter=args.adapter,
            session=args.session,
            contract=args.contract,
        ),
        report_path,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if not result.stdout and result.report_path.is_file():
        print(result.report_path.read_text(encoding="utf-8"), end="")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        _write_github_outputs(Path(github_output), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
