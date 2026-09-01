# What the outcome field says, and what its cross-check says

The dataset is an independent upload under an individual account, not
a release by any of the vendors whose models the arms are named for. An
arm name identifies a set of runs in this dataset. It is not a number any
vendor published, and nothing below is a measurement of a model.

Every arm here records real API calls and real published spend, both
of which are in the frozen evidence and checkable. They differ in
whether the outcome was confirmed.

`naive` reads `info.resolved` alone, which is what a consumer computing
a leaderboard from this dataset would do. `confirmed` counts only the
trajectories whose `info.scores.resolved` is a number rather than the
string `"unknown"`.

| arm | n | naive resolved | naive rate | cross-check unknown | confirmed rate |
|---|---:|---:|---:|---:|---:|
| `claude-4.5-haiku-high` | 500 | 333 | 66.6% | 0 | 66.6% |
| `claude-4.5-opus-high` | 500 | 384 | 76.8% | 0 | 76.8% |
| `claude-opus-4.6` | 500 | 386 | 77.2% | 8 | 76.8% |
| `gemini-3-flash-high` | 500 | 379 | 75.8% | 0 | 75.8% |
| `glm-5-high` | 500 | 364 | 72.8% | 0 | 72.8% |
| `gpt-5-mini` | 500 | 281 | 56.2% | 0 | 56.2% |
| `gpt-5.2-codex` | 500 | 364 | 72.8% | 0 | 72.8% |
| `gpt-5.2-high` | 500 | 364 | 72.8% | 0 | 72.8% |
| `minimax-m2.5-high` | 500 | 379 | 75.8% | 0 | 75.8% |
| `gemini-3-pro` | 500 | 500 | 100.0% | 500 | **unestablished** |

**1 of 10 arms examined report a resolution rate that their own cross-check field does not confirm for a single task.**

`gemini-3-pro` reads **100%** from `info.resolved` across all 500 tasks, at $480.01 of published spend over 25,641 API calls. Its cross-check is `"unknown"` on all 500. There is no confirmed rate to report, which is different from a low one.

Harder than any plausibility argument: 9 of those 500 runs record a single API call and no spend, and `info.resolved` is `true` for every one of them. Whatever those runs were, they did not resolve a SWE-bench issue.

## The same transcripts, published twice, scored differently

One arm pair carries byte-identical transcripts. Same messages,
same cost to sixteen decimal places, same API call count; the
files differ only in `info.docent.model_label` and the run id.

That accident is useful. It scored the same input twice, which is
a direct reading of how repeatable this outcome label is.

`gpt-5.2-codex` and `gpt-5.2-high`: **500 of 500 transcripts identical**, and `info.resolved` disagrees on **44** of them. Agreement with itself on identical input: **91.2%**.

Examples where the same transcript was scored both ways: `django__django-11138`, `django__django-11149`, `django__django-11265`.

Across the 9 arms with a confirmed rate, the spread is 20.6 points (56.2% to 76.8%). The label disagrees with itself by 8.8. Gaps of a few points between models in this dataset cannot be distinguished from the instrument disagreeing with itself; the largest gaps can.

What causes it is not established here. Flaky tests, a non-deterministic evaluation environment, and a labelling pipeline that scored the two copies at different times would all produce this, and nothing in the frozen evidence separates them.

A fourth possibility undercuts the reading above rather than explaining it: these may have been two genuinely different runs whose transcript files were duplicated during packaging while their labels were joined in separately. That would make this a packaging artifact and not a reading of the label at all, and the figure would not be a test-retest figure.

Two things in the evidence argue against it. The 44 disagreements split exactly 22/22 in each direction, and both arms resolve exactly 364 of 500. Two different configurations would not be expected to produce either. Neither settles it.

What is established is narrower and enough: whatever produced these labels, it did not produce the same label twice for the same transcript.

## What this is and is not

It is a factual reading of two fields in a public MIT-licensed dataset,
reproducible from the frozen content-free evidence in
`examples/public-swebench/outcome_audit.json`, where every row carries
the SHA-256 of the complete upstream trajectory it came from.

It is not a claim that the dataset is wrong. The dataset ships the
cross-check that makes this visible and marks the unscored arm honestly.
A consumer reading one field and publishing a rate is the failure.

It is not a claim about any model's real capability. An unscored arm is
unscored; nothing here establishes whether it would have done well.

All 10 arms published upstream at the pinned revision are included. Nothing was dropped for a failed fetch.

