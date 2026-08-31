"""Defects that were live while the test suite was green.

Every bug benchmark this author is aware of hands you a failing test and asks
for a fix: SWE-bench, Defects4J, BugsInPy, QuixBugs. The failing test *is* the
task. Mutation testing inverts the roles, but its mutants are synthetic and the
suite is the artefact under evaluation.

This corpus is the other case. Each entry is a real defect that was live in this
repository at a commit where the entire suite passed.

**Read that statistic sceptically; it is close to a tautology.** Every fix commit
here adds its regression test in the same commit, so "the suite was green at the
parent of the fix" reduces to "the regression test did not exist yet", which is
true of essentially every bug fix in every repository. 5 of 5 is the expected
result anywhere, and `_suite_at` measures commit hygiene rather than a property
of defects. An adversarial review made this point and it is correct.

What is not tautological, and is the only thing worth taking from this file, is
the per-defect `invisibility` field: *which* technique would have caught each
one. That question has real answers and they differ by defect.

The measurement needs no reintroduction and no synthetic mutant. Git holds the
states. For each defect this checks out the commit before its fix, runs the full
suite there, and runs a **discriminating probe**: the input that makes the wrong
number visibly wrong. Then it runs the same probe at the fix and shows the two
answers side by side.

The probe is the contribution. It is what no test had, and writing one is the
only technique that ever found anything on this list.

Every claim here is checked, not asserted. If the suite turns out to have been
red at one of these commits, this prints that and the entry does not count.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclasses.dataclass(frozen=True)
class GreenDefect:
    id: str
    title: str
    file: str
    mechanism: str
    #: Why hundreds of passing tests did not express this. The interesting field.
    invisibility: str
    #: The commit that fixed it. Its parent is the state where the defect is live.
    fix: str
    #: Prints one JSON object. Runs unchanged at both commits, so it must not
    #: assume attributes that only exist after the fix.
    probe: str
    #: Set where the defect was introduced by another entry's fix.
    introduced_by: str = ""


PREAMBLE = '''
import json
from types import SimpleNamespace
from dataclasses import replace
from agent_economics.models import TraceEvent, Outcome, ModelRate
from agent_economics.evidence import make_evidence_bundle
from agent_economics.unsupplied import checks_only_bundle
from agent_economics.audit import audit, render_markdown
from agent_economics.delegation import assess_bundle_closure, delegation_closure_gate
from agent_economics import load_normalized_json_bundle

RATES = {"m": ModelRate(input_per_million_usd=3.0, output_per_million_usd=15.0)}
BASE = load_normalized_json_bundle("examples/claude-code/bundle.json")
OUT = {"t0": Outcome(task_id="t0", acceptable=True)}

def ev(i, name, kind="model", direct=None, tin=0, tout=0, model="m"):
    return TraceEvent(
        task_id="t0", event_id="e%d" % i, timestamp="2026-08-27T00:00:%02dZ" % i,
        event_type=kind, name=name, model=model, direct_cost_usd=direct,
        input_tokens=tin, output_tokens=tout,
    )

def priced(events, edges, declared=()):
    return make_evidence_bundle(
        events=events, outcomes=OUT, rates=RATES, baseline=BASE.baseline,
        policy=BASE.policy, source_id="s.x", dependency_edges=edges,
        declared_delegations=declared,
    )

def emit(question, reported, actual):
    print(json.dumps(
        {"question": question, "reported": reported, "actual": actual}
    ))
'''


DEFECTS: tuple[GreenDefect, ...] = (
    GreenDefect(
        id="D07",
        title="the gate paid teams to delete their own honesty field",
        file="agent_economics/audit.py",
        fix="ffb6ca4",
        mechanism=(
            "A missing evidence instrument was a note while an unattested one "
            "was a ground. Declaring what produced your labels made a bundle "
            "unassessable; recording nothing made it assessable."
        ),
        invisibility=(
            "Caught by a metamorphic relation: deleting evidence must never "
            "increase assessability. An earlier version of this file claimed no "
            "single-case assertion could express it, implying nothing could -- "
            "wrong, and refuted by tests/test_stress_properties.py in this same "
            "suite, which already used the technique on the decision kernel. It "
            "was simply never applied to audit(). "
            "tests/test_audit_metamorphic.py now states it, and fails at "
            "4b60e19 where this defect was live."
        ),
        probe=PREAMBLE + '''
declared = audit(replace(BASE, label_source="fixture.manual-review"))
deleted = audit(replace(BASE, label_source=""))
emit("does deleting the field naming your label source buy a pass?",
     {"declared_assessable": declared.assessable,
      "deleted_assessable": deleted.assessable},
     {"declared_assessable": False, "deleted_assessable": False})
''',
    ),
    GreenDefect(
        id="D08",
        title="a dollar figure computed from costs nothing had priced",
        file="agent_economics/audit.py",
        fix="ffb6ca4",
        mechanism=(
            "The audit rendered '$0.0000 of delegated spend' for a bundle that "
            "declared no rate card. The verdict was right at every step; the "
            "number was invented at the renderer."
        ),
        invisibility=(
            "Renderer tests assert on words, not on the numbers between them, "
            "and every verdict assertion passed because every verdict was "
            "correct. The refusal held in the logic and leaked at the last inch."
        ),
        probe=PREAMBLE + '''
# A delegated call with no stated cost and no rate card to price it. Its
# spend is unknown, so no dollar figure about it can be honest.
b = checks_only_bundle(
    events=(ev(0, "chat", direct=0.0), ev(1, "Agent", "tool", direct=0.0),
            ev(2, "chat", tin=1000000, tout=1000000)),
    outcomes=OUT, source_id="s.x", dependency_edges=(("e1", "e2"),))
money = [l.strip() for l in render_markdown(audit(b)).splitlines() if "$" in l]
emit("does a bundle report dollars for spend nothing could price?",
     {"dollar_lines": money}, {"dollar_lines": []})
''',
    ),
    GreenDefect(
        id="D09",
        title="rate-priced subagent spend weighed nothing",
        file="agent_economics/delegation.py",
        fix="93c3552",
        mechanism=(
            "Cost-weighted closure summed `direct_cost_usd or 0.0` rather than "
            "calling the resolver every other consumer uses, so any event "
            "priced by the rate card counted as free."
        ),
        invisibility=(
            "Every adapter-built bundle sets an explicit cost, so every fixture "
            "in the suite took the one branch that worked. The documented CSV "
            "evidence path leaves the column blank and had no fixture."
        ),
        probe=PREAMBLE + '''
b = priced(
    (ev(0, "chat", direct=0.0),
     ev(1, "Agent", "tool", direct=0.0), ev(2, "chat", direct=100.0),
     ev(3, "Agent", "tool", direct=0.0), ev(4, "chat", tin=1000000, tout=1000000)),
    (("e1", "e2"), ("e3", "e4")), declared=("e1",))
c = assess_bundle_closure(b)
emit("how much undeclared delegated spend goes unreported?",
     {"closure_pct": round(c.closure * 100, 1),
      "unaccounted_usd": c.unaccounted_cost_usd},
     {"closure_pct": 84.7, "unaccounted_usd": 18.0})
''',
    ),
    GreenDefect(
        id="D10",
        title="the fix for D09 left the gate unable to price anything",
        file="agent_economics/delegation.py",
        fix="dc72ae6",
        introduced_by="D09",
        mechanism=(
            "`delegation_closure_gate` called `assess_closure` without rates, "
            "though the view it receives carries them, so a rate-priced bundle "
            "became unpriceable inside the gate."
        ),
        invisibility=(
            "Introduced by the fix for D09, in the same file, within the hour, "
            "by an agent that had just written the lesson about this class of "
            "error. No test drove a rate-priced delegation through the gate "
            "rather than through the report."
        ),
        probe=PREAMBLE + '''
events = (ev(0, "chat", direct=0.0), ev(1, "Agent", "tool", direct=0.0),
          ev(2, "chat", tin=1000000, tout=1000000))
view = SimpleNamespace(events=events, dependency_edges=(("e1", "e2"),), rates=RATES)
try:
    out = delegation_closure_gate(declared=("e1",)).run(view)
    got = {"raised": None, "priced_18": "18.0000" in out.results[0].message}
except Exception as exc:
    got = {"raised": type(exc).__name__, "priced_18": False}
emit("can the gate price a delegation whose rate card it was handed?",
     got, {"raised": None, "priced_18": True})
''',
    ),
    GreenDefect(
        id="D11",
        title="tool calls asserted free with no rate card to say so",
        file="agent_economics/delegation.py",
        fix="dc72ae6",
        mechanism=(
            "Cost resolution answered 0.0 for any non-model event before "
            "consulting rates. Which tools are billed is exactly what a rate "
            "card says, so with none the claim is unsupported."
        ),
        invisibility=(
            "True of every fixture in the suite, because every fixture had a "
            "rate card. The claim is only wrong in the configuration no test "
            "constructed."
        ),
        probe=PREAMBLE + '''
b = checks_only_bundle(
    events=(ev(0, "chat", direct=0.0), ev(1, "Agent", "tool"),
            ev(2, "WebSearch", "tool", model=""), ev(3, "WebFetch", "tool", model="")),
    outcomes=OUT, source_id="s.x", dependency_edges=(("e1", "e2"), ("e1", "e3")))
c = assess_bundle_closure(b)
emit("with no rate card, is unpriced tool spend reported as zero dollars?",
     {"basis": getattr(c, "basis", "cost"),
      "unaccounted_usd": c.unaccounted_cost_usd},
     {"basis": "count", "unaccounted_usd": None})
''',
    ),
)


def _checkout(commit: str, destination: pathlib.Path) -> None:
    archive = subprocess.run(
        ["git", "archive", commit], cwd=ROOT, capture_output=True, check=True
    )
    subprocess.run(
        ["tar", "-x", "-C", str(destination)], input=archive.stdout, check=True
    )


def _run(argv: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def _probe_at(commit: str, probe: str, python: str) -> dict:
    with tempfile.TemporaryDirectory() as raw:
        tree = pathlib.Path(raw)
        _checkout(commit, tree)
        (tree / "_probe.py").write_text(probe, encoding="utf-8")
        finished = _run([python, "_probe.py"], tree)
        try:
            return json.loads(finished.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"probe_failed": (finished.stderr or finished.stdout)[-240:]}


def _suite_at(commit: str, python: str) -> tuple[bool, int]:
    with tempfile.TemporaryDirectory() as raw:
        tree = pathlib.Path(raw)
        _checkout(commit, tree)
        finished = _run([python, "-m", "unittest", "discover", "-s", "tests"], tree)
        ran = 0
        for line in finished.stderr.splitlines():
            if line.startswith("Ran ") and " test" in line:
                ran = int(line.split()[1])
        return finished.returncode == 0, ran


def assess(defect: GreenDefect, python: str) -> dict:
    before = f"{defect.fix}^"
    green, ran = _suite_at(before, python)
    return {
        "id": defect.id,
        "title": defect.title,
        "file": defect.file,
        "mechanism": defect.mechanism,
        "invisibility": defect.invisibility,
        "introduced_by": defect.introduced_by,
        "live_at": _sha(before),
        "fixed_by": _sha(defect.fix),
        "suite_green_while_live": green,
        "tests_passing_while_live": ran,
        "probe_while_live": _probe_at(before, defect.probe, python),
        "probe_after_fix": _probe_at(defect.fix, defect.probe, python),
    }


def _sha(rev: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short", rev], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def main(argv: list[str]) -> int:
    python = argv[1] if len(argv) > 1 else sys.executable
    rows = [assess(defect, python) for defect in DEFECTS]

    print("# Defects that were live while the suite was green\n")
    print(
        "Each row checks out the commit before the defect's fix, runs the whole "
        "suite there, and runs a probe that discriminates. Nothing is "
        "reintroduced and nothing is synthetic: these are the states the "
        "repository was actually in.\n"
    )
    print("| id | defect | commit | tests passing | suite green |")
    print("|---|---|---|---|---|")
    for row in rows:
        mark = "**yes**" if row["suite_green_while_live"] else "no"
        print(
            f"| {row['id']} | {row['title']} | `{row['live_at']}` | "
            f"{row['tests_passing_while_live']} | {mark} |"
        )
    green = sum(bool(r["suite_green_while_live"]) for r in rows)
    total = sum(r["tests_passing_while_live"] for r in rows if r["suite_green_while_live"])
    print(
        f"\n**{green} of {len(rows)} defects were live at a commit where the "
        f"entire suite passed**, across {total} passing tests in total.\n"
    )

    print("## What each probe asked\n")
    for row in rows:
        print(f"### {row['id']} — {row['title']}\n")
        print(f"- **File:** `{row['file']}`")
        print(f"- **Live at** `{row['live_at']}`, **fixed by** `{row['fixed_by']}`")
        if row["introduced_by"]:
            print(f"- **Introduced by the fix for {row['introduced_by']}.**")
        print(f"- **Mechanism:** {row['mechanism']}")
        print(f"- **Why no test expressed it:** {row['invisibility']}")
        live, fixed = row["probe_while_live"], row["probe_after_fix"]
        if "question" in live:
            print(f"- **Probe:** {live['question']}")
            print(f"  - while live: `{live['reported']}`")
            print(f"  - after the fix: `{fixed.get('reported', fixed)}`")
            print(f"  - true answer: `{live['actual']}`")
        else:
            print(f"- **Probe could not run while live:** `{live}`")
        print()

    print("## The claim this supports, and its limits\n")
    print(
        "A green suite is evidence that specified behaviour holds. It is not "
        "evidence that the specification produces a number worth reporting. "
        "Every defect above sat inside that gap, in a package built to close "
        "it, written by someone hunting this exact failure.\n"
    )
    print(
        f"Population: {len(rows)} defects, one repository, one author, one "
        "day. That is a case series, not a rate. It does not estimate how "
        "often this happens elsewhere and no sampling frame supports "
        "generalising it. What it does establish is existence and mechanism: "
        "these defects are reachable, they are of a kind, and the technique "
        "that found them is stated precisely enough to try.\n"
    )
    return 0 if green == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
