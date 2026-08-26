# Our CI was green. Three of its checks could not fail.

This repository argues one thing: **a missing check is not a passing check.** If a
gate that a decision depends on is absent, disabled, or unsatisfied, the only
honest verdict is `INCOMPLETE`, never a pass.

We ran that argument against the repository that makes it: three review agents,
one pass, run concurrently. They found three places where this repository did the
exact thing it tells other people not to do. From the first commit of the reviewed
change set to the last fix was ten minutes, which is checkable from the commit
timestamps; the agents began before that commit and no start time is recoverable
from the repository.

Then we ran the same auditor against this page, three more times, and it found a
fourth. That one is in the document you are reading, and it is the finding that
generalizes furthest.

All three passed CI. One had been in the repository since its first commit. The
other two became checks in a commit we wrote minutes earlier, the one meant to fix
this exact class of problem; one of those two was dormant code that had sat on
`main` for weeks until that commit made it load-bearing. That is disclosed in full
below, because it changes what the findings are evidence of.

## What we pointed at it

Three agents, non-overlapping scopes, run concurrently:

| Agent | Question |
|---|---|
| `contract-invariant-guard` | Can any change let a missing gate produce a verdict other than `INCOMPLETE`? |
| `repro-drift-check` | Does the full pipeline still reproduce its committed artifacts byte-for-byte? |
| `claims-auditor` | Is every number published in the README asserted by a test and executed by a make target? |

The invariant review came back clean, and it earned that verdict: rather than
reading diff hunks, it parsed every changed module before and after, stripped the
import nodes, and compared the ASTs. Eleven of the sixteen changed engine files were
AST-identical modulo imports; the other five were read individually and are benign.
The decision-contract digest and all four example evidence digests were unchanged.
The gate-removal kill rate held at 588/588.

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

The fix is two tokens:

```make
	@set -e; for lesson in lessons/*.py; do PYTHONPATH=. $(PYTHON) "$$lesson"; done
```

Since first publishing this, `tests/test_lessons.py` also asserts the lesson count
and runs all five from the test suite, so the target no longer has to be written
correctly for a broken lesson to be caught.

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

It was not true, though the gap was narrower than we first wrote. `test_frontier.py`
already asserted part of the published table from a live run: the 171 reference-
acceptable count, two of the three conditional harmful-regression rates, the
eligibility of `balanced-4-step` and `cheap-2-step` (two of the three cells in the
Result column), the `ADOPT` decision, and the selected arm.

What no test asserted: **the three absolute upper bounds (3.7% / 12.5% / 2.6%),
the three cost lower bounds (32.0% / 29.9% / -38.9%), `premium-12-step`'s
zero-count and its ineligibility, and the 180 paired-task figure.** Those were
guarded only by a byte-comparison inside `make frontier`.

We verified the gap rather than asserting it: scaling `premium-12-step` costs by
1.4 moved the published cost lower bound from -38.9% to **-93.2%**, and the full
test suite still reported 202 tests, OK.

That comparison does run in CI, so "fails CI" survived. "Asserted by the test
suite" did not. `python -m unittest discover -s tests` passed with those published
numbers arbitrarily wrong.

Two smaller versions of the same thing, from the same audit:

- The OpenTelemetry semantic-conventions pin published in the README was
  "asserted" by a test comparing the rendered template to the same constant the
  README quotes. The assertion could not fail when the constant changed.
- A published cost ratio had its numerator asserted and its denominator living
  only inside a byte-compared artifact.

The semconv pin is now asserted as a literal and both sides of the ratio are
checked. `tests/test_published_frontier_figures.py` locks the frontier table.

**But that fix is partial, and the partialness matters.** The new test reads the
committed artifact `research/results/frontier/frontier.json`. It catches an edit
to that file. It does not catch drift originating upstream of it. Applying the
same cost perturbation at current HEAD and running the repository's own question 2
below — change a number, run only the test suite — leaves the full suite green,
while `make frontier` correctly exits 2.

This sentence used to publish the exact test count. It broke three times in a row
as later commits added tests, so the count is gone rather than corrected a fourth
time. That decision is Finding 4 in miniature.

