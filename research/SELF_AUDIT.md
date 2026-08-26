# Our CI was green. Three of its checks could not fail.

This repository argues one thing: **a missing check is not a passing check.** If a
gate that a decision depends on is absent, disabled, or unsatisfied, the only
honest verdict is `INCOMPLETE`, never a pass.

We ran that argument against the repository that makes it. Three review agents,
one pass, roughly forty minutes. They found three places where this repository
did the exact thing it tells other people not to do.

All three had been green in CI the whole time.

## What we pointed at it

Three agents, non-overlapping scopes, run concurrently:

| Agent | Question |
|---|---|
| `contract-invariant-guard` | Can any change let a missing gate produce a verdict other than `INCOMPLETE`? |
| `repro-drift-check` | Does the full pipeline still reproduce its committed artifacts byte-for-byte? |
| `claims-auditor` | Is every number published in the README asserted by a test and executed by a make target? |

The invariant review came back clean, and it earned that verdict: rather than
reading diff hunks, it parsed every changed module before and after, stripped the
import nodes, and compared the ASTs. Eleven engine files were AST-identical modulo
imports. The decision-contract digest and all four example evidence digests were
unchanged. The gate-removal kill rate held at 588/588.

The other two found the following.

## Finding 1: the loop that swallowed failures

`make reproduce` runs five executable lessons. The recipe was:

```make
lessons:
	@for lesson in lessons/*.py; do PYTHONPATH=. $(PYTHON) "$$lesson"; done
```

A shell `for` loop exits with the status of its **last** iteration. A failing
lesson `00` through `03` was discarded as long as `04` succeeded. `make reproduce`
returned 0 with a broken lesson in the chain.

Nothing in `tests/` referenced `lessons/`, so `make reproduce` was the only thing
exercising them, and it under-reported.

The fix is one word:

```make
	@set -e; for lesson in lessons/*.py; do PYTHONPATH=. $(PYTHON) "$$lesson"; done
```

Verified by breaking lesson `00` in place and confirming the target now fails, then
restoring and confirming it passes. All five lessons pass today, so this was
latent, never active. That is exactly the condition the repository says you cannot
rely on.

## Finding 2: the gate that always returned zero

`mutation_score.py` injects 588 gate-removal mutations and reports how many the
engine still refuses. It had just been wired into `make reproduce`, which made it
look like a gate.

Its `main()` ended:

```python
    return 0
```

Unconditionally. A degraded kill rate printed `✗ GAPS FOUND` in large friendly
letters and exited 0. A display step wearing the shape of a gate.

```python
    return 0 if fixed_score == 1.0 else 1
```

The exposure was narrow, because `make reproduce` runs the test suite first and
`test_research_scripts.py` asserts the 588 figure directly. But anyone running
`make mutation` on its own, which is what the README invites you to do, got a
green exit code on a broken harness.

## Finding 3: the claim the tests did not check

This is the worst one, because we introduced it in the commit that was supposed to
fix exactly this class of problem.

That commit added tests locking the repository's published numbers, wired three
previously-unrun scripts into CI, and added this line to the README:

> Every number this README publishes is asserted by the test suite, so a change
> that moves one fails CI.

It was not true. The frontier comparison table — three upper bounds, three cost
lower bounds, the harmful-regression counts, the 180 paired-task count — was
asserted by **nothing** in `tests/`. Its only guard was a byte-comparison inside
`make frontier`.

That comparison does run in CI, so "fails CI" survived. "Asserted by the test
suite" did not. `python -m unittest discover -s tests` passed with those published
numbers arbitrarily wrong.

Two smaller versions of the same thing, from the same audit:

- The OpenTelemetry semantic-conventions pin published in the README was
  "asserted" by a test comparing the rendered template to the same constant the
  README quotes. The assertion could not fail when the constant changed.
- A published cost ratio had its numerator asserted and its denominator living
  only inside a byte-compared artifact.

The fix was to make the claim true rather than soften it:
`tests/test_published_frontier_figures.py` now asserts the table, the semconv pin
is asserted as a literal, and both sides of the ratio are checked. The README
sentence was also rewritten to name both guard mechanisms precisely instead of
claiming one that did not exist.

## All three are the same bug

Different mechanisms. Identical failure:

> **A check that cannot fail reads as a check that passed.**

A loop that discards non-final exit codes. A function that returns a constant. A
sentence asserting coverage that was never written. In each case the signal was
structurally incapable of going red, and a green result was interpreted as
evidence.

This is not an exotic failure. It is the ordinary shape of eval and CI rot, and it
is invisible precisely because everything looks fine. The reason it is worth
writing down is that a repository built specifically to detect it still shipped
three instances of it.

We also found something adjacent and worth naming: three README blocks presented
stylized ASCII summaries as program output. The numbers were correct, but a reader
running `python3 false_green.py` got a different-looking Markdown report. For a
project whose entire pitch is "run this one file," that gap is a credibility
problem independent of whether the numbers are right. They are now verbatim output.

## How to check your own

None of this required special tooling. Four questions, each answerable in minutes:

1. **Can each CI step actually fail?** Force one to fail and confirm the build goes
   red. Shell loops, `|| true`, and functions returning a constant are the usual
   culprits.
2. **Is every published number asserted somewhere a test runner will catch?**
   Change one to a wrong value and run only your test suite, not the full pipeline.
3. **Are your assertions tautological?** An assertion comparing a value to the same
   constant your docs quote cannot fail when the constant changes.
4. **Does your documented output match the real output?** Run the command in your
   README and diff it against what you published.

Question 2 is the one that caught us. It is also the one nobody runs, because the
full pipeline is green and that feels like the same thing.

## Limits

This is a self-audit, not an independent one. We wrote both the method and the
target. The three findings are real and reproducible from the commit history, but
their severity was low: all five lessons passed, the kill rate was intact, and
every published number happened to be correct. Nothing here caught a wrong result.
It caught three ways a wrong result would not have been noticed.

The repository's headline experiment runs on a synthetic 98-scenario fixture. It
measures a property of a specific eval design, not a production prevalence rate.
That distinction is stated throughout the repository and it applies to this
document too.

## Reproduce it

```bash
make reproduce PYTHON=python3.12
```

Commits: [`77a563b`](../../../commit/77a563b) fixes the lessons loop,
[`73a3f50`](../../../commit/73a3f50) fixes the exit code and the claim gaps. The
three agents are checked in under `.claude/agents/` and run against any diff.
