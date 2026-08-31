"""Where green defects should live, derived from the five that did.

The corpus in `green_defects.py` is retrospective. It cannot tell you whether
the technique works, because the technique is not what found those five: luck
and suspicion did. A case series assembled after the fact has no hit rate.

So this states the method first and looks second. Each of the five known
defects is an instance of a shape, and every shape here is mechanically
greppable. This module enumerates every site in the package matching those
shapes. The list it produces is the pre-registration: it is committed before
any probe is written, so the misses get counted too.

A site is not a defect. Most of these will be correct code. That is the point:
a search that only reports its hits is the thing this repository exists to
refuse.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "agent_economics"


@dataclasses.dataclass(frozen=True)
class Shape:
    """One recurring form, abstracted from a defect that actually happened."""

    id: str
    name: str
    learned_from: str
    why: str


SHAPES: tuple[Shape, ...] = (
    Shape(
        id="S1",
        name="numeric default absorbing an absence",
        learned_from="D09",
        why=(
            "`x or 0.0` and `d.get(k, 0)` cannot distinguish 'zero' from 'not "
            "established'. Where the result is summed or divided, an unknown "
            "becomes a confident zero and the total understates."
        ),
    ),
    Shape(
        id="S2",
        name="formatted number with no check that it is known",
        learned_from="D08",
        why=(
            "A format spec renders whatever it is handed. If the value can be "
            "absent, unestablished, or a placeholder, the renderer converts it "
            "into a figure with decimal places, which reads as a measurement."
        ),
    ),
    Shape(
        id="S3",
        name="ratio whose denominator can be empty",
        learned_from="the vacuous closure line",
        why=(
            "A ratio over nothing is 1.0 or a guarded constant. Printed as a "
            "percentage it reads as full marks for work that never happened."
        ),
    ),
    Shape(
        id="S4",
        name="early return that answers before consulting its qualifier",
        learned_from="D11",
        why=(
            "A branch that returns a value before reading the parameter that "
            "would qualify it is right in the configuration the tests build "
            "and unsupported in the one they do not."
        ),
    ),
    Shape(
        id="S5",
        name="caller omitting an optional parameter it could supply",
        learned_from="D10",
        why=(
            "A helper takes an optional input and a caller with that input in "
            "hand does not pass it. The helper then degrades, correctly, to a "
            "weaker answer nobody asked for."
        ),
    ),
)

NUMERIC_DEFAULT = re.compile(r"\bor\s+(0\.0|0|1\.0|1)\b")
FORMAT_NUMBER = re.compile(r"\{[^{}]*:[<>^]?[+ ]?[0-9,]*\.[0-9]+[fe%]\}")
GET_WITH_ZERO = re.compile(r"\.get\([^)]+,\s*(0|0\.0)\s*\)")


@dataclasses.dataclass(frozen=True)
class Site:
    shape: str
    file: str
    line: int
    excerpt: str

    def __str__(self) -> str:
        return f"{self.shape}  {self.file}:{self.line}  {self.excerpt}"


def _sources() -> list[tuple[pathlib.Path, str]]:
    return [
        (path, path.read_text(encoding="utf-8"))
        for path in sorted(PACKAGE.rglob("*.py"))
        if "__pycache__" not in str(path)
    ]


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT))


def find_sites() -> list[Site]:
    """Every site matching a known shape. Mechanical, not curated."""
    sites: list[Site] = []
    for path, source in _sources():
        lines = source.splitlines()
        for number, text in enumerate(lines, start=1):
            stripped = text.strip()
            if stripped.startswith("#"):
                continue
            if NUMERIC_DEFAULT.search(text) or GET_WITH_ZERO.search(text):
                sites.append(Site("S1", _rel(path), number, stripped[:88]))
            if FORMAT_NUMBER.search(text):
                sites.append(Site("S2", _rel(path), number, stripped[:88]))
        sites.extend(_ratio_sites(path, source))
        sites.extend(_early_return_sites(path, source))
        sites.extend(_omitted_argument_sites(path, source))
    return sites


def _ratio_sites(path: pathlib.Path, source: str) -> list[Site]:
    """Divisions guarded by a zero/empty check, which is where the vacuous 1.0 hides."""
    found: list[Site] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            found.append(
                Site("S3", _rel(path), node.lineno, lines[node.lineno - 1].strip()[:88])
            )
    return found


def _early_return_sites(path: pathlib.Path, source: str) -> list[Site]:
    """Constant numeric returns inside a function that also takes a qualifier."""
    found: list[Site] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    lines = source.splitlines()
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        parameters = {a.arg for a in function.args.args + function.args.kwonlyargs}
        if not parameters:
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Return)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, (int, float))
                and not isinstance(node.value.value, bool)
            ):
                found.append(
                    Site(
                        "S4", _rel(path), node.lineno,
                        f"in {function.name}(): {lines[node.lineno - 1].strip()[:70]}",
                    )
                )
    return found


def _omitted_argument_sites(path: pathlib.Path, source: str) -> list[Site]:
    """Calls to package functions that omit an optional keyword the caller may hold.

    D10 exactly: `assess_closure` grew a `rates` parameter and one caller did
    not pass it, while holding rates on the object it already had.
    """
    found: list[Site] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    optional_keywords = _optional_keywords()
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        expected = optional_keywords.get(node.func.id)
        if not expected:
            continue
        supplied = {k.arg for k in node.keywords if k.arg}
        missing = sorted(expected - supplied)
        if missing:
            found.append(
                Site(
                    "S5", _rel(path), node.lineno,
                    f"{node.func.id}(...) omits {', '.join(missing)}"
                    f"  [{lines[node.lineno - 1].strip()[:40]}]",
                )
            )
    return found


def _optional_keywords() -> dict[str, set[str]]:
    """Keyword-only parameters with defaults, per package function."""
    table: dict[str, set[str]] = {}
    for _path, source in _sources():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef):
                continue
            names = {
                argument.arg
                for argument, default in zip(
                    function.args.kwonlyargs,
                    function.args.kw_defaults,
                    strict=True,
                )
                if default is not None
            }
            if names:
                table.setdefault(function.name, set()).update(names)
    return table


@dataclasses.dataclass(frozen=True)
class Divergence:
    """The same quantity computed two ways, which is what the five defects were.

    D09 read `direct_cost_usd or 0.0` where a resolver `TraceEvent.cost` existed.
    D10 called `assess_closure` without `rates` where another caller passed it.
    D11 answered before consulting the parameter that qualifies the answer.

    None of those is "a suspicious line". Each is *two* places disagreeing about
    how to compute one thing, which is why reading either alone looks fine and
    why a test exercising either alone passes.
    """

    kind: str
    quantity: str
    consistent: tuple[str, ...]
    divergent: tuple[str, ...]


def _call_sites() -> dict[str, list[tuple[str, int, set[str]]]]:
    calls: dict[str, list[tuple[str, int, set[str]]]] = {}
    for path, source in _sources():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.setdefault(node.func.id, []).append(
                    (_rel(path), node.lineno, {k.arg for k in node.keywords if k.arg})
                )
    return calls


def inconsistent_callers() -> list[Divergence]:
    """Optional arguments that some callers pass and others omit.

    An optional parameter every caller omits is dead. One every caller passes is
    not optional. The interesting case is disagreement, because it means the
    argument carries something at least one author thought was necessary.
    """
    found: list[Divergence] = []
    optional = _optional_keywords()
    for name, sites in sorted(_call_sites().items()):
        expected = optional.get(name)
        if not expected or len(sites) < 2:
            continue
        for keyword in sorted(expected):
            passes = [f"{f}:{n}" for f, n, kw in sites if keyword in kw]
            omits = [f"{f}:{n}" for f, n, kw in sites if keyword not in kw]
            if passes and omits:
                found.append(
                    Divergence("inconsistent-caller", f"{name}(..., {keyword}=)",
                               tuple(passes), tuple(omits))
                )
    return found


def raw_field_versus_resolver() -> list[Divergence]:
    """Fields read directly where a resolver method for the same value exists.

    D09 in one query. `direct_cost_usd` has a resolver named `cost`; reading the
    field raw skips whatever the resolver knows, which was the whole defect.
    """
    resolvers = {"direct_cost_usd": "cost"}
    found: list[Divergence] = []
    for field, method in resolvers.items():
        raw, resolved = [], []
        for path, source in _sources():
            for number, text in enumerate(source.splitlines(), start=1):
                if text.strip().startswith("#"):
                    continue
                if f".{field}" in text:
                    raw.append(f"{_rel(path)}:{number}")
                if re.search(rf"\.{method}\(", text):
                    resolved.append(f"{_rel(path)}:{number}")
        if raw and resolved:
            found.append(
                Divergence("raw-field-vs-resolver", f"{field} / .{method}()",
                           tuple(resolved), tuple(raw))
            )
    return found


def main() -> int:
    sites = find_sites()
    by_shape: dict[str, list[Site]] = {}
    for site in sites:
        by_shape.setdefault(site.shape, []).append(site)

    print("# Pre-registered probe sites\n")
    print(
        "Derived mechanically from the shapes of five defects that were live "
        "while the suite was green. Committed before any probe is written, so "
        "that the misses are counted with the hits.\n"
    )
    print("## The shapes, and the defect each was abstracted from\n")
    for shape in SHAPES:
        hits = len(by_shape.get(shape.id, ()))
        print(f"### {shape.id} — {shape.name}  ({hits} sites)\n")
        print(f"- **Learned from:** {shape.learned_from}")
        print(f"- **Why it hides:** {shape.why}\n")

    print(f"## The {len(sites)} sites\n")
    for shape in SHAPES:
        found = by_shape.get(shape.id, [])
        if not found:
            continue
        print(f"### {shape.id} ({len(found)})\n")
        print("```")
        for site in found:
            print(f"{site.file}:{site.line}  {site.excerpt}")
        print("```\n")

    print("## Why the coarse shapes are not the method\n")
    print(
        f"{len(sites)} sites in a package this size is a detector with no "
        "specificity. Probing them one at a time would be a worse use of "
        "attention than reading the code. Reported here rather than quietly "
        "dropped, because a search that only shows its narrowed form is "
        "hiding how it was narrowed.\n"
    )

    divergences = inconsistent_callers() + raw_field_versus_resolver()
    print("## The narrowing that has support\n")
    print(
        "All five known defects share a sharper form than any shape above: the "
        "same quantity computed two ways, with one way wrong. That is why each "
        "read fine in isolation and why a test exercising either path alone "
        "passed. Divergence is enumerable, and there are far fewer of them.\n"
    )
    print(f"**{len(divergences)} divergences**, against {len(sites)} coarse sites.\n")
    for divergence in divergences:
        print(f"### `{divergence.quantity}`  ({divergence.kind})\n")
        print(f"- passes / resolves ({len(divergence.consistent)}): "
              f"`{'`, `'.join(divergence.consistent[:6])}`")
        print(f"- omits / reads raw ({len(divergence.divergent)}): "
              f"`{'`, `'.join(divergence.divergent[:6])}`\n")

    print("## What this list is not\n")
    print(
        "A divergence is not a defect. Two callers may differ for good reason, "
        "and a raw read may be correct where no resolution is wanted. This is "
        "a pre-registration: the next step is a probe per divergence and an "
        "honest count of how many found nothing.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
