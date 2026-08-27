"""
Generate research/SELF_AUDIT.md from the repository.

The document went through five hand-editing rounds before this existed, and the
defects that recurred were almost entirely derived numbers written into prose:
test counts, elapsed times, an AST-identical file count, a correction-round
count. Every one of them is computable from git or from a live run. A hand-typed
copy of a computed value is an unguarded claim, which is the exact failure the
document is about.

So the prose lives in SELF_AUDIT.template.md and every derived number is
substituted here. The generated file is committed, and `--verify` byte-compares
it, matching how false_green.py guards SUMMARY.md and how the frontier guards
frontier.md. A number that moves now fails CI instead of drifting.

Generation and verification are deliberately separate. Deriving the facts needs
git history and specific commit SHAs; verifying must not, because CI checks out
shallow and because a rebase changes every SHA. So the derived facts are frozen
into a committed JSON artifact, exactly as the frontier and false-green results
are, and rendering reads that file. Only `--facts` touches git.

This was learned the hard way: the first version called `git diff` during
`make reproduce`, which passed locally and failed on every CI runner for five
commits before anyone looked.

Run:
    python3 research/self_audit.py --facts         # re-derive from git history
    python3 research/self_audit.py                 # render from the frozen facts
    python3 research/self_audit.py --verify PATH   # byte-compare, exit 1 on drift
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("SELF_AUDIT.template.md")
OUTPUT = Path(__file__).with_name("SELF_AUDIT.md")

# The commits this document reasons about. Named here so the prose never has to
# spell a SHA it might get wrong.
BASE = "520487e"          # branch point
FIRST = "73fd32e"         # repository's first commit
DORMANT = "4b0d55e"       # mutation_score.py lands on main, wired to nothing
INTRODUCED = "6eb88f2"    # promotes it to a gate; adds the README overclaim
FIX_LESSONS = "77a563b"   # fixes finding 1
FIX_CLAIMS = "73a3f50"    # fixes findings 2 and 3
STALE_FROM = "4164192"    # writes a test count that was correct at the time
STALE_BY = "d3afc7e"      # adds tests, silently falsifying it


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _epoch(rev: str) -> int:
    return int(_git("show", "-s", "--format=%ct", rev))


def _minutes(a: str, b: str) -> int:
    return round((_epoch(b) - _epoch(a)) / 60)


def _days(a: str, b: str) -> int:
    return (_epoch(b) - _epoch(a)) // 86400


def _spell(n: int) -> str:
    words = {
        1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
        7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
        12: "twelve", 15: "fifteen", 16: "sixteen",
    }
    return words.get(n, str(n))


def _test_count(rev: str | None = None) -> int:
    """Collected test count, at HEAD or in a throwaway worktree at `rev`."""
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    if rev is None:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stderr
    else:
        work = Path(subprocess.check_output(["mktemp", "-d"], text=True).strip())
        try:
            _git("worktree", "add", "-q", "--detach", str(work), rev)
            out = subprocess.run(cmd, cwd=work, capture_output=True, text=True).stderr
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(work)],
                           cwd=ROOT, capture_output=True)
    match = re.search(r"^Ran (\d+) tests", out, re.MULTILINE)
    if not match:
        raise RuntimeError(f"could not read a test count for {rev or 'HEAD'}")
    return int(match.group(1))


def _ast_identical(base: str, head: str) -> tuple[int, int]:
    """Engine files whose AST is unchanged once imports are stripped."""
    changed = [
        p for p in _git("diff", "--name-only", base, head).splitlines()
        if p.startswith("agent_economics/") and p.endswith(".py")
    ]

    def shape(rev: str, path: str) -> str | None:
        try:
            tree = ast.parse(_git("show", f"{rev}:{path}"))
        except (subprocess.CalledProcessError, SyntaxError):
            return None
        tree.body = [
            n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        return ast.dump(tree)

    same = sum(
        1 for p in changed
        if (a := shape(base, p)) is not None and a == shape(head, p)
    )
    return same, len(changed)


def _carrying_commits(introduced: str, fixed: str) -> int:
    """
    Commits that contain the defect: the one introducing it, through the last
    before the fix. How many of those got their own green CI run is not
    recoverable from git, so this counts commits and the prose says so.
    """
    carrying = {c for c in _git("rev-list", f"{introduced}..{fixed}^").splitlines() if c}
    carrying.add(_git("rev-parse", introduced))
    return len(carrying)


def facts() -> dict[str, str]:
    ast_same, ast_total = _ast_identical(BASE, FIX_LESSONS)
    return {
        "tests_at_fix_lessons": str(_test_count(FIX_LESSONS)),
        "tests_at_stale_from": str(_test_count(STALE_FROM)),
        "ast_identical": _spell(ast_same).capitalize(),
        "ast_total": _spell(ast_total),
        "ast_differing": _spell(ast_total - ast_same),
        "fix_minutes": _spell(_minutes(INTRODUCED, FIX_CLAIMS)),
        "stale_minutes": _spell(_minutes(STALE_FROM, STALE_BY)),
        "dormant_days": str(_days(DORMANT, INTRODUCED)),
        "carrying_commits": _spell(_carrying_commits(INTRODUCED, FIX_CLAIMS)),
        "first_commit": FIRST,
        "fix_lessons": FIX_LESSONS,
        "stale_from": STALE_FROM,
        "stale_by": STALE_BY,
    }


FACTS = Path(__file__).with_name("self_audit_facts.json")


def frozen_facts() -> dict[str, str]:
    """The derived facts, as committed. Reading these never touches git."""
    if not FACTS.exists():
        raise RuntimeError(
            f"{FACTS.name} is missing. Re-derive it with: make self-audit-facts"
        )
    return json.loads(FACTS.read_text(encoding="utf-8"))


def render() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    values = frozen_facts()
    missing = {m for m in re.findall(r"\{\{(\w+)\}\}", text)} - set(values)
    if missing:
        raise RuntimeError(f"template references unknown facts: {sorted(missing)}")
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path, help="byte-compare instead of writing")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument(
        "--facts",
        action="store_true",
        help="re-derive the facts from git history and freeze them to JSON",
    )
    args = parser.parse_args(argv)

    if args.facts:
        FACTS.write_text(
            json.dumps(facts(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {FACTS}")
        return 0

    text = render()
    if args.verify:
        if not args.verify.exists() or args.verify.read_text(encoding="utf-8") != text:
            print(f"Generated self-audit differs from {args.verify}")
            print("Regenerate with: make self-audit")
            return 1
        print(f"Self-audit matches {args.verify}")
        return 0
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
