# Recipes

Every worked example, moved out of the README so the front page can lead with
what was found rather than with instructions. Each one runs against data in this
repository and each number below is produced by a `make` target, not typed.

Start with [the README](../README.md) for what this is and why. Come here when
you want to run something.

## Run the full decision

Python 3.10+. No cloud account. No third-party runtime packages.

```bash
make demo
```

The included support workload creates positive value versus its human-only
alternative, but the result is still `ASSIST`: outcome quality, unit cost, tail cost,
and runtime caps fail policy. A profitable agent is not automatically a scalable
agent.

This is the literal output, not a summary of it. A test asserts these lines appear
verbatim in what `make demo` prints, so this block cannot drift from the code:

```text
**Decision: ASSIST**

| Measure | Result |
|---|---:|
| Attempts | 8 |
| Acceptable outcomes | 6 (75.0%) |
| Total effective cost | $21.02 |
| Cost per acceptable outcome | $3.50 |
| p95 effective task cost | $14.25 |
| Maximum effective task cost | $14.25 |
| Expected net value per attempt | $3.37 |

- **FAIL · gate.acceptable-rate:** acceptable_rate 75.0% < 80.0%
- **FAIL · gate.unit-economics:** cost_per_acceptable_outcome $3.50 > $2.00
- **FAIL · gate.tail-cost:** p95_task_cost $14.25 > $8.00
- **PASS · gate.net-value:** expected_net_value_per_attempt $3.37 >= $0.00
- **PASS · gate.counterfactual:** incremental_net_value_vs_baseline $2.77 >= $0.00
- **FAIL · gate.runtime-caps:** t-005: 12 calls > cap of 8
- **FAIL · gate.runtime-caps:** t-005: $0.2454 trace cost > cap of $0.1500
```

The full report also prints the assurance manifest, the counterfactual table, the
diagnostic findings, and a claim boundary.

<details>
<summary>Why the output above is text and not a terminal recording</summary>

A recording cannot be re-verified when the code changes. Every other number in this
README is checked byte-for-byte in CI, so a screencast is the one artifact that could
drift out of date without failing anything. The block above is produced by the same
command and asserted line-by-line by a test.

</details>

That is the assurance case: evidence, the fixed decision contract, and routing
semantics remain inspectable.

## Run a non-synthetic public case

Twenty paired SWE-bench Verified tasks compare real mini-SWE-agent trajectories
using Claude Opus 4.6 and Claude Haiku 4.5:

```bash
make public-case
```

Opus resolves `14/20` tasks versus Haiku's `11/20`, while costing 56.9% more
per attempt and 23.3% more per resolved task.

**The useful result is the frontier's `HOLD`, not the engine's `STOP`.** One
harmful transition in 20 pairs gives an exact one-sided upper bound of 24.9% on
the harmful-regression rate, against a predeclared 5% limit. Twenty paired tasks
cannot detect the regression rate the decision depends on, so the honest answer is
that the comparison is undecided. Teams approve model downgrades on evaluations
this size routinely.

**Read the `STOP` with care: it is forced, not earned.** A benchmark resolution is
credited $0 of business value, because the public source publishes no defensible
value for one, and the net-value gate requires a non-negative result. Total cost is
positive, so `expected_net_value` is negative for *any* set of outcome labels and
the routing cannot be anything but `STOP`. That is arithmetic, not a finding about
either model. It demonstrates the refusal path and the audit trail; it says nothing
about whether Opus is worth its price.

Prompts, reasoning, patches, and tool output are excluded, while each complete
public trajectory remains verifiable by its upstream path and SHA-256 digest.

[Inspect the public case](../examples/public-swebench/) ·
[Read the AssuranceCase](../examples/public-swebench/assurance-case.md) ·
[Read the paired frontier](../examples/public-swebench/frontier/frontier.md)

## Compose a contract by name

`agent-economics capabilities` lists every check this build can run. Two of
them — delegation closure and evidence provenance — shipped, were documented,
and reached no command-line decision at all, because the check set was a
literal compiled into four consumers rather than something a caller could ask
for.

```bash
agent-economics evaluate --bundle bundle.json \
  --check gate.acceptable-rate \
  --check gate.delegation-closure \
  --require-coverage outcome_quality \
  --require-coverage delegation_closure
```

Order matters, because the decision-contract digest binds it: the same checks
in a different order are a different contract. A check the build cannot
resolve is refused with exit 2 rather than dropped, because a contract naming a
check nobody can build is unreadable rather than weaker.

