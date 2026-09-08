# Benchmark Data Card

## Intended Use

BackendForge measures whether an agentic coding system can construct a deployable Python backend from a visible contract and satisfy that contract under black-box execution. It supports research on end-to-end code generation, agent scaffolds, executable specifications, and test-oracle design.

The benchmark is not intended to certify production security, reliability, legal compliance, or compatibility with the upstream applications that inspired the tasks.

## Composition

- 56 rewritten backend service tasks across six coarse domains.
- 2,345 OpenAPI operations and 1,356 schemas.
- 7,250 base pytest items.
- 589 retained co-evolved pytest items in 573 files.
- 7,839 final-oracle items in total.
- 51 candidates excluded during human adjudication and not distributed as scored tests.

Task-level composition fields are in `benchmark/tasks.json`.

## Contract Grounding

Every co-evolved candidate is reviewed against only the visible `spec.md` and `openapi.yaml`. Two auditors independently label all 624 automatically admitted files. For the binary release decision, `SUPPORTED` and `AMBIGUOUS` are retained initially while `UNSUPPORTED` is marked for exclusion. Initial agreement is 554/624 files (88.8%); 70 disagreements are adjudicated individually. The final release excludes 51 files and has no unresolved case.

## Limitations

The oracle is bounded by the written contracts and cannot exhaust all valid backend behavior. Co-evolution may emphasize behaviors exposed by the construction agents. Public release of hidden tests enables reproducible evaluation but also increases contamination risk. Benchmark runs should therefore report the exact release version, harness, inference configuration, access date, and artifact-visibility policy.

Task names refer to upstream open-source applications, but the contracts are rewritten benchmark tasks rather than drop-in compatibility suites. A high score does not imply equivalence to the upstream product.
