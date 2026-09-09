# Start here with your own data

If the package is installed, `agent-economics demo --extract .` writes these
five files into the current directory for you. Everything below explains what
goes in them.


Every other example in this repository runs on data already committed here.
This one does not. Copy the five files below, replace their contents with
your runs, and the three commands at the bottom produce a decision.

## The five files you replace

| file | what it is | columns or keys |
|---|---|---|
| [`support_trace.csv`](support_trace.csv) | one row per event your agent emitted | `task_id`, `event_id`, `timestamp`, `event_type`, `name`, `model`, `input_tokens`, `output_tokens`, `direct_cost_usd`, `status`, `arguments` |
| [`outcomes.csv`](outcomes.csv) | one row per task, whether it was acceptable | `task_id`, `acceptable`, `business_value_usd`, `human_minutes`, `remediation_cost_usd`, `incident_loss_usd` |
| [`rates.json`](rates.json) | price per model, so token counts become money | one entry per model id |
| [`baseline.json`](baseline.json) | the alternative you are comparing against, usually humans | `cost_per_attempt_usd`, `acceptable_rate`, `value_per_acceptable_outcome_usd` |
| [`policy.json`](policy.json) | the thresholds you are willing to defend | nine keys, see below |

`direct_cost_usd` is optional. Leave it blank and the cost comes from
`rates.json`; supply it and the supplied figure wins. Leaving both empty is
not free, it is unpriced, and the gate refuses rather than scoring it zero.

## Setting the numbers you do not have yet

Most teams stall on `baseline.json` and `policy.json`, because both ask for
figures nobody has written down. Reasonable first passes:

- `cost_per_attempt_usd`: fully loaded hourly cost of whoever does this work
  today, times median handle time in hours.
- `acceptable_rate`: pass rate from your existing QA sample. If you do not
  sample, this is the finding, not the blocker.
- `value_per_acceptable_outcome_usd`: revenue per resolved unit, or avoided
  contractor cost, or avoided penalty. This is usually a negotiation with
  whoever owns the P&L rather than an afternoon's work, and a wrong number
  here moves the verdict, so record where it came from.
- `max_calls_per_task`: the p99 of what your current traces already do.
- `min_acceptable_rate` and the cost ceilings: start from the baseline above.
  A gate you cannot justify out loud is a gate that will be argued away the
  first time it fires.

These are starting points, not standards. The thresholds are yours to defend.

## If a model labelled your outcomes

Then `--label-source` names a model, and the gate wants to know how good that
labeller is before it counts the labels. Supply an
[`attestations.json`](attestations.json) record whose `method` is one of
these, meeting its floor, with at least 100 samples, measured within the last
180 days:

| method | floor |
|---|---|
| `agreement-vs-human-adjudication` | 0.80 |
| `raw-agreement` | 0.80 |
| `cohens-kappa` | 0.60 |
| `fleiss-kappa` | 0.60 |
| `krippendorff-alpha` | 0.667 |
| `held-out-accuracy` | 0.80 |

`test-retest-agreement` has a floor of 0.80 and can never clear the gate on
its own: an instrument that repeats itself can be consistently wrong about
everything. An unknown method is refused rather than graded on some other
method's scale, and a future-dated calibration is not a calibration.

The corpus in [`research/CORPUS.md`](../research/CORPUS.md) is what happens
when nobody runs this check: seven models asked to verify correctness reached
AUC 0.501 to 0.653 against a checkable answer, and one was indistinguishable
from a coin.

## The three commands

```
agent-economics bundle \
  --traces support_trace.csv --outcomes outcomes.csv \
  --rates rates.json --baseline baseline.json --policy policy.json \
  --label-source human-adjudication --out bundle.json

agent-economics evaluate --bundle bundle.json

agent-economics claim --bundle bundle.json \
  --assertion "This agent earns expanded autonomy on support triage." \
  --source-commit $(git rev-parse HEAD) --output claim.json
```

`evaluate` prints one of four answers. `INCOMPLETE` means a required gate had
no evidence, and it is the common first result: the tool refuses to score you
rather than scoring you on what happened to be present. `STOP`, `ASSIST` and
`SCALE` are decisions. Only `SCALE` exits 0.

`claim` writes a file anyone can check with
`agent-economics verify --claim claim.json --bundle bundle.json`, without
trusting you or this repository. It exits 0 for SUPPORTED, 2 for UNVERIFIED
and 4 for REFUTED. Pass `--source-commit` or the claim cannot be rechecked
once the code moves.

## The rest of this directory

| path | what it shows |
|---|---|
| [`public-swebench/`](public-swebench/) | the worked case on public SWE-bench trajectories, end to end |
| [`kimi-judge/`](kimi-judge/) | labelling outcomes with a model, then gating on that label |
| [`claude-code/`](claude-code/), [`claude-code-tree/`](claude-code-tree/) | converting Claude Code sessions into evidence |
| [`otel-genai/`](otel-genai/) | converting OpenTelemetry GenAI spans |
| [`compute-frontier/`](compute-frontier/) | comparing configurations on identical tasks |
| [`checks-only/`](checks-only/) | what the harness reports when it cannot price anything |
| [`assurance-case.md`](assurance-case.md) | a rendered decision, for reference |
| [`modularity_demo.py`](modularity_demo.py) | using the checks as a library |
