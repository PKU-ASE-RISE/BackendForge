from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(__file__).resolve().parents[1]
INSTALLED_ROOT = Path(sys.prefix) / "share" / "backendforge"
REPO_ROOT = SOURCE_ROOT if (SOURCE_ROOT / "benchmark" / "tasks.json").is_file() else INSTALLED_ROOT

if not (REPO_ROOT / "benchmark" / "tasks.json").is_file():
    raise RuntimeError(
        "BackendForge benchmark data is missing. Install from the complete source release "
        "or reinstall the wheel with its data files."
    )


def load_json(relative_path: str) -> Any:
    return json.loads((REPO_ROOT / relative_path).read_text())


def tasks() -> list[dict[str, Any]]:
    return load_json("benchmark/tasks.json")


def task_ids() -> list[str]:
    return [task["id"] for task in tasks()]


def task(task_id: str) -> dict[str, Any]:
    for item in tasks():
        if item["id"] == task_id:
            return item
    valid = ", ".join(task_ids())
    raise ValueError(f"unknown task {task_id!r}; choose one of: {valid}")


def base_manifest() -> list[dict[str, Any]]:
    return load_json("oracle/base_manifest.json")


def coevolved_manifest() -> list[dict[str, Any]]:
    return load_json("oracle/manifest.json")


def oracle_summary() -> dict[str, Any]:
    return load_json("benchmark/oracle_summary.json")
