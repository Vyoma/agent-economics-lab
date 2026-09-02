# Lessons

Corrections that must not recur. Each is a rule plus the evidence that produced it.

## The defect I keep shipping has one shape

Information sufficient to refuse existed, and was flattened into a pass or a
fail at a boundary. Nine instances in this repository, seven of them mine.

The boundaries where it happened are not the ones tests watch:

- A **renderer**. The audit printed `$0.0000 of delegated spend` for a bundle
  that declared no rate card. The verdict was correct; the number was invented
  at the last step before a human read it.
- An **arithmetic default**. `direct_cost_usd or 0.0` in cost-weighted closure
  meant every rate-priced event weighed nothing. $100 declared and $18
  undelegated reported 100% closure and $0.00 unaccounted.
- An **incentive**. A missing evidence instrument was a note while an unattested
  one was a ground, so deleting the field that says what produced your labels
  was the cheapest way to pass.

**Rule:** after any change that produces a number a human reads, ask what that
number would look like if it were wrong, and construct the input that makes it
wrong. Defects 8 and 9 were both found this way. Neither was found by a test,
and 455 tests were passing when both were live.

**Rule:** a ratio over an empty denominator is not a measurement. Say "this run
delegated no work", never "closure 100%".

## Verification must not need anything the verifier will not have

A generator walked git history at verification time. Fine on a full local
clone, broken on every shallow CI checkout. That cost five red commits, was
written up in docs/novelty.md as a story, and then **happened again in
`research/green_defects.py`** in the same repository, because a story is not a
rule and nothing checked for the shape.

**Rule:** before putting anything in `make reproduce`, list what it reads that
is not a file in the repository -- git history, the network, the clock, an
interpreter's own standard library, an environment variable -- and decide
explicitly whether CI has it. If it genuinely needs the thing, configure CI to
provide it and say why in the workflow. If it does not, remove the dependency.

**Rule:** a target that cannot run in CI must not be in `reproduce`.
`make held-out` measures the running interpreter's own stdlib, so its numbers
move with the Python version across a four-version matrix. It is a standalone
target with a version guard, and the reason is written at the recipe.

## The fix for a defect is where the next defect lives

Defect 10 was introduced by the fix for defect 9. Same file, same hour, by
someone who had just written the lesson above about this exact class of error.
Routing closure through the cost resolver was right; the gate then called that
resolver without the rate card sitting one attribute away on the view it
already receives. The suite was green across it.

**Rule:** after fixing a defect, enumerate every caller of the thing you
changed and construct the input that makes each one wrong. `grep` for the
function you touched. A fix narrows one path and widens another, and the
widened one is never the path the failing test exercised.

**Rule:** when a plan's premise turns out to be wrong, say so before building.
This session's plan asserted `direct_cost_usd` needed an `Unsupplied` variant
across 18 sites in 7 files. Ten minutes of probing showed `None` plus an
unsupplied rate card already fails closed, and the real work was two holes
elsewhere. The investigation was worth more than the plan.

## Never assert what a script did; make the script prove it

I printed `"helper added"` from a Python edit whose `str.replace` anchor never
matched, then spent two rounds debugging a `NameError`. The anchor was a
one-line function signature; the real one spanned three lines.

**Rule:** every scripted edit ends with `assert s != before` and a check for the
specific text that should now exist. Never print a success message that the
edit's success does not gate.

## Verify the counter-case, not just the case

I confirmed the attestation flags "worked" against an instrument name I had
guessed rather than read from the bundle. All three cases returned identical
output, which I briefly read as the flags not being wired. They were wired; my
test was wrong.

**Rule:** read the actual identifier out of the artifact before asserting
against it. A test where every case gives the same answer is testing nothing.

## An audit that raises is not fail-closed

Closure began raising `UnpricedDelegation` on unknowable cost, which is right,
but `audit()` propagated it. The caller should never have to catch a refusal;
the contract is a withheld verdict.

**Rule:** a refusal inside a component becomes a ground in the report, not an
exception through the front door.

## Gates outside the build gate

The audit is this package's front door and was not in `make reproduce` at all.
The example directory the README described did not exist.

**Rule:** a documented path that no target exercises is an undefended claim.
And after adding a gate, break something on purpose and confirm the gate fails.
Both new targets were proven to fail before being trusted.

## Blocked scope is stated, not silently dropped

A CLI producer for checks-only traces needs `direct_cost_usd` itself to be
unsuppliable: 18 reads across 7 files, and the shape that leaked before when a
metric subclassed `float`. I scoped it out, which was right, but I initially
dropped the *unblocked* half of the same task (wiring `make audit`) without
saying so.

**Rule:** when part of a task is blocked, finish every unblocked part and name
the blocked remainder explicitly. Do not let one blocked sub-item quietly
absorb its siblings.

## Never `git checkout --` a file carrying uncommitted intended work (2026-09-01)

Proving a new guard non-vacuous means corrupting a file and restoring it. I
restored README.md with `git checkout -- README.md` while my own uncommitted
corrections were in it, and wiped them along with the corruption. The rule:
before any corrupt-and-restore experiment, either commit the intended state
first (a WIP commit is fine) or restore by writing back the exact original
string, never by checkout. The same applies to scripted experiments: hold the
original bytes in memory and write them back.

## The checkout rule was too narrow, and I paid for it twice (2026-09-02)

Yesterday's lesson said: never `git checkout -- <file>` during a
corrupt-and-restore experiment. Today I ran `git checkout <branch> -- .` while
carrying a full day of uncommitted work, and wiped all of it: the rule as
written was about experiments, and this was "just" branch management. The rule
as it should have been written: **no `git checkout`, `git switch`, or
`git restore` of tracked paths while `git status` shows modifications you
intend to keep. Commit first, every time; a WIP commit costs nothing and
amend exists.** Rebuilding from session history took an hour that a
five-second commit would have saved.

## Backticks inside double-quoted shell strings execute (2026-09-02)

A gh pr create --body "..." with markdown backticks ran `RecursionError` and
`verify` as command substitutions and shipped a mangled body. Markdown bodies
go through --body-file with a single-quoted heredoc, never inline in double
quotes.

## The pre-push gate is make reproduce, not the test suite (2026-09-02)

Twice in one session CI caught PROBE_SITES.md drift the local unittest run
could not see, costing a full CI round-trip each time. Any change that
touches agent_economics/ can move pre-registered sites; the generated-doc
byte-compares live in `make reproduce`. Run it before every push, not just
the suite.