Both of those gates are built from the evidence itself — the delegation
manifest the bundle declares, the instrument it names — so naming one on a
command line is enough. A contract that let the caller supply the manifest
could declare every delegation accounted for without the evidence saying so.

## Ask what your harness cannot tell you

```bash
agent-economics audit --bundle bundle.json --ci
```

One command, four grounds for withholding a verdict: required coverage no check
supplies, which gates actually carry this run, delegated work nobody undertook to
assess, and instruments nobody validated. None of them is a score. Each is a
reason the honest answer is `INCOMPLETE`.

`evaluate` asks the same question before it will say `SCALE`: a green decision
the audit refuses comes back `INCOMPLETE` with the grounds, so this command
and `evaluate --ci` cannot disagree about one bundle. Pass the calibration
records to either with the same `--attestations` flag.

The fourth ground asks what validated your evidence instruments. Answer it by
supplying their calibration records; without one, the audit withholds:

```bash
agent-economics audit --bundle bundle.json \
  --attestations attestations.json --as-of 2026-08-27
```

Each record states a method, an agreement figure, a sample size, what it was
measured against, and when. Agreement is checked against a floor for its own
method, and an unknown method is refused rather than graded on another method's
scale. An instrument whose output is independently checked by something else is
not the sole provider of its evidence and may be exempted with
`--independently-verified`.

A bundle that records no instrument at all is also withheld, and this is
deliberate. While that was merely noted, declaring what produced your labels
made a bundle unassessable until attested and recording nothing made it
assessable, so the tool paid you to delete the field.

It runs on a bundle with no economics at all, so a team with a PII gate and a
jailbreak gate can ask the question without first inventing a rate card. Convert
a real session under a contract that declares no pricing:

```json
{ "pricing": { "unsupplied": "rates" } }
```

Every call keeps its true token counts and states no cost, because nothing
priced it. Where the cost of delegated work cannot be established, closure
counts delegations instead of weighting them by spend and says which it did:
a share of counts and a share of spend are different quantities, so the report
may state the count ratio and the gate refuses to compare it against a
threshold meaning spend. See `examples/checks-only/`, the same session as
`examples/claude-code/` converted without a price card.



```text
- Verdict on the evidence as supplied: **STOP**
- Withheld on: **unprovided coverage**

- `refusal_rate` — no enabled check supplies this
- `jailbreak_safety` is pivotal: removing it flips this run green
```

## Find the cheapest tested configuration that still clears policy

```bash
make frontier
```

The paired frontier runs four configurations on the same 180 synthetic task input
digests and frozen rubric:

```text
Decision                         ADOPT balanced-4-step

Candidate            Absolute UCB   Conditional H/R+   Cost LCB   Result
balanced-4-step             3.7%             1/171       32.0%   eligible
cheap-2-step               12.5%            12/171       29.9%   quality fails
premium-12-step             2.6%             0/171      -38.9%   cost fails
```

The absolute H/N upper bound governs v1 eligibility. The conditional H/R+ rate is
reported because a weak reference can hide breakage in the absolute denominator.
The selected arm's observed cost rank is post-selection exploratory and needs a
held-out or independently replicated confirmation before generalization.

[Read the method](frontier.md) ·
[Inspect the decision](../research/results/frontier/frontier.md) ·
[See the protocol](../research/FRONTIER_PROTOCOL.md) ·
[Review the data card](../research/FRONTIER_DATA_CARD.md)

## Convert a Claude Code session without inventing its economics

Claude Code JSONL contains execution facts, not acceptable-outcome labels, a
counterfactual baseline, or a complete price contract. The converter therefore has
two explicit phases:

```bash
agent-economics convert \
  --from claude-code \
  --in session.jsonl \
  --template conversion-contract.json

# Complete the labels, rate tiers, tool costs, baseline, and policy.

agent-economics convert \
  --from claude-code \
  --in session.jsonl \
  --contract conversion-contract.json \
  --out bundle.json

agent-economics evaluate --bundle bundle.json
```

The adapter deduplicates streamed assistant fragments into model calls, prices
base/cache/server-tool usage from the supplied contract, discards prompt and
response content, preserves only content-free tool-argument type shape, and refuses unresolved
delegation or incomplete tool-call inventories.

[Read the adapter contract](claude-code-adapter.md) ·
[Inspect the complete fixture](../examples/claude-code/)

## Include delegated Claude Code subagent spend