So the honest status is: the frontier table is guarded by a literal test against
the published artifact, plus a byte-comparison that catches upstream drift. Both
run in CI. The test suite alone does not catch it. We rewrote the README sentence
to say that, rather than to claim a guarantee we had not built.

## The first three are the same bug

Different mechanisms. Identical failure:

> **A check that cannot fail reads as a check that passed.**

A loop that discards non-final exit codes. A function that returns a constant. A
sentence asserting coverage that was never written. In each case the signal was
structurally incapable of going red, and a green result was interpreted as
evidence.

This is not an exotic failure. It is the ordinary shape of eval and CI rot, and it
is invisible precisely because everything looks fine. The reason it is worth
writing down is that a repository built specifically to detect it still contained
three instances of it, one of them on `main` since its first commit.

There is a fourth finding, and we only have it because we audited this page before
publishing it. It is in the next section.

We also found something adjacent and worth naming: four README blocks presented
hand-cut ASCII summaries directly beneath the command that supposedly produced
them. The numbers were correct, but a reader running `python3 false_green.py` got
a differently-shaped Markdown report. For a project whose pitch is "run this one
file," that gap is a credibility problem independent of whether the numbers are
right.

One block is now verbatim output, marked as truncated. The other three are still
summaries, and are now labelled as summaries rather than presented as output. We
flag this because the first version of this document claimed all of them had been
converted, which was false, and it was caught by the same audit that produced the
rest of this page.

## Finding 4: this document

Before publishing, we ran the same auditor against this page. It came back
do-not-publish three times.

**Round 1** found four statements that did not hold. The worst was the paragraph
claiming we had converted the stylized README blocks to real output: one of four
was converted. That was the one paragraph saying "we fixed the credibility
problem," and it was disprovable in thirty seconds by running the README's own
commands. The round also caught that the sentence we had written to replace the
overclaim was itself an overclaim of the same shape.

**Round 2** found seven more. Two of them were introduced by round 1's fixes. One
was a new line in the README describing a "per-scenario table" in the false-green
output. No such table exists; the report ends with a per-gate bar chart. We wrote a
false statement about program output in the commit whose purpose was to stop making
false statements about program output. Round 2 also found "five executable lessons"
in the README, guarded by nothing: a live counterexample to the meta-claim two
paragraphs below it.

**Round 3** found four blocking items. Two were introduced by round 2's fixes,
including a section heading contradicting its own paragraph two lines down. The
sharpest was this sentence, in the section above about the frontier table:

> ...gives **210 tests, OK**, while `make frontier` correctly exits 2.

That number was **accurate when written**. The next commit in the same correction
sequence added `tests/test_lessons.py`, three tests, and did not update the
sentence. Its own commit message said 213. A published number, inside the section
about published numbers going unguarded, silently falsified by the diff that was
supposed to be fixing exactly that.

We re-ran the experiment and pasted the literal output rather than editing the
number by hand, which is the only version of this that does not recur.

### What the correction rounds are actually evidence of

Every round's fix introduced the next round's defect. That happened three times
consecutively, in a document written by people who at that moment were paying more
attention to this failure mode than they ever had.

Two things generalize:

**Corrections are where defects concentrate.** They are written in the belief that
the problem is now understood, which is exactly when scrutiny drops. A correction
gets less review than the thing it corrects, and it is edited in prose that has
already been rewritten once, so contradictions accumulate between paragraphs that
were never re-read together.

**A claim that is true when written, and guarded by nothing, will drift.** The 210
was not an error. It was a correct measurement with no mechanism attaching it to
the thing it measured. Three tests were added fifteen minutes later and it became
false with no signal anywhere. That is the same failure as the three findings above,
arriving by a different route: not a check that cannot fail, but a number that
nothing checks.

If you take one thing from this page, take this: findings 1 through 3 came from one
audit. Everything in this section came from auditing that audit, three more times.

