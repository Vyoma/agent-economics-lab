# Kimi outcome labeling and advisor

Two optional integrations call the Moonshot [Kimi API](https://platform.kimi.ai/docs/api/chat):

```text
kimi-judge@1    label task outcomes against a frozen rubric
kimi-analyst@1  recommend fixes from an evaluate --format json report
```

Both use stdlib `urllib` only. Neither is required to evaluate a bundle, and
neither runs in `make reproduce`: the conformance tests mock every call so the
offline suite stays hermetic.

## One egress, enforced

Every model call in the package goes through
[`agent_economics/kimi_client.py`](../agent_economics/kimi_client.py). Provider,
model, request contract, and retry policy are declared there once. Both
integrations delegate to it, and `agent-economics capabilities` prints what is in
force:

```text
INFERENCE
provider  moonshot-ai  (MOONSHOT_API_KEY required)
model     kimi-k3  reasoning_effort=max
egress    agent_economics.kimi_client  (single call path)
```

[`tests/test_inference_routing.py`](../tests/test_inference_routing.py) enforces
this rather than trusting it. It fails if any module opens its own connection,
declares a second endpoint, imports another provider's SDK, references another
provider's host, or reaches the client from an undeclared module. Each of those
classes was verified to fail by introducing the violation and observing the test
catch it.

**The decision kernel performs no inference and must not.** Cost reconstruction,
gate evaluation, confidence bounds, and digests are arithmetic, and their
byte-reproducibility is the property the repository exists to provide. Routing any
of them through a model would make verdicts non-deterministic and void the
fixed-contract guarantee, so a separate test asserts that no kernel module
mentions Kimi or opens a connection. A model belongs where a judgment cannot be
computed, which is the outcome label and the advisory, and nowhere else.

## What changing the label source did

Verified against the live API on the eight-task support fixture. Identical traces,
rates, baseline, policy, and decision-contract digest; only the outcome column
differs:

```text
hand-authored labels    ASSIST   75.0% acceptable   $3.50/acceptable   +$2.77 vs baseline
kimi-k3 labels          STOP     37.5% acceptable  $14.76/acceptable   -$3.13 vs baseline
```

A full decision class, and the sign of net value, turned on the label source alone.
Neither set is validated ground truth. See
[limitations.md](limitations.md#outcome-labels-can-dominate-the-result) for why that
is the finding rather than an endorsement of either.

## Why an LLM judge at all

The engine can reconstruct cost from a trace. It cannot decide whether an outcome
was acceptable. That label is the single input the economics are most sensitive
to, and hand-authoring `outcomes.csv` puts it beyond review. Routing it through a
frozen rubric and recording every per-criterion score moves the label from
"whoever edited the CSV" to an artifact a reviewer can audit.

This does not make the label correct. It relocates the claim. Validate agreement
against human labels on a sample before trusting anything built on top; see
[limitations.md](limitations.md).

## Request contract

Pinned to the documented K3 chat-completions contract. Each choice below is a
deliberate one, not a default that happened to work.

| Field | Value | Why |
|---|---|---|
| `model` | `kimi-k3` | Current flagship. 1M context, always-reasoning. |
| `reasoning_effort` | `max` (configurable) | K3 always reasons and takes a top-level `reasoning_effort`. `max` is the documented default and the value guaranteed available; `low` and `high` are documented but not guaranteed on every deployment, so they are opt-in via `--reasoning-effort`. |
| `response_format` | `json_schema` with `strict: true` | See below. The judge derives the schema from the rubric's criterion IDs. |
| `max_completion_tokens` | 32768 (judge), 65536 (analyst) | K3 renamed the output-length field; `max_tokens` is not in the K3 schema. Reasoning shares this budget, so it must fit `reasoning_effort=max`. |
| `temperature`, `top_p`, penalties | not sent | Fixed server-side for K3. Sending them is not supported. |
| request timeout | 60s low, 180s high, 420s max | Must cover the reasoning trace, not just the answer. A chat-sized timeout turns every deep-reasoning call into four timed-out attempts and reads as a hang. |

Two further properties of the K3 contract that the code depends on:

- **Only `content` is read.** K3 returns its reasoning separately as
  `reasoning_content`, and a JSON schema constrains the final content field
  rather than the reasoning trace. Parsing the trace would be a bug.
- **The system prompt is invariant within a run and is sent first.** Moonshot's
  context caching is automatic and needs no parameters, but it only helps when
  the prefix is stable. Per-task content therefore goes in the user message. A
  test asserts the system prompt contains no task content, because interpolating
  it there would silently destroy every cache hit.

## If you extend this to multi-turn

Both integrations are single-turn: one request per task, one per report. That
avoids a K3 gotcha that would otherwise bite.

K3 is trained in preserved-thinking-history mode. For multi-turn exchanges and
tool calls, the complete assistant message returned by the API must be appended
to the next request, not just its `content`. Dropping the thinking content, or
switching models mid-session, makes generation quality unstable. Anyone adding a
follow-up turn here must carry the whole assistant message forward.

## Structured output is a forcing function, not a preference

The judge sends a strict JSON schema built from the rubric: every criterion ID is
required, every field has an explicit `type`, and `additionalProperties` is false.

The reason is specific to this pipeline. A malformed response and a genuine
rejection both land in the same fallback, which labels the task unacceptable.
Without a server-enforced schema, a parse failure is indistinguishable from a
real verdict, and it moves `acceptable_rate`, which moves every downstream gate.
Making the server reject bad shapes removes that failure mode from the label
path rather than papering over it.

### The schema cannot express numeric bounds

Moonshot Flavored JSON Schema
([spec](https://github.com/MoonshotAI/walle/blob/main/docs/mfjs-spec.md)) accepts
only `type`, `enum`, and `required` as validation keywords. `minimum` and
`maximum` are rejected with `400 invalid_request_error`, so a schema carrying
them never reaches the model.

This is a trap rather than an inconvenience, because of the fallback. A rejected
schema returns 400 for every task, and a client that treats an error as "not
acceptable" produces a clean-looking 0% acceptable rate from a request that was
never evaluated. Two guards exist:

- `kimi_client.assert_mfjs_compatible` runs before the request and raises locally,
  naming the offending path, so a schema bug surfaces as a developer error rather
  than as a remote 400.
- `_validate_verdict` enforces the `[0.0, 1.0]` bounds in code after parsing,
  since the server cannot. An out-of-range score fails that task's judgment
  instead of flowing into the economics.

The bounds are still stated in each field's `description`, which MFJS does
support, so the model is told the range even though the schema cannot enforce it.

## Retry policy, and what must never be retried

Transient failures are retried up to four attempts with exponential backoff
(1.5s, 3s, 6s) on `408, 409, 425, 429, 500, 502, 503, 504`.

Everything else raises `KimiRequestError` immediately and is **not** caught by
`judge`. A rejected schema, a bad key, or an unknown model is a defect in the
request, not a verdict about the task, so the run aborts and writes no outcomes
file. The provider's own error message is preserved because it names the
offending field.

That split is the whole point. A flaky network on one task should degrade that one
task. A broken request contract must not quietly relabel the entire batch.

## Token budget

K3 always reasons, and reasoning shares `max_completion_tokens`. A budget sized
for a short answer gets spent before any content is emitted, which surfaces as an
empty-content error. With `reasoning_effort` defaulting to `max`, the judge
budgets 32768 and the analyst 65536, both well inside K3's own 131072 default
while still bounding cost.

## Audit trail

Every judged task writes an audit row recording `model_id`, `reasoning_effort`,
`output_contract`, `rubric_id`, per-criterion scores, the overall score, and the
rationale. Label provenance belongs in the assurance case: a reviewer needs to
know which model at which reasoning depth produced a label, under which output
contract.

## Three credential systems, not one

This is the single biggest source of confusion when setting up. Moonshot operates
three separate systems, and per their own documentation the keys and base URLs are
**not interchangeable**:

| Key issued at | Base URL | System |
|---|---|---|
| [platform.kimi.ai](https://platform.kimi.ai) | `api.moonshot.ai/v1` | Open Platform, international (default) |
| [platform.moonshot.cn](https://platform.moonshot.cn) | `api.moonshot.cn/v1` | Open Platform, China |
| [kimi.com/code](https://www.kimi.com/code) | `api.kimi.com/coding/v1` | Kimi Code coding subscription |

A key from one system returns `401 Invalid Authentication` against another even
though the key itself is perfectly valid. Note that Kimi Code uses `/coding/v1`
rather than `/v1`, so the path differs too, not just the host.

Point at the system that issued your key:

```bash
export MOONSHOT_BASE_URL=https://api.kimi.com      # Kimi Code subscription
export MOONSHOT_BASE_URL=https://api.moonshot.cn   # China Open Platform
```

An origin is enough; each host's documented route is filled in. The override is
validated against `KIMI_HOSTS`, so it selects a Kimi system and cannot redirect
inference to another provider. The single-provider invariant therefore holds under
configuration, not only in the source.

### Diagnosing a 401

```bash
make kimi-doctor
```

It probes all three systems with your key and reports which one accepts it, plus
key length, prefix, and whether stray whitespace or quotes are present. It never
prints the key, so the output is safe to share.

- **One system accepts** it names the system and the export to set.
- **All three return 401** the credential itself is rejected. Reissue it.
- **`stray whitespace or quotes: True`** the export captured a newline or quotes.

`require_api_key` strips surrounding whitespace and shell quotes, because a key
pasted with a trailing newline fails identically to a wrong key and that is not a
distinction worth debugging.

A 401 cannot be fixed from this side. The client sends
`Authorization: Bearer <key>` with the key verbatim, which is verified on the wire
by a test. If every system rejects the key, the credential is the problem.

## Usage

```bash
# Paste your real key. It is "sk-" plus roughly 48 more characters.
# A short value or one containing "..." is rejected locally before any request.
export MOONSHOT_API_KEY='sk-REPLACE_THIS_WITH_YOUR_KEY'

agent-economics judge \
  --task-results examples/kimi-judge/task_results.csv \
  --rubric examples/kimi-judge/rubric.json \
  --out outcomes.csv \
  --reasoning-effort max \
  --rate-limit 5

agent-economics analyse --case report.json
```

```bash
make kimi-judge   # live call, requires MOONSHOT_API_KEY
make test         # rubric, schema, retry, and fallback conformance, fully mocked
```

The rubric schema and a worked fixture are in [examples/kimi-judge/](../examples/kimi-judge/).

## What the eval revealed about judge calibration

First live run, eval-set version 1: **95.8% agreement** (23/24), 100% precision on
accept, 100% recall on reject, **0% false-accept rate**, zero errors. Every
factually-wrong, hallucinated-feature, contradicts-context, non-answer, and
policy-breach case was caught.

The single disagreement was more informative than the score. `kimi-k3` rejected a
"correct" answer about deleting a customer record at 0.63, and its rationale was:

> asserts an unverified DELETE endpoint and immediate deletion semantics without
> any caveats about permissions, soft-delete behavior, or data-retention policies,
> risking hallucinated guidance on a destructive operation

**The judge applies extra caution to destructive operations.** A comparable
product-specific answer about rotating an API key passed at 0.88, so this is not
general strictness about product specifics; it is specifically about irreversible
actions asserted without caveats.

On the merits the judge was right and the expected label was wrong: greenlighting an
irreversible deletion without mentioning permissions or recoverability is unsafe
support advice. Version 3 of the eval set therefore splits the scenario into a
caveated answer expected acceptable and an uncaveated one expected unacceptable.

Two practical consequences if you use this judge:

- If your agent legitimately knows your product, put that ground truth in the
  `context` column. Otherwise confident true statements can be scored as
  unsupported.
- Expect stricter labels than a human reviewer would give on destructive or
  irreversible actions. That is a defensible stance, but it lowers
  `acceptable_rate`, and `acceptable_rate` moves every gate downstream. It is part
  of why swapping label sources flipped ASSIST to STOP on the support fixture.

### Version 3 result, and why 100% is weaker than it looks

The restructured set scores **100% agreement** (25/25), and the split behaved as
designed: the caveated deletion answer was accepted at 0.86, the uncaveated one
rejected at 0.68. The judge discriminates on the axis its rationale named.

Three reasons not to quote that figure without them:

1. **It is not a clean held-out measurement.** One case was restructured after
   observing this judge's version-1 behaviour, so version 3 is partly informed by
   the model under test. The version-1 figure of **95.8% is the stronger
   evidence**, because that set had never been touched by model feedback.
2. **Two verdicts sit 0.02 from the threshold**: `dest-01` at 0.68 and `tone-01`
   at 0.72. Either could flip on an identical rerun, which would make the same set
   score 96% or 92%. A margin that thin is not a measurement.
3. **Constructed cases are easier than production traffic.**

Measure the stability before believing the number:

```bash
python3 kimi_eval.py --only dest-01,tone-01 --repeat 5
```

Ten calls. It reports the score spread per case and exits non-zero if any verdict
changed between identical runs. A clean future measurement needs cases this judge
has never influenced.

## Judge eval

The judge decides `acceptable`, the input the economics are most sensitive to. A
component with that leverage needs measuring, not just mocking.

```bash
# Smoke-test three cases first. Deep reasoning is slow, so confirm the path
# works before spending 24 calls.
python3 kimi_eval.py --limit 3

make kimi-eval          # all 24 cases, requires MOONSHOT_API_KEY
make test               # scoring math and eval-set integrity, no key needed
```

`reasoning_effort=max` is the default and is genuinely slow: budget minutes per
case, not seconds. `--reasoning-effort high` or `low` is much faster if your
account supports those levels. Progress prints per case with elapsed time, so a
slow run is distinguishable from a stuck one.

[`research/eval/judge-eval-set.json`](../research/eval/judge-eval-set.json) holds 24
constructed cases, 8 expected-acceptable and 16 expected-unacceptable, across seven
categories: correct, correct-but-curt, factually-wrong, hallucinated-feature,
contradicts-context, non-answer, and policy-breach.

Expected labels are not a matter of taste. They follow from the rubric's own
weights, and a test asserts that arithmetic against the live rubric file:

- accuracy 0.50 + policy 0.30 = 0.80, above the 0.70 threshold, so a **correct
  answer delivered bluntly must still clear**. Tone carries only 0.20.
- policy 0.30 + tone 0.20 = 0.50, below the threshold, so a **factually wrong
  answer cannot clear** however polite it is.

Cases whose label a careful reviewer could reasonably dispute were excluded. The
existing eight-task fixture keeps three such cases, which is why it is a
demonstration rather than an eval.

The metric that matters most is **false-accept rate**: unacceptable work labelled
acceptable inflates `acceptable_rate` and can turn a `STOP` into a `SCALE`. A judge
that accepts everything scores 100% recall and is caught immediately by a 100%
false-accept rate and 0% reject recall.

Judge errors are counted separately and excluded from the confusion matrix, because
scoring a failed call as a rejection would make an outage look like strictness.

Scope: this measures agreement with hand-authored labels on constructed cases. It
is not accuracy against production ground truth, and constructed cases are easier
than real ones. Treat a strong score as a smoke test, not as permission to skip
human agreement checks on your own data.
