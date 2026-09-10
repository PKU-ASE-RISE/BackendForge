# Evaluation

## Input and submission

The agent receives `spec.md` and `openapi.yaml` in an empty workspace. It generates a Python service with a root-level `Dockerfile`, listening on `0.0.0.0:8000` and starting without seed data. The evaluator keeps tests and mock services outside the agent workspace.

## Scoring

| Oracle | Groups | Tests across 56 tasks |
|---|---|---:|
| Base | L1 correctness, L2 integration, L3 workflows | 7,250 |
| Final (default) | Base + R1, R2, R3 co-evolved tests | 7,839 |

Each group runs HTTP tests against a fresh service container. A task passes when every expected test passes; build errors, timeouts, missing tests and skipped tests count as an unsuccessful task. Overall results report both passed tasks and passed tests.

Task counts are in `benchmark/tasks.json`. Test paths and group counts are in `oracle/base_manifest.json` and `oracle/manifest.json`.

## External services

The evaluator starts the mocks and injects their URLs through these environment variables:

| Task | Service | Host port | Variable |
|---|---|---:|---|
| Cal.com | Calendar | 9998 | `CALENDAR_SERVICE_URL` |
| Medusa | Payment | 9999 | `PAYMENT_SERVICE_URL` |
| Novu | Delivery | 9998 | `DELIVERY_SERVICE_URL` |
| Saleor | Payment | 9999 | `PAYMENT_URL` |
| Spree | Payment | 9999 | `PAYMENT_GATEWAY_URL` |

Services must use the injected URL. These host ports must be free during evaluation, so `backendforge run` evaluates tasks sequentially.

## Development checks

```bash
python -m pytest tests -q
backendforge validate --collect
```
