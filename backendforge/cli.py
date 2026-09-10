from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .evaluator import evaluate
from .inventory import REPO_ROOT, oracle_summary, task, tasks


def _empty_destination(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"destination is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _prepare(task_id: str, destination: Path) -> None:
    item = task(task_id)
    _empty_destination(destination)
    spec_dir = destination / "spec"
    spec_dir.mkdir()
    shutil.copy2(REPO_ROOT / item["contract"]["spec"], spec_dir / "spec.md")
    shutil.copy2(REPO_ROOT / item["contract"]["openapi"], spec_dir / "openapi.yaml")
    print(destination.resolve())


def _list_tasks() -> None:
    print(f"{'ID':<18} {'DOMAIN':<34} {'OPS':>4} {'BASE':>5} {'EVOLVED':>7} {'FINAL':>5}")
    for item in tasks():
        print(
            f"{item['id']:<18} {item['domain']:<34} {item['api_operations']:>4} "
            f"{item['base_pytest_items']:>5} {item['coevolved_pytest_items']:>7} {item['final_pytest_items']:>5}"
        )


def _evaluate(args: argparse.Namespace) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or Path("evaluation-results") / f"{args.task}-{stamp}"
    payload = evaluate(
        args.task,
        args.submission,
        oracle=args.oracle,
        output_dir=output.resolve(),
        port=args.port,
        startup_timeout=args.startup_timeout,
        pytest_timeout=args.pytest_timeout,
        build_timeout=args.build_timeout,
        keep_image=args.keep_image,
    )
    print(json.dumps(payload, indent=2))
    if not payload["task_success"]:
        raise SystemExit(1)


def _validate(collect: bool) -> None:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "validate_release.py")]
    if collect:
        command.append("--collect")
    raise SystemExit(subprocess.run(command, cwd=REPO_ROOT, check=False).returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backendforge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="generate, evaluate, and summarize (run --help for options)")
    subparsers.add_parser("list", help="list benchmark tasks")

    show = subparsers.add_parser("summary", help="print benchmark oracle counts")
    show.add_argument("--json", action="store_true")

    prepare = subparsers.add_parser("prepare", help="create an agent-visible task workspace")
    prepare.add_argument("task")
    prepare.add_argument("destination", type=Path)

    run = subparsers.add_parser("evaluate", help="evaluate one Dockerized submission")
    run.add_argument("task")
    run.add_argument("submission", type=Path)
    run.add_argument("--oracle", choices=("base", "final"), default="final")
    run.add_argument("--output", type=Path)
    run.add_argument("--port", type=int, default=9400)
    run.add_argument("--startup-timeout", type=int, default=120)
    run.add_argument("--pytest-timeout", type=int, default=600)
    run.add_argument("--build-timeout", type=int, default=900)
    run.add_argument("--keep-image", action="store_true")

    validate = subparsers.add_parser("validate", help="validate release structure and counts")
    validate.add_argument("--collect", action="store_true", help="also recollect every pytest item")
    return parser


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        from .agent import main as run_agent
        run_agent(sys.argv[2:], evaluate_submissions=True)
        return
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "list":
        _list_tasks()
    elif args.command == "summary":
        summary = oracle_summary()
        print(json.dumps(summary, indent=2) if args.json else "56 tasks; 7,250 base + 589 co-evolved = 7,839 final items")
    elif args.command == "prepare":
        _prepare(args.task, args.destination)
    elif args.command == "evaluate":
        _evaluate(args)
    elif args.command == "validate":
        _validate(args.collect)
    else:
        parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
