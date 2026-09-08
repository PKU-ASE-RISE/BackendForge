#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TASKS = 56
EXPECTED_OPERATIONS = 2345
EXPECTED_SCHEMAS = 1356
EXPECTED_BASE = 7250
EXPECTED_COEVOLVED = 589
EXPECTED_FINAL = 7839
EXPECTED_ROUNDS = {"R1": 239, "R2": 187, "R3": 163}
FORBIDDEN_TEXT = (
    "/".join(("", "mnt", "cephfs")),
    "/".join(("", "data", "backendforge")),
    ".".join(("ichat", "woa", "com")),
    "".join(("luban", "llm")),
    "".join(("REFERENCE_", "EVIDENCE:")),
    "".join(("EXPECTED_REFERENCE_", "BEHAVIOR:")),
    "".join(("reference_", "pass:")),
    "".join(("stability_", "pass:")),
)
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def load_json(path: Path):
    return json.loads(path.read_text())


def collect_count(paths: list[Path]) -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-q",
            *map(str, paths),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout[-4000:])
    return sum("::" in line and not line.startswith("<") for line in result.stdout.splitlines())


def validate(run_collection: bool) -> None:
    tasks = load_json(ROOT / "benchmark" / "tasks.json")
    base = load_json(ROOT / "oracle" / "base_manifest.json")
    evolved = load_json(ROOT / "oracle" / "manifest.json")
    summary = load_json(ROOT / "benchmark" / "oracle_summary.json")

    task_ids = [row["id"] for row in tasks]
    assert len(task_ids) == EXPECTED_TASKS
    assert len(set(task_ids)) == EXPECTED_TASKS
    assert "krayin" not in task_ids
    assert len(base) == 168
    assert len(evolved) == 573
    assert sum(row["pytest_items"] for row in base) == EXPECTED_BASE
    assert sum(row["pytest_items"] for row in evolved) == EXPECTED_COEVOLVED
    assert summary["final_oracle"]["pytest_items"] == EXPECTED_FINAL
    assert Counter({name: sum(row["pytest_items"] for row in evolved if row["round"] == name) for name in EXPECTED_ROUNDS}) == Counter(EXPECTED_ROUNDS)

    operations = 0
    schemas = 0
    mock_tasks = 0
    for item in tasks:
        task_id = item["id"]
        for name in ("spec.md", "openapi.yaml"):
            assert (ROOT / "tasks" / task_id / name).is_file()
        document = yaml.safe_load((ROOT / "tasks" / task_id / "openapi.yaml").read_text())
        operations += sum(method.lower() in HTTP_METHODS for value in document.get("paths", {}).values() for method in value)
        schemas += len(document.get("components", {}).get("schemas", {}))
        mock_tasks += (ROOT / "tasks" / task_id / "mock_services").is_dir()
    assert operations == EXPECTED_OPERATIONS
    assert schemas == EXPECTED_SCHEMAS
    assert mock_tasks == 5

    for row in [*base, *evolved]:
        assert row["task"] in task_ids
        assert (ROOT / row["path"]).is_file()
        assert not any("sha" in key.lower() for key in row)
    for row in evolved:
        assert len(row["spec_traces"]) == len(set(row["spec_traces"]))

    for path in ROOT.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")

    text_suffixes = {".md", ".json", ".csv", ".yaml", ".yml", ".toml", ".py", ".cff"}
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in text_suffixes:
            text = path.read_text(errors="replace")
            for token in FORBIDDEN_TEXT:
                assert token not in text, f"internal text {token!r} in {path.relative_to(ROOT)}"

    if run_collection:
        base_total = 0
        evolved_total = 0
        for task_id in task_ids:
            base_total += collect_count([ROOT / row["path"] for row in base if row["task"] == task_id])
            evolved_total += collect_count([ROOT / row["path"] for row in evolved if row["task"] == task_id])
        assert base_total == EXPECTED_BASE
        assert evolved_total == EXPECTED_COEVOLVED

    print(f"OK: {EXPECTED_TASKS} tasks, {EXPECTED_BASE} base items, {EXPECTED_COEVOLVED} co-evolved items, {EXPECTED_FINAL} final items")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    validate(args.collect)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
