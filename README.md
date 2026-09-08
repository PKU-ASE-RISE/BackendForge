# BackendForge

BackendForge is a benchmark for agentic end-to-end generation of deployable backend services. Each task gives an agent a visible natural-language specification and OpenAPI contract. The submitted service must build in Docker, listen on port 8000, and satisfy a black-box HTTP oracle.

This repository is the artifact release for **BackendForge: Benchmarking Agentic End-to-End Code Generation with Backend Services** (Findings of EMNLP 2026; [arXiv:2607.11042](https://arxiv.org/abs/2607.11042)).

## Release Scope

| Artifact | Count | Location |
|---|---:|---|
| Rewritten backend tasks | 56 | `tasks/` |
| Base oracle | 7,250 pytest items | `oracle/base/` |
| Human-adjudicated co-evolved oracle | 573 files / 589 pytest items | `oracle/coevolved/` |
| Final oracle | 7,839 pytest items | `oracle/` |
| Deterministic external mock services | 5 tasks | `tasks/*/mock_services/` |

The paper-facing co-evolution rounds contain 239, 187, and 163 pytest items for R1, R2, and R3, respectively.

## Install

Python 3.11+ and Docker are required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
backendforge validate
backendforge list
```

Use `pip install -e .` when developing the release itself.

Use `backendforge validate --collect` to recollect every released pytest item and verify the reported totals.

## Run One Task

Prepare an agent-visible workspace:

```bash
backendforge prepare actualbudget workspaces/actualbudget
```

Give the agent only `workspaces/actualbudget/spec/`. Its submission must place a `Dockerfile` at the workspace root and run the API on port 8000.

Evaluate the submission:

```bash
backendforge evaluate actualbudget workspaces/actualbudget --oracle final
```

The evaluator builds the image once and starts a fresh container for each applicable L1, L2, L3, R1, R2, and R3 group. Task success requires every applicable item to pass. See [docs/EVALUATION.md](docs/EVALUATION.md) for the complete protocol.

## Artifact Boundary

`tasks/<task>/spec.md` and `tasks/<task>/openapi.yaml` are the visible contract. Mock services are evaluator-managed external dependencies; their source is released for reproducibility.

`oracle/` is public for reproducible evaluation, but it must not be mounted into the agent workspace. Publishing the oracle also creates contamination risk for future model evaluation; report the release version, model access date, and whether the model may have trained on this repository.

## Oracle Audit

Two auditors independently review all 624 automatically admitted files against the visible contracts. Their initial file-level decisions agree on 554/624 files (88.8%); all 70 disagreements are adjudicated. The final oracle excludes 51 files and retains 573 files containing 589 pytest items.

## Repository Map

- `benchmark/`: task inventory and oracle counts.
- `tasks/`: visible contracts and evaluator-managed mock services.
- `oracle/`: base and retained co-evolved scored tests.
- `backendforge/`: workspace preparation and local evaluation CLI.
- `docs/`: evaluation protocol, data card, and task provenance.
- `scripts/validate_release.py`: release integrity checks.

## Citation

Use the metadata in [CITATION.cff](CITATION.cff). Source applications and task provenance are listed in [docs/TASK_SOURCES.md](docs/TASK_SOURCES.md).

## License

The release is provided under the Apache License 2.0. BackendForge tasks are rewritten from publicly available applications; upstream project names and links are provided for attribution. Upstream trademarks and project licenses remain with their respective owners.
