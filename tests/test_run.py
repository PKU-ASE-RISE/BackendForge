"""End-to-end orchestration checks without paid API calls or Docker."""
import json
from argparse import Namespace
from unittest.mock import patch

from backendforge.agent import evaluate_results


def test_failed_build_does_not_stop_batch_or_shrink_denominator(tmp_path):
    args = Namespace(output=tmp_path, oracle="final", port=9400,
                     startup_timeout=120, pytest_timeout=600, build_timeout=900)
    tasks = ["actualbudget", "bookstack", "calcom"]
    for name in tasks[:2]:
        code = tmp_path / name / "code"
        code.mkdir(parents=True)
        (code / "Dockerfile").write_text("FROM scratch\n")
    from backendforge.inventory import task
    count = task("bookstack")["final_pytest_items"]
    with patch("backendforge.evaluator.evaluate", side_effect=[
        RuntimeError("build failed"),
        {"passed": count, "task_success": True, "expected_items": count},
    ]) as evaluator:
        report = evaluate_results([{"task": name, "status": "ERROR"} for name in tasks], args)
    assert evaluator.call_count == 2
    assert report["tasks_passed"] == 1
    assert report["tasks_total"] == 3
    assert report["passed"] == count
    assert report["expected_items"] == sum(task(name)["final_pytest_items"] for name in tasks)
    assert report["tasks"][0]["error"] == "build failed"
    assert report["tasks"][2]["error"] == "No Dockerfile generated"
    assert json.loads((tmp_path / "results.json").read_text()) == report


def test_run_command_dispatches_all_options():
    from backendforge.cli import main
    argv = ["backendforge", "run", "bookstack", "--model", "openai/test", "--concurrency", "10"]
    with patch("sys.argv", argv), patch("backendforge.agent.main") as run:
        main()
    run.assert_called_once_with(argv[2:], evaluate_submissions=True)


def test_full_command_generates_evaluates_and_returns_failure(tmp_path):
    import pytest
    from subprocess import CompletedProcess
    from backendforge.agent import main

    pytest.importorskip("minisweagent")
    output = tmp_path / "run"

    def generate(name, destination, args):
        code = destination / "code"
        code.mkdir(parents=True)
        (code / "Dockerfile").write_text("FROM scratch\n")
        return {"task": name, "status": "DONE", "exit_status": "Submitted"}

    with patch("backendforge.agent.subprocess.run", return_value=CompletedProcess([], 0)), \
         patch("backendforge.agent.run_task", side_effect=generate), \
         patch("backendforge.evaluator.evaluate", return_value={
             "passed": 1, "task_success": False,
         }) as evaluator, pytest.raises(SystemExit) as exit_info:
        main(["bookstack", "--model", "openai/test", "--output", str(output)],
             evaluate_submissions=True)
    assert exit_info.value.code == 1
    evaluator.assert_called_once()
    assert (output / "summary.json").is_file()
    report = json.loads((output / "results.json").read_text())
    assert report["tasks_total"] == 1
    assert report["tasks_passed"] == 0
    assert report["passed"] == 1
