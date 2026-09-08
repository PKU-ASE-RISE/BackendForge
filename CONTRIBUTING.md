# Contributing

BackendForge is a versioned benchmark artifact. Changes to contracts or scored oracle files can alter task semantics and reported results, so submit them separately from tooling and documentation changes.

Before opening a pull request, run:

```bash
pip install -e .
backendforge validate --collect
```

For oracle changes, include the affected task, the exact supporting clause in `spec.md` or `openapi.yaml`, the collected item-count change, and updated manifests where applicable. Do not commit credentials, private execution logs, model trajectories, generated service submissions, local databases, or evaluation outputs.

Use an issue to report ambiguous or conflicting contract behavior. A proposed test must rely only on the visible task contract and exercise the service through HTTP.