The separate `claude-code-tree` adapter expands the parent transcript and every
paired subagent transcript before applying the same conversion contract:

```bash
agent-economics convert \
  --from claude-code-tree \
  --in session.jsonl \
  --template conversion-contract.json
```

The adapter discovers `session/subagents/agent-<id>.jsonl` and its matching
metadata files next to `session.jsonl`. Root external prompts remain the economic
tasks. Child model and tool calls inherit the task that spawned them. The source
digest binds the parent, every child transcript, and every metadata file.

Missing pairs, unknown delegation links, duplicate tool identities, inconsistent
spawn depth, and any remaining unexpanded `Agent` or `Task` call return
`INCOMPLETE`. The child bootstrap envelope is verified but not counted twice.

```bash
make claude-code-tree
```

[Read the session-tree contract](claude-code-tree-adapter.md) ·
[Inspect the complete tree fixture](../examples/claude-code-tree/)

## Convert OpenTelemetry GenAI exports with one pinned contract

The generic OTLP JSON adapter is tested against content-safe fixtures derived from
Langfuse and Arize OpenInference. It is pinned to OpenTelemetry Semantic
Conventions `1.43.0` and GenAI commit `799e014`.

```bash
agent-economics convert \
  --from otel-genai \
  --in traces.otlp.json \
  --template conversion-contract.json

# Approve trace-to-task mapping. Add labels, prices, baseline, and policy.

agent-economics convert \
  --from otel-genai \
  --in traces.otlp.json \
  --contract conversion-contract.json \
  --out bundle.json
```

The adapter decodes only economic GenAI attributes. It drops prompt, response,
message, tool-definition, argument, and result values. Unknown operations,
unresolved parents, unapproved task mapping, missing usage, and incomplete price
cards return `INCOMPLETE`.

Parent span relationships become typed dependency edges covered by the evidence
digest. The same typed edge field is also populated from Claude Code `parentUuid`
relationships.

[Read the OpenTelemetry contract](otel-genai-adapter.md) ·
[Inspect both fixtures](../examples/otel-genai/)

## Label outcomes with Kimi instead of hand-writing them

