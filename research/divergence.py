"""Find one quantity computed two ways, in any Python package.

This is the detector from `probe_sites.py`, lifted out of the repository that
produced it. That move is the whole point. A rule abstracted from five defects
and then evaluated on the same codebase is fitted to its own training set, and
no claim survives that. The only way to learn whether divergence-hunting finds
anything is to point it at code it has never seen.

The signal is deliberately narrow and fully mechanical, requiring no knowledge
of what the package does:

    A function has a parameter with a default. Some call sites pass it and
    others omit it.

An optional parameter every caller omits is dead. One every caller passes is
not optional. Disagreement is the interesting case, because it means at least
one author judged the argument necessary and at least one did not, for the same
function. That is where D10 lived: `assess_closure` grew a `rates` parameter and
one caller kept omitting it while holding rates on the object in its hand.

A divergence is not a defect. Most are deliberate. The output is a ranked
reading list, not a verdict, and the ranking is by how lopsided the disagreement
is: one caller out of nine differing from the other eight is more interesting
than a four-five split.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import pathlib
import sys


@dataclasses.dataclass(frozen=True)
class Divergence:
    function: str
    parameter: str
    passes: tuple[str, ...]
    omits: tuple[str, ...]

    @property
    def total(self) -> int:
        return len(self.passes) + len(self.omits)

    @property
    def lopsidedness(self) -> float:
        """1.0 when a single call site disagrees with every other one.

        A lone dissenter is worth reading. An even split usually means the
        parameter genuinely varies by context.
        """
        minority = min(len(self.passes), len(self.omits))
        return 1.0 - (minority / (self.total / 2))


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    if root.is_file():
        return [root]
    return [
        path
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts and "/test" not in str(path)
    ]


def _parsed(root: pathlib.Path) -> list[tuple[pathlib.Path, ast.Module]]:
    trees = []
    for path in _python_files(root):
        try:
            trees.append((path, ast.parse(path.read_text(encoding="utf-8"))))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
    return trees


def _defaulted_parameters(trees) -> dict[str, set[str]]:
    """Parameters with a default, for function names that resolve unambiguously.

    Names defined more than once in the package are dropped entirely. Matching
    a call to a definition by name alone conflates every same-named method:
    the first held-out run reported `__init__(..., stdout=)` as "1 caller
    passes, 33 omit" across asyncio, which is 34 unrelated constructors, not a
    disagreement about one function. Dunders are excluded for the same reason
    and because their call sites are mostly implicit.

    Positional-with-default counts as well as keyword-only, because a caller
    can omit either. Only keyword *usage* is detectable at the call site, so
    the caller analysis below sees a positional pass as an omission; that
    inflates the count rather than hiding anything, and lopsidedness ranks
    those down.
    """
    table: dict[str, set[str]] = {}
    definitions: dict[str, int] = {}
    for _path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            definitions[node.name] = definitions.get(node.name, 0) + 1
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            names: set[str] = set()
            positional = node.args.posonlyargs + node.args.args
            with_defaults = positional[len(positional) - len(node.args.defaults):]
            names.update(argument.arg for argument in with_defaults)
            for argument, default in zip(
                node.args.kwonlyargs, node.args.kw_defaults, strict=True
            ):
                if default is not None:
                    names.add(argument.arg)
            if names:
                table.setdefault(node.name, set()).update(names)
    return {
        name: parameters
        for name, parameters in table.items()
        if definitions.get(name) == 1
    }


def _call_sites(trees, root: pathlib.Path):
    calls: dict[str, list[tuple[str, int, set[str]]]] = {}
    for path, tree in trees:
        try:
            label = str(path.relative_to(root if root.is_dir() else root.parent))
        except ValueError:
            label = str(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            calls.setdefault(name, []).append(
                (label, node.lineno, {k.arg for k in node.keywords if k.arg})
            )
    return calls


def find_divergences(root: pathlib.Path, *, min_sites: int = 2) -> list[Divergence]:
    trees = _parsed(root)
    defaults = _defaulted_parameters(trees)
    found: list[Divergence] = []
    for name, sites in sorted(_call_sites(trees, root).items()):
        parameters = defaults.get(name)
        if not parameters or len(sites) < min_sites:
            continue
        for parameter in sorted(parameters):
            passes = tuple(f"{f}:{n}" for f, n, kw in sites if parameter in kw)
            omits = tuple(f"{f}:{n}" for f, n, kw in sites if parameter not in kw)
            if passes and omits:
                found.append(Divergence(name, parameter, passes, omits))
    return sorted(found, key=lambda d: (-d.lopsidedness, -d.total, d.function))


def measure(root: pathlib.Path) -> dict:
    trees = _parsed(root)
    lines = sum(
        len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        for path, _ in trees
    )
    divergences = find_divergences(root)
    return {
        "root": str(root),
        "files": len(trees),
        "lines": lines,
        "divergences": len(divergences),
        "per_kloc": round(len(divergences) / (lines / 1000), 2) if lines else 0.0,
        "lone_dissenters": sum(
            1 for d in divergences
            if min(len(d.passes), len(d.omits)) == 1 and d.total >= 4
        ),
        "top": divergences[:12],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="+", help="package directories to scan")
    parser.add_argument(
        "--show", type=int, default=8, help="how many divergences to print each"
    )
    args = parser.parse_args(argv)

    print("| package | files | lines | divergences | per kLOC | lone dissenters |")
    print("|---|---|---|---|---|---|")
    reports = []
    for raw in args.roots:
        report = measure(pathlib.Path(raw).resolve())
        reports.append(report)
        print(
            f"| `{pathlib.Path(report['root']).name}` | {report['files']} | "
            f"{report['lines']} | {report['divergences']} | "
            f"{report['per_kloc']} | {report['lone_dissenters']} |"
        )

    for report in reports:
        name = pathlib.Path(report["root"]).name
        print(f"\n## {name}: most lopsided divergences\n")
        if not report["top"]:
            print("None found.\n")
            continue
        print("```")
        for divergence in report["top"][: args.show]:
            print(
                f"{divergence.function}(..., {divergence.parameter}=)  "
                f"{len(divergence.passes)} pass / {len(divergence.omits)} omit"
            )
            minority = (
                divergence.omits
                if len(divergence.omits) <= len(divergence.passes)
                else divergence.passes
            )
            side = "omits" if minority is divergence.omits else "passes"
            print(f"    the {side}: {', '.join(minority[:3])}")
        print("```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
