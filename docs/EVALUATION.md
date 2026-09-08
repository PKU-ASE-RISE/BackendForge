# Evaluation Protocol

## Agent Input

For task `<task>`, the evaluated agent receives only:

- `tasks/<task>/spec.md`
- `tasks/<task>/openapi.yaml`
- a writable empty workspace and standard coding tools

The agent must generate a Python backend service with a root-level `Dockerfile`. The image must start without seed data and listen on `0.0.0.0:8000`.

Do not expose `oracle/` or evaluator traces to the evaluated agent.

## Scoring

The base oracle contains three test groups:

- L1: endpoint and local correctness checks
- L2: cross-endpoint integration checks
- L3: multi-step workflow checks

The final oracle adds the retained R1, R2, and R3 co-evolved tests. Each group runs against a fresh container. Requests reach the candidate only through its HTTP interface, and the tests do not inspect implementation source or storage.

Task success is an all-pass metric. A task succeeds only if every item in every selected group passes. Build failure, startup failure, timeout, collection mismatch, failed assertion, error, or skipped item prevents task success.

## Mock Services

Five tasks use deterministic external mock services:

| Task | Service | Port | Candidate environment variable |
|---|---|---:|---|
| Cal.com | calendar | 9998 | `CALENDAR_SERVICE_URL` |
| Medusa | payment | 9999 | `PAYMENT_SERVICE_URL` |
| Novu | delivery | 9998 | `DELIVERY_SERVICE_URL` |
| Saleor | payment | 9999 | `PAYMENT_URL` |
| Spree | payment | 9999 | `PAYMENT_GATEWAY_URL` |

The local evaluator starts and stops these services for each test group and injects only the task-specific variable shown above into the candidate container. Implementations must read that variable; the `localhost` value in each specification is only a local-development fallback. The evaluator refuses to replace another process already using a required mock port.

## Execution Safety

Submissions are untrusted code. Evaluation builds and runs the submitted Docker image and gives mock-backed tasks access to an evaluator-managed host service. Run evaluations only on a disposable or otherwise isolated machine; the local runner is a reproducibility tool, not a security boundary.

## Commands

```bash
# Visible workspace only
backendforge prepare TASK WORKSPACE

# Base oracle: 7,250 items over the complete benchmark
backendforge evaluate TASK WORKSPACE --oracle base

# Final oracle: 7,839 items over the complete benchmark
backendforge evaluate TASK WORKSPACE --oracle final
```

Per-group logs, pytest JSON reports, and an aggregate `summary.json` are written under `evaluation-results/` unless `--output` is supplied.
