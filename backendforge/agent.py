"""Run the BackendForge mini-SWE agent and export Dockerized submissions."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

from .inventory import REPO_ROOT, task, task_ids

ASSETS = Path(__file__).resolve().parent
RUNTIME_IMAGE = "backendforge-agent-runtime:2.2.8"


def run_task(task_id, output, args):
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_model import LitellmModel

    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    code = output / "code"
    code.mkdir()
    env = None
    agent = None
    result = {"task": task_id, "status": "ERROR", "exit_status": "NotStarted"}
    try:
        model_kwargs = {"temperature": args.temperature, "drop_params": True}
        if args.api_base:
            model_kwargs["api_base"] = args.api_base
        model_kwargs.update(args.model_kwargs)
        model = LitellmModel(model_name=args.model, model_kwargs=model_kwargs,
                             cost_tracking="ignore_errors")
        env = DockerEnvironment(
            image=args.runtime_image, cwd="/workspace", timeout=args.timeout,
            run_args=["--privileged", "--rm"], container_timeout="5h",
            pull_timeout=600, env={"PAGER": "cat", "DEBIAN_FRONTEND": "noninteractive"},
        )
        container = env.container_id
        subprocess.run(["docker", "exec", container, "mkdir", "-p", "/workspace/spec"],
                       check=True, timeout=30, capture_output=True)
        for name in ("spec.md", "openapi.yaml"):
            subprocess.run(["docker", "cp", str(REPO_ROOT / "tasks" / task_id / name),
                            f"{container}:/workspace/spec/{name}"],
                           check=True, timeout=60, capture_output=True)
        ready = env.execute({"command":
            "dockerd --host=unix:///var/run/docker.sock --storage-driver=vfs "
            "--data-root=/var/lib/docker --log-level=warn >/tmp/dockerd.log 2>&1 & "
            "for i in $(seq 1 30); do docker info >/dev/null 2>&1 && exit 0; sleep 1; done; "
            "cat /tmp/dockerd.log; exit 1"}, timeout=40)
        if ready["returncode"] != 0:
            raise RuntimeError("Task Docker daemon failed to start: " + ready["output"])
        agent = DefaultAgent(
            model, env, system_template=(ASSETS / "prompts/system.j2").read_text(),
            instance_template=(ASSETS / "prompts/instance.j2").read_text(),
            step_limit=args.step_limit, cost_limit=0.0,
            output_path=output / "trajectory.json",
        )
        info = agent.run(task=(REPO_ROOT / "tasks" / task_id / "spec.md").read_text())
        result["exit_status"] = info.get("exit_status", "unknown")
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if env is not None:
            try:
                subprocess.run(["docker", "cp", f"{env.container_id}:/workspace/.", str(code)],
                               check=True, timeout=60, capture_output=True)
            except Exception as exc:
                result["error"] = f"Code extraction failed: {exc}"
            finally:
                try:
                    env.cleanup()
                except Exception as exc:
                    result["error"] = f"Container cleanup failed: {exc}"
        if "error" not in result and (code / "Dockerfile").is_file():
            result["status"] = "DONE" if result["exit_status"] == "Submitted" else "INCOMPLETE"
        result.update(model=args.model, duration_seconds=round(time.monotonic() - started, 2))
        result.update(step_limit=args.step_limit, timeout=args.timeout, temperature=args.temperature,
                      steps=agent.n_calls if agent is not None else 0,
                      cost=agent.cost if agent is not None else 0.0)
        (output / "metadata.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def evaluate_results(results, args):
    """Evaluate serially: mock-backed tasks share fixed host ports."""
    from .evaluator import evaluate

    report = {"tasks": [], "tasks_passed": 0, "tasks_total": len(results),
              "passed": 0, "expected_items": 0, "oracle": args.oracle}
    for generated in results:
        name = generated["task"]
        item = task(name)
        expected = item["final_pytest_items" if args.oracle == "final" else "base_pytest_items"]
        row = {"task": name, "generation_status": generated["status"],
               "passed": 0, "expected_items": expected, "task_success": False}
        code = args.output / name / "code"
        if (code / "Dockerfile").is_file():
            try:
                row.update(evaluate(name, code, oracle=args.oracle,
                                    output_dir=args.output / name / "evaluation",
                                    port=args.port, startup_timeout=args.startup_timeout,
                                    pytest_timeout=args.pytest_timeout, build_timeout=args.build_timeout))
            except Exception as exc:
                row["error"] = str(exc)
        else:
            row["error"] = "No Dockerfile generated"
        report["tasks"].append(row)
        report["passed"] += row["passed"]
        report["expected_items"] += expected
        report["tasks_passed"] += int(row["task_success"])
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Evaluated {name}: {row['passed']}/{expected}; "
              f"{'PASS' if row['task_success'] else 'FAIL'}", flush=True)
    print(f"Tasks: {report['tasks_passed']}/{report['tasks_total']}; "
          f"tests: {report['passed']}/{report['expected_items']}")
    print(f"Results: {args.output / 'results.json'}")
    return report


def main(argv=None, *, evaluate_submissions=False):
    parser = argparse.ArgumentParser(
        prog="backendforge run" if evaluate_submissions else "backendforge-agent",
        description="Generate and evaluate BackendForge submissions." if evaluate_submissions else __doc__,
    )
    parser.add_argument("tasks", nargs="*", help="task IDs; omit to run all 56")
    parser.add_argument("--model", required=True, help="LiteLLM model name")
    parser.add_argument("--api-base", default="")
    parser.add_argument("--model-kwargs", default="{}", help="JSON model options, e.g. reasoning_effort")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--step-limit", type=positive, default=500)
    parser.add_argument("--timeout", type=positive, default=120, help="seconds per command")
    parser.add_argument("--concurrency", type=positive, default=1)
    parser.add_argument("--runtime-image", default=RUNTIME_IMAGE)
    parser.add_argument("--output", type=Path, default=None, required=not evaluate_submissions)
    if evaluate_submissions:
        parser.add_argument("--oracle", choices=("base", "final"), default="final")
        parser.add_argument("--port", type=positive, default=9400)
        parser.add_argument("--startup-timeout", type=positive, default=120)
        parser.add_argument("--pytest-timeout", type=positive, default=600)
        parser.add_argument("--build-timeout", type=positive, default=900)
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = Path("agent-results") / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    try:
        args.model_kwargs = json.loads(args.model_kwargs)
        if not isinstance(args.model_kwargs, dict):
            raise ValueError("--model-kwargs must be a JSON object")
        selected = args.tasks or task_ids()
        if len(selected) != len(set(selected)):
            raise ValueError("duplicate task IDs")
        for name in selected:
            task(name)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    try:
        import minisweagent  # noqa: F401
    except ImportError:
        parser.error("Install agent dependencies with pip install '.[agent]'")
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("--output must be an empty or new directory")
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        docker = subprocess.run(["docker", "info"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        parser.error(f"Docker is unavailable: {exc}")
    if docker.returncode:
        parser.error("Docker is not running; start Docker and retry")
    print(f"Output: {args.output}", flush=True)
    if subprocess.run(["docker", "image", "inspect", args.runtime_image], capture_output=True).returncode:
        subprocess.run(["docker", "build", "-t", args.runtime_image,
                        "-f", str(ASSETS / "Dockerfile.runtime"), str(ASSETS)], check=True, timeout=900)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending = {pool.submit(run_task, name, args.output / name, args): name for name in selected}
        completed = {}
        for future in as_completed(pending):
            row = future.result()
            completed[row["task"]] = row
            print(f"Generated {row['task']}: {row['status']}", flush=True)
            (args.output / "summary.json").write_text(json.dumps(list(completed.values()), indent=2) + "\n")
        results = [completed[name] for name in selected]
    (args.output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    for row in results:
        print(f"{row['task']}: {row['status']} ({row['exit_status']})")
    if evaluate_submissions:
        report = evaluate_results(results, args)
        raise SystemExit(0 if report["tasks_passed"] == report["tasks_total"] else 1)
    raise SystemExit(0 if all(row["status"] == "DONE" for row in results) else 1)


if __name__ == "__main__":
    main()
