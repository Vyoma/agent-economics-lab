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