Each round is a separate commit, so the number of rounds is checkable. The
per-round finding counts above are reported from the reviews and are not checkable
from this repository, which is precisely the property this finding is about. We are
leaving them in and labelled rather than dropping them, because a reader deserves
the shape of the thing even when we cannot hand them the mechanism.

One pass is not a process. It is the first sample.

## How to check your own

None of this required special tooling. Five questions, each answerable in minutes:

1. **Can each CI step actually fail?** Force one to fail and confirm the build goes
   red. Shell loops, `|| true`, and functions returning a constant are the usual
   culprits.
2. **Is every published number asserted somewhere a test runner will catch?**
   Change one to a wrong value and run only your test suite, not the full pipeline.
3. **Are your assertions tautological?** An assertion comparing a value to the same
   constant your docs quote cannot fail when the constant changes.
4. **Does your documented output match the real output?** Run the command in your
   README and diff it against what you published.
5. **Which of your published numbers were correct when written and have nothing
   attaching them to what they measure?** Those do not fail. They drift. Grep your
   docs for figures, and for each one ask what would have to break for anything to
   notice.

Question 2 is the one that caught the repository. Question 5 is the one that caught
this document, twice. Neither gets run, because the full pipeline is green and that
feels like the same thing.

## Limits

This is a self-audit, not an independent one. We wrote both the method and the
target. Several things a hostile reader would reach for, stated before they have to:

**Only one of the three reached `main` as a check that could not fail.** Finding 1
dates to the repository's first commit and is genuine long-standing state.

Finding 2 is mixed: the unconditional `return 0` shipped on `main` 26 days
earlier, but it was harmless prose until the commit under audit *promoted the
script to a gate* by adding `make mutation` and wiring it into `make reproduce`.
Finding 3 was introduced outright by that same commit. Both were fixed ten
minutes later, in one commit, on an unmerged branch. **Two green CI runs contain
them.** They were caught in pre-merge review, which is where review is supposed to
catch things.

Read findings 2 and 3 as evidence that this failure mode is easy to introduce
while actively looking for it, not as evidence of years of rot.

**The repository's own question 2 does not pass for the frontier table.** Changing
a published bound upstream of the committed artifact still leaves the test suite
green; only `make frontier` catches it. We fixed the claim rather than the
underlying coupling.

**No test parses this README.** (`test_packaging.py` does parse `CHANGELOG.md` and
`CITATION.cff` for version strings; the README is the gap.) Every "published
number" test hardcodes the value in its assertion and names the README claim in a
docstring. Edit a number in the prose by hand and nothing fails. The link between a
published sentence and the assertion guarding it is convention, enforced by review.
For a project whose thesis is about claims and their guards, that is the largest
remaining gap, and it is not fixed.

**Findings 1 through 3 were low severity.** All five lessons passed, the kill rate
was intact, and every number the repository published was correct. Those three
caught no wrong result; they caught three ways a wrong result would not have been
noticed. Finding 4 is different in kind: it caught published numbers that were
wrong on the page and shipped that way.

**The headline experiment is synthetic.** The 98-scenario fixture measures a
property of a specific eval design, not a production prevalence rate. That
distinction is stated throughout the repository and applies to this document.

**This document needed four rounds of correction.** Every round's fix introduced at
least one defect that the next round caught, including the round that added Finding
4 itself: it left a stale test count and introduced a five-item list under a
four-item heading. The specific errors are in Finding 4 and in the commit history.
A reader is entitled to treat that as evidence about our care as much as evidence
about the failure mode. We think it is both, and we would rather publish the
sequence than a clean draft that hid it.

**Some claims here are not checkable from the repository.** The timing, the
concurrency, and the AST methodology attributed to the invariant review are
reported from the run, not reconstructible from a checked-in transcript. The AST
result itself was independently reproduced; the process claim was not.

## Reproduce it

```bash
make reproduce PYTHON=python3.12
```

Commits: [`77a563b`](../../../commit/77a563b) fixes the lessons loop,
[`73a3f50`](../../../commit/73a3f50) fixes the exit code and the claim gaps. The
three agents are checked in under `.claude/agents/` and run against any diff.