The one input the engine cannot derive is whether an outcome was acceptable. Two
optional integrations call the [Kimi API](https://platform.kimi.ai/docs/api/chat)
on `kimi-k3`, Moonshot's current flagship, using stdlib `urllib` and no added
dependencies, so that label comes from a frozen rubric rather than from whoever
edited the CSV:

```bash
# Paste your real key. It is "sk-" plus roughly 48 more characters.
export MOONSHOT_API_KEY='sk-REPLACE_THIS_WITH_YOUR_KEY'

agent-economics judge \
  --task-results examples/kimi-judge/task_results.csv \
  --rubric examples/kimi-judge/rubric.json \
  --out outcomes.csv

agent-economics analyse --case report.json
```

`judge` scores every task against weighted rubric criteria, writes a standard
`outcomes.csv`, and writes an audit sidecar recording the model, reasoning depth,
output contract, and every per-criterion score. `analyse` reads an
`evaluate --format json` report and returns recommendations against the same
thresholds.

The request contract is pinned to K3's documented shape: verdicts are forced
through a strict JSON schema derived from the rubric, output length uses
`max_completion_tokens`, sampling parameters are omitted because K3 fixes them
server-side, and the invariant system prompt is sent first so automatic context
caching can reuse it across a batch. Transient `429` and `5xx` responses are
retried with backoff; a `401` fails immediately. That retry policy is load
bearing rather than hygiene: an exhausted call labels the task unacceptable, so a
swallowed rate limit would quietly depress `acceptable_rate` and move every gate
downstream of it.

All inference in the package routes through one client,
`agent_economics.kimi_client`, and a test enforces that: it fails if any module
opens its own connection, declares a second endpoint, or imports another
provider's SDK. The decision kernel is excluded by the same test and performs no
inference at all, because cost reconstruction, gates, and confidence bounds are
arithmetic and their byte-reproducibility is the property this repo exists to
provide. A model belongs where a judgment cannot be computed, and nowhere else.

The label is still a claim owned by the data owner. An LLM judge moves who
authored it, not whether it needs validation: check agreement against human
labels on a sample before trusting the economics built on top.

```bash
make kimi-judge      # live call, requires MOONSHOT_API_KEY
make kimi-eval       # score the judge against 25 labelled cases
make kimi-doctor     # diagnose a 401 without printing the key
make test            # rubric, schema, retry, and fallback conformance, mocked
```

The judge is measured, not just mocked. `make kimi-eval` scores it against 25
constructed cases across eight categories and reports a **false-accept
rate**: unacceptable work labelled acceptable inflates `acceptable_rate` and can
turn a `STOP` into a `SCALE`. Expected labels follow from the rubric's own weights,
and a test checks that arithmetic against the rubric file.

Moonshot runs three credential systems whose keys and base URLs are not
interchangeable, so a valid key returns `401` against the wrong one:

| Key from | Base URL |
|---|---|
| platform.kimi.ai | `api.moonshot.ai/v1` (default) |
| platform.moonshot.cn | `api.moonshot.cn/v1` |
| kimi.com/code | `api.kimi.com/coding/v1` |

`export MOONSHOT_BASE_URL=https://<host>` selects one. `make kimi-doctor` probes
all three and reports which accepts your key, without printing it.

The conformance tests mock every API call, so `make reproduce` stays hermetic and
needs no key.

[Read the integration contract](kimi-integration.md) ·
[Inspect the rubric and fixture](../examples/kimi-judge/)

## Put the decision contract in a pull request

The composite GitHub Action installs the package, runs the same `evaluate --ci`
path as the CLI, and optionally upserts the Markdown assurance report on the pull
request. Only `SCALE` passes. `INCOMPLETE`, `ASSIST`, and `STOP` fail the check.

```yaml
name: agent-economics

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  assurance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: Vyoma/agent-economics-lab@main # Preview only. Pin a commit SHA.
        with:
          bundle: evidence/agent-economics-bundle.json
          github-token: ${{ github.token }}
```

Use exactly one mode:

| Mode | Inputs |
|---|---|
| normalized bundle | `bundle` |
| CSV evidence | `traces`, `outcomes`, `rates`, `baseline`, `policy` |
| offline conversion | `adapter`, `session`, `contract` |

Partial or conflicting modes return `INCOMPLETE`. The action exposes `decision`,
`exit-code`, and `report` outputs. During dogfood, pin an exact commit SHA for any
production use. Stable `v1` tags follow successful dogfood rather than preceding
it.

[Inspect the action contract](../action.yml)

## Delete actual evidence

Gate disablement and evidence deletion are different experiments. The second
executable deletes real raw records and fields while keeping checks, coverage, and
the decision-contract digest fixed:

```bash
python3 evidence_ablation.py
```

```text
ablations                  9
operational refusals       4
ASSIST -> SCALE             5
INCOMPLETE case artifacts  0
```

The five transitions expose two concrete source-contract gaps: omitted cost fields
can become zero, and a deleted timed-out event is invisible without an independent
attempt manifest. They are boundary cases, not a failure rate.

[Read the evidence-ablation protocol](../research/EVIDENCE_ABLATION_PROTOCOL.md) ·
[Inspect the generated rows](../research/results/evidence-ablation/results.csv)

## Decide over more events than memory holds

The engine is linear to a million events in one process
([the measured envelope](at-scale.md)), and evidence bundles are in-memory
objects, so the wall past that is memory, not time. The supported answer is
sharding: split the fleet's window into cohorts, decide each cohort, and
issue one claim per cohort. Nothing about the contract weakens — each shard
carries its own evidence digest, its own bounded decision, and its own
claim, and a reader verifies each shard exactly as they would one bundle.

```bash
# one decision and one portable claim per week-sized shard
for shard in evidence/week-*.csv; do
  agent-economics evaluate --traces "$shard" ... --ci
  agent-economics claim --bundle "$shard" ...
done
```

What sharding does not license: computing a fleet-wide rate by averaging
shard rates without weighting, or letting a green shard speak for a red one.
A fleet answer is the set of shard decisions, worst decision governing, the
same way one bundle's worst gate governs its decision.

## The kernel

Keep the observability, evaluation, and runtime-control tools you already use.
Normalize their offline exports, then issue an inspectable decision artifact.

```text
traces + outcomes + labor/risk cost + baseline + policy
                            |
canonical evidence + digest
                            |
     typed checks + fixed required coverage
                            |
       decision-contract digest + bounded decision
```

Delete an optional diagnostic and only its warning disappears. Disable a
sole-provider gate while the contract stays fixed and the decision becomes
`INCOMPLETE`. Add a local gate and it can restrict the result without editing the
core.

```bash
make modularity
```

[Methodology](methodology.md) ·
[Modularity contract](modularity.md) ·
[Architecture](../ARCHITECTURE.md) ·
[Limitations](limitations.md)

