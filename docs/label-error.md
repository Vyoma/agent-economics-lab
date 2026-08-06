# Agreement is not enough: how judge error reaches your decision

```bash
python3 -m agent_economics.label_error
```

If you label outcomes with an LLM judge and gate a deployment decision on cost per
acceptable outcome, the judge accuracy you need is not the accuracy the field quotes.

## The result

```
largest tolerable label error   e* = r * s / (1 + s)
```

`r` is the true acceptable rate. `s` is the relative slack: how far the metric
currently sits below its threshold, as a fraction of the metric.

At `r = 0.70` and `s = 0.10`, that is 6.36%, so the judge must agree **93.6%** of the
time. Practitioner guidance commonly treats 75 to 90% agreement as sufficient to act
on. Across the fifteen combinations printed by the command above, 85% suffices in
**one**: a workload that already succeeds 90% of the time and sits 25% clear of its
limit, which is the case where the decision was never in doubt.

## Why a classification threshold is the wrong threshold

The 85% guidance is inherited from classification, where an 85%-accurate labeller
induces roughly 15% error in whatever you compute next. A cost gate is not a
classification. It is a ratio, and the label is in the denominator:

```
u = total effective cost / number judged acceptable
```

Total cost does not depend on the labels. Model spend, human review, remediation and
incident loss were incurred whether or not the outcome is later called acceptable.
Only the denominator moves.

**Proposition 1.** For net label bias `D = false accepts - false rejects`,

```
u_hat / u = a / (a + D)
```

exactly, where `a` is the true acceptable count. Verified over 4,000 random
workloads to a maximum deviation of `4.4e-16`. Note what governs it: `D / a`, the
error relative to the *acceptable count*, not `D / n`, the error relative to the
workload.

**Proposition 2.** Under one-directional error at rate `epsilon`, the relative error
in `u` is `epsilon / (r - epsilon)`, so the amplification factor tends to `1 / r`.

| acceptable rate | 5% label error becomes |
|---:|---:|
| 90% | 5.9% |
| 50% | 11.1% |
| 20% | 33.3% |
| 10% | 100.0% |

Amplification is worst at low acceptable rates, which are exactly the workloads
where a scale-up decision is contested.

**Proposition 3, the one with a free remedy.** Difference-form metrics do not
amplify. For net value per attempt,

```
| N_hat - N |  <=  v_max * epsilon
```

with no dependence on `r`. So the label accuracy you need is a property of **the
metric you gate on**, not only of your judge. A team whose judge cannot reach the
accuracy that cost-per-acceptable-outcome demands can change the metric instead of
the judge, on the same labels and the same data, for a requirement several times
looser. That is a decision available this quarter.

**Proposition 4.** For a gate `u <= tau` with slack `s > 0`, a one-directional
false-reject rate flips it exactly when `epsilon > r*s/(1+s)`. Verified by exhaustive
integer search over `n` in {20, 50, 100, 200} and every `2 <= a < n`, agreeing with
the integer-quantised truth to within one task in every cell.

## What this does not claim

- **It does not measure any judge.** The result is conditional: *given* a judge that
  errs at `epsilon`, the decision behaves as derived. What rate a particular model
  attains on a particular workload is an empirical question this does not answer.
- **Real judge error is not uniformly random.** It correlates with task difficulty,
  which correlates with genuine failure. That correlation could raise or lower the
  flip rate and is not resolved here.
- **Proposition 4 is a worst case.** It assumes one-directional error, which is the
  behaviour of a systematically biased judge. Symmetric error is more forgiving.
- **The algebra is elementary.** Amplification through division is not a discovery.
  What is worth stating is that the field's sufficiency threshold is calibrated for
  the wrong functional form, and that Proposition 3 gives a cheaper fix than
  improving the judge.

## Practical use

1. Compute `e* = r*s/(1+s)` before choosing a judge. An agreement figure quoted
   without `r` and `s` says nothing about whether a gated decision is safe.
2. Report slack beside the verdict. A decision at 3% slack and one at 40% slack
   differ in robustness by an order of magnitude, and the verdict hides it.
3. Treat one-directional error as the operating case, because systematic bias is the
   common judge failure and it is the worst case here. Balanced-accuracy tuning is
   mis-specified for a gated decision, which is why
   [`make kimi-eval`](kimi-integration.md) reports a false-accept rate.

Related: [limitations.md](limitations.md) records that swapping the label source on
the support fixture moved the verdict from `ASSIST` to `STOP` and moved cost per
acceptable outcome 4.2x on identical spend.
