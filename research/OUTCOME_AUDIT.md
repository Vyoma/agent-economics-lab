# What the outcome field says, and what its cross-check says

Every arm here is a real run: real API calls, real published spend,
`exit_status` "Submitted". They differ only in whether the outcome was
scored.

`naive` reads `info.resolved` alone, which is what a consumer computing
a leaderboard from this dataset would do. `confirmed` counts only the
trajectories whose `info.scores.resolved` is a number rather than the
string `"unknown"`.

| arm | n | naive resolved | naive rate | cross-check unknown | confirmed rate |
|---|---:|---:|---:|---:|---:|
| `claude-4.5-haiku-high` | 500 | 333 | 66.6% | 0 | 66.6% |
| `claude-4.5-opus-high` | 500 | 384 | 76.8% | 0 | 76.8% |
| `claude-opus-4.6` | 500 | 386 | 77.2% | 8 | 76.8% |
| `gpt-5.2-codex` | 500 | 364 | 72.8% | 0 | 72.8% |
| `gemini-3-pro` | 500 | 500 | 100.0% | 500 | **unestablished** |

**1 of 5 arms examined report a resolution rate that their own cross-check field does not confirm for a single task.**

`gemini-3-pro` reads **100%** from `info.resolved` across all 500 tasks, at $480.01 of published spend over 25,641 API calls. Its cross-check is `"unknown"` on all 500. There is no confirmed rate to report, which is different from a low one.

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

Five further arms exist upstream and are absent here because the
download was rate-limited. They are omitted rather than recorded as
empty, since a failed fetch is not evidence.

