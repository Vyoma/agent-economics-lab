# Kimi Judge + Analyst — 3-command demo

This example shows the full Kimi-powered workflow for agent-economics-lab:

1. **Judge** — Kimi scores each agent output against the rubric and writes `outcomes.csv`
2. **Evaluate** — the framework runs 6 economic gates and issues a SCALE/ASSIST/STOP decision
3. **Analyse** — Kimi reads the decision and gives quantified, actionable recommendations

## Prerequisites

```bash
export MOONSHOT_API_KEY=<your key from https://platform.kimi.ai>
```

## Step 1: Label outcomes with Kimi

```bash
agent-economics judge \
  --task-results examples/kimi-judge/task_results.csv \
  --rubric       examples/kimi-judge/rubric.json \
  --out          /tmp/kimi_outcomes.csv
```

Kimi scores 8 agent outputs against the support rubric (accuracy 50%, policy 30%, tone 20%).
Each task above 0.70 overall is labelled acceptable. An audit sidecar is written to
`/tmp/kimi_outcomes.audit.json` with per-criterion scores and rationale for every task.

## Step 2: Run the economics evaluation

```bash
agent-economics evaluate \
  --traces    examples/support_trace.csv \
  --outcomes  /tmp/kimi_outcomes.csv \
  --rates     examples/rates.json \
  --baseline  examples/baseline.json \
  --policy    examples/policy.json \
  --format    json \
  --output    /tmp/case.json
cat /tmp/case.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['decision'])"
```

The framework runs 6 gates: acceptable-rate, unit-economics, tail-cost, net-value,
counterfactual, and runtime-caps. Output is a JSON assurance case.

## Step 3: Get Kimi's recommendations

```bash
agent-economics analyse \
  --case     /tmp/case.json \
  --policy   examples/policy.json \
  --baseline examples/baseline.json
```

Kimi reads the decision and metric gaps and returns:
- **ASSIST** → top-3 fixes ranked by threshold distance, with quantified expected impact
- **STOP** → viability math — what change in acceptable_rate or cost would flip the decision
- **SCALE** → sustainability watch-outs for metrics within 20% of their thresholds

## Rubric schema

```json
{
  "rubric_id": "support-v1",
  "task_type": "description of what the agent does",
  "acceptable_threshold": 0.70,
  "business_value_usd_if_acceptable": 8.00,
  "human_minutes_if_not_acceptable": 8.0,
  "remediation_cost_usd_if_not_acceptable": 0.75,
  "incident_loss_usd_if_not_acceptable": 0.0,
  "criteria": [
    {"id": "accuracy", "question": "Was the answer correct?",        "weight": 0.50},
    {"id": "policy",   "question": "Did it comply with policy?",     "weight": 0.30},
    {"id": "tone",     "question": "Was the tone professional?",     "weight": 0.20}
  ]
}
```

Criterion weights must sum to exactly 1.0.

## task_results.csv format

| Column    | Required | Notes                                    |
|-----------|----------|------------------------------------------|
| task_id   | yes      | must match task IDs in traces CSV        |
| output    | yes      | the agent's final response text          |
| context   | no       | brief description of the task for Kimi   |

## Audit trail

Every `judge` run writes a `.audit.json` sidecar alongside `outcomes.csv`:

```json
[
  {
    "task_id": "t-001",
    "model_id": "kimi-k3",
    "rubric_id": "support-v1",
    "overall_score": 0.88,
    "criterion_scores": {"accuracy": 0.9, "policy": 0.8, "tone": 1.0},
    "acceptable": true,
    "rationale": "Accurate, policy-compliant, and professionally toned.",
    "label_source": "kimi-judge@support-v1"
  }
]
```

This audit trail lets you review every labelling decision and detect systematic
biases before using the outcomes for economic evaluation.
