# Defects that were live while the suite was green

Each row checks out the commit before the defect's fix, runs the whole suite there, and runs a probe that discriminates. Nothing is reintroduced and nothing is synthetic: these are the states the repository was actually in.

| id | defect | commit | tests passing | suite green |
|---|---|---|---|---|
| D07 | the gate paid teams to delete their own honesty field | `4b60e19` | 448 | **yes** |
| D08 | a dollar figure computed from costs nothing had priced | `4b60e19` | 448 | **yes** |
| D09 | rate-priced subagent spend weighed nothing | `ffb6ca4` | 455 | **yes** |
| D10 | the fix for D09 left the gate unable to price anything | `dbc28e8` | 462 | **yes** |
| D11 | tool calls asserted free with no rate card to say so | `dbc28e8` | 462 | **yes** |

**5 of 5 defects were live at a commit where the entire suite passed**, across 2275 passing tests in total.

## What each probe asked

### D07 — the gate paid teams to delete their own honesty field

- **File:** `agent_economics/audit.py`
- **Live at** `4b60e19`, **fixed by** `ffb6ca4`
- **Mechanism:** A missing evidence instrument was a note while an unattested one was a ground. Declaring what produced your labels made a bundle unassessable; recording nothing made it assessable.
- **Why no test expressed it:** Both behaviours were individually correct and individually tested. The defect is the *relation* between two cases, which no single-case assertion can express.
- **Probe:** does deleting the field naming your label source buy a pass?
  - while live: `{'declared_assessable': False, 'deleted_assessable': True}`
  - after the fix: `{'declared_assessable': False, 'deleted_assessable': False}`
  - true answer: `{'declared_assessable': False, 'deleted_assessable': False}`

### D08 — a dollar figure computed from costs nothing had priced

- **File:** `agent_economics/audit.py`
- **Live at** `4b60e19`, **fixed by** `ffb6ca4`
- **Mechanism:** The audit rendered '$0.0000 of delegated spend' for a bundle that declared no rate card. The verdict was right at every step; the number was invented at the renderer.
- **Why no test expressed it:** Renderer tests assert on words, not on the numbers between them, and every verdict assertion passed because every verdict was correct. The refusal held in the logic and leaked at the last inch.
- **Probe:** does a bundle report dollars for spend nothing could price?
  - while live: `{'dollar_lines': ['$0.0000 of delegated spend is unassessed; closure 0%.']}`
  - after the fix: `{'dollar_lines': []}`
  - true answer: `{'dollar_lines': []}`

### D09 — rate-priced subagent spend weighed nothing

- **File:** `agent_economics/delegation.py`
- **Live at** `ffb6ca4`, **fixed by** `93c3552`
- **Mechanism:** Cost-weighted closure summed `direct_cost_usd or 0.0` rather than calling the resolver every other consumer uses, so any event priced by the rate card counted as free.
- **Why no test expressed it:** Every adapter-built bundle sets an explicit cost, so every fixture in the suite took the one branch that worked. The documented CSV evidence path leaves the column blank and had no fixture.
- **Probe:** how much undeclared delegated spend goes unreported?
  - while live: `{'closure_pct': 100.0, 'unaccounted_usd': 0.0}`
  - after the fix: `{'closure_pct': 84.7, 'unaccounted_usd': 18.0}`
  - true answer: `{'closure_pct': 84.7, 'unaccounted_usd': 18.0}`

### D10 — the fix for D09 left the gate unable to price anything

- **File:** `agent_economics/delegation.py`
- **Live at** `dbc28e8`, **fixed by** `dc72ae6`
- **Introduced by the fix for D09.**
- **Mechanism:** `delegation_closure_gate` called `assess_closure` without rates, though the view it receives carries them, so a rate-priced bundle became unpriceable inside the gate.
- **Why no test expressed it:** Introduced by the fix for D09, in the same file, within the hour, by an agent that had just written the lesson about this class of error. No test drove a rate-priced delegation through the gate rather than through the report.
- **Probe:** can the gate price a delegation whose rate card it was handed?
  - while live: `{'raised': 'UnpricedDelegation', 'priced_18': False}`
  - after the fix: `{'raised': None, 'priced_18': True}`
  - true answer: `{'raised': None, 'priced_18': True}`

### D11 — tool calls asserted free with no rate card to say so

- **File:** `agent_economics/delegation.py`
- **Live at** `dbc28e8`, **fixed by** `dc72ae6`
- **Mechanism:** Cost resolution answered 0.0 for any non-model event before consulting rates. Which tools are billed is exactly what a rate card says, so with none the claim is unsupported.
- **Why no test expressed it:** True of every fixture in the suite, because every fixture had a rate card. The claim is only wrong in the configuration no test constructed.
- **Probe:** with no rate card, is unpriced tool spend reported as zero dollars?
  - while live: `{'basis': 'cost', 'unaccounted_usd': 0.0}`
  - after the fix: `{'basis': 'count', 'unaccounted_usd': None}`
  - true answer: `{'basis': 'count', 'unaccounted_usd': None}`

## The claim this supports, and its limits

A green suite is evidence that specified behaviour holds. It is not evidence that the specification produces a number worth reporting. Every defect above sat inside that gap, in a package built to close it, written by someone hunting this exact failure.

Population: 5 defects, one repository, one author, one day. That is a case series, not a rate. It does not estimate how often this happens elsewhere and no sampling frame supports generalising it. What it does establish is existence and mechanism: these defects are reachable, they are of a kind, and the technique that found them is stated precisely enough to try.

