# Historical Paper Results

These are the paper's persisted evaluation results for GPT-5.5 (xhigh) and
Claude Opus 4.7 (max), adjusted by removing 51 unsupported co-evolved items.
No rejected candidates are added. The oracle contains 7,250 base items and
589 retained co-evolved items, for 7,839 items across 56 tasks.

**These are not new evaluations of the release-hardened test suite.** Subsequent
release fixes, including the replacement of an Invoice Ninja no-op test, are
not reflected in these historical scores. An equal item count does not imply
identical test behavior. This directory does not contain generated services,
reference implementations, model trajectories, credentials, or raw logs.

| Model | Base task all-pass | Final task all-pass | Final item pass rate |
|---|---:|---:|---:|
| GPT-5.5 (xhigh) | 31/56 (55.36%) | 16/56 (28.57%) | 7,621/7,839 (97.22%) |
| Claude Opus 4.7 (max) | 33/56 (58.93%) | 10/56 (17.86%) | 7,609/7,839 (97.07%) |

## Files and Definitions

- `gpt55_tasks.csv`: all 56 GPT-5.5 task results.
- `claude-opus-4-7_tasks.csv`: all 56 Claude Opus task results.
- `summary.json`: aggregate scores and final passing-task lists.

Each CSV reports passed and total item counts for Base and each co-evolution
round, plus Base and Final task-level all-pass outcomes. `r1`, `r2`, and `r3`
are individual rounds, not cumulative scores; their totals are 239, 187, and
163 items. They correspond to the historical analysis keys `r0`, `r1`, and
`r2`. A round with no items for a task is recorded as 0/0, not as a measured
round pass rate. Final combines Base and all three rounds. Boolean all-pass
fields are `True` or `False`; item pass rates and task success rates are
different metrics.

## Provenance

Counts are exported from the paper analysis
`final_pool_v3_unsupported51_eval_v1/main_table.json`. Every final task outcome
is independently cross-checked against
`reviewer_robustness_unsupported51_v1/task_success_rates.csv`. Export validation
checks the 56-task denominator, per-round totals, final item totals, and both
models' aggregate pass counts. The original internal analysis artifacts are
not required to use these public CSV and JSON files.
