# BackendForge

Generate and evaluate deployable backend services from natural-language specifications and OpenAPI contracts. Includes **56 tasks and 7,839 black-box HTTP tests**.

## Install

Requires Python 3.11+ and a running Docker engine with privileged Linux container support.

```bash
git clone https://github.com/PKU-ASE-RISE/BackendForge.git
cd BackendForge
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[agent]'
```

## Run

Set your provider's API key, then run one task:

```bash
export OPENAI_API_KEY="YOUR_API_KEY"
backendforge run actualbudget --model openai/YOUR_MODEL
```

For an OpenAI-compatible endpoint, add `--api-base https://YOUR_ENDPOINT/v1`.

Run all 56 tasks with 10 concurrent generation workers:

```bash
backendforge run --model openai/YOUR_MODEL --concurrency 10 --output agent-results/run1
```

The command builds the agent runtime image automatically, generates services, evaluates them, and summarizes scores. Generation uses mini-SWE-agent 2.2.8; evaluation runs sequentially because external mock services share fixed ports. Only `spec.md` and `openapi.yaml` are exposed to the agent.

Defaults: 500 model calls, 120 seconds per shell command, temperature 0, and the final oracle. Set provider-specific options with `--model-kwargs '{"reasoning_effort":"max"}'`. See `backendforge run --help` for all options.

## Results

Each run writes to a new directory under `agent-results/`, or the empty/new directory supplied with `--output`:

- `results.json`: aggregate scores and per-task evaluation results.
- `<task>/code/`: generated service and Dockerfile.
- `<task>/trajectory.json` and `metadata.json`: generation trace and status.
- `<task>/evaluation/`: build log, per-group test reports, and scores.

A task passes only when every applicable test passes. Failed builds and missing submissions remain in the score denominator. Exit status is 0 when all tasks pass, and nonzero otherwise.

To evaluate existing code or use another agent:

```bash
backendforge list
backendforge prepare actualbudget workspaces/actualbudget
# Have your agent implement the service using only workspaces/actualbudget/spec/.
backendforge evaluate actualbudget workspaces/actualbudget
```

[Evaluation protocol](docs/EVALUATION.md) · [Paper](https://arxiv.org/abs/2607.11042) · [Citation](CITATION.cff)

Apache-2.0. Tasks are rewritten from public applications; upstream names are retained for attribution. See [NOTICE](NOTICE).
