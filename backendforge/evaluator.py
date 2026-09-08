from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import requests

from .inventory import REPO_ROOT, base_manifest, coevolved_manifest, task


MOCK_ENV_BY_TASK = {
    "calcom": "CALENDAR_SERVICE_URL",
    "medusa": "PAYMENT_SERVICE_URL",
    "novu": "DELIVERY_SERVICE_URL",
    "saleor": "PAYMENT_URL",
    "spree": "PAYMENT_GATEWAY_URL",
}

PYTEST_MOCK_ENV_BY_TASK = {
    "calcom": lambda url: {"WEBHOOK_RECEIVER_URL": f"{url}/webhooks"},
    "novu": lambda url: {"DELIVERY_URL": url},
    "saleor": lambda url: {"PAYMENT_URL": url},
}


@dataclass(frozen=True)
class TestGroup:
    name: str
    files: tuple[Path, ...]
    expected_items: int


@dataclass
class GroupResult:
    group: str
    status: str
    passed: int
    failed: int
    skipped: int
    total: int
    expected_items: int
    all_pass: bool
    log: str
    report: str


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-")


def _test_groups(task_id: str, oracle: str) -> list[TestGroup]:
    groups: list[TestGroup] = []
    for level in ("L1", "L2", "L3"):
        rows = [row for row in base_manifest() if row["task"] == task_id and row["level"] == level]
        groups.append(
            TestGroup(
                name=level,
                files=tuple(REPO_ROOT / row["path"] for row in rows),
                expected_items=sum(int(row["pytest_items"]) for row in rows),
            )
        )
    if oracle == "final":
        manifest = coevolved_manifest()
        for round_name in ("R1", "R2", "R3"):
            rows = [row for row in manifest if row["task"] == task_id and row["round"] == round_name]
            if rows:
                groups.append(
                    TestGroup(
                        name=round_name,
                        files=tuple(REPO_ROOT / row["path"] for row in rows),
                        expected_items=sum(int(row["pytest_items"]) for row in rows),
                    )
                )
    return groups


def _run(args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _mock_port(app_path: Path) -> int:
    source = app_path.read_text(errors="replace")
    match = re.search(r"port\s*=\s*(\d{4,5})", source)
    if not match:
        raise RuntimeError(f"cannot determine mock-service port from {app_path}")
    return int(match.group(1))


def _start_mocks(
    task_id: str,
    output_dir: Path,
) -> tuple[list[subprocess.Popen[bytes]], list[str], dict[str, str]]:
    mock_root = REPO_ROOT / "tasks" / task_id / "mock_services"
    if not mock_root.is_dir():
        return [], [], {}

    processes: list[subprocess.Popen[bytes]] = []
    docker_env: list[str] = []
    pytest_env: dict[str, str] = {}
    try:
        for service_dir in sorted(path for path in mock_root.iterdir() if path.is_dir()):
            app_path = service_dir / "app.py"
            port = _mock_port(app_path)
            if _port_is_open(port):
                raise RuntimeError(f"mock-service port {port} is already in use")
            log_handle = (output_dir / f"mock-{service_dir.name}.log").open("wb")
            process = subprocess.Popen(
                [sys.executable, "app.py"],
                cwd=service_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            log_handle.close()
            processes.append(process)
            deadline = time.time() + 15
            while time.time() < deadline and not _port_is_open(port):
                if process.poll() is not None:
                    break
                time.sleep(0.25)
            if not _port_is_open(port):
                raise RuntimeError(f"mock service {service_dir.name} did not start on port {port}")
            env_name = MOCK_ENV_BY_TASK.get(task_id)
            if env_name is None:
                raise RuntimeError(f"missing candidate environment mapping for mock-backed task {task_id}")
            docker_url = f"http://host.docker.internal:{port}"
            docker_env.extend(["-e", f"{env_name}={docker_url}"])

            host_url = f"http://127.0.0.1:{port}"
            env_factory = PYTEST_MOCK_ENV_BY_TASK.get(task_id)
            if env_factory is not None:
                pytest_env.update(env_factory(host_url))
        return processes, docker_env, pytest_env
    except Exception:
        _stop_processes(processes)
        raise


def _stop_processes(processes: Iterable[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is not None:
            continue
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def _wait_ready(task_id: str, port: int, timeout: int) -> bool:
    deadline = time.time() + timeout
    paths = ("/api/health", "/") if task_id == "ntfy" else ("/",)
    while time.time() < deadline:
        for path in paths:
            try:
                response = requests.get(f"http://127.0.0.1:{port}{path}", timeout=2)
                if response.status_code in {200, 401, 404, 405, 422, 500}:
                    return True
            except requests.RequestException:
                pass
        time.sleep(2)
    return False


def _warmup(task_id: str, port: int) -> None:
    if task_id == "gotify":
        requests.get(
            f"http://127.0.0.1:{port}/current/user",
            headers={"X-Gotify-Key": "admin-user", "Content-Type": "application/json"},
            timeout=30,
        )


def _report_counts(report_path: Path) -> tuple[int, int, int, int]:
    if not report_path.exists():
        return 0, 0, 0, 0
    summary = json.loads(report_path.read_text()).get("summary", {})
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0) + int(summary.get("error", summary.get("errors", 0)) or 0)
    skipped = int(summary.get("skipped", 0) or 0)
    total = int(summary.get("total", summary.get("collected", passed + failed + skipped)) or 0)
    return passed, failed, skipped, total


def _pytest_environment(base_url: str, extra: dict[str, str]) -> dict[str, str]:
    env = {
        "BASE_URL": base_url,
        "API_KEY": "test-api-key-123",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    for name in ("HOME", "LANG", "LC_ALL", "PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR"):
        value = os.environ.get(name)
        if value:
            env[name] = value
    env.update(extra)
    return env


def _run_group(
    task_id: str,
    image: str,
    group: TestGroup,
    output_dir: Path,
    port: int,
    startup_timeout: int,
    pytest_timeout: int,
) -> GroupResult:
    group_dir = output_dir / group.name
    if group_dir.exists():
        shutil.rmtree(group_dir)
    group_dir.mkdir(parents=True, exist_ok=True)
    log_path = group_dir / "pytest.log"
    report_path = group_dir / "report.json"
    container = _safe_name(f"backendforge-{task_id}-{group.name}-{uuid.uuid4().hex[:8]}")
    mocks: list[subprocess.Popen[bytes]] = []
    status = "OK"
    try:
        mocks, mock_env, pytest_mock_env = _start_mocks(task_id, group_dir)
        run = _run(
            [
                "docker", "run", "-d", "--name", container,
                "-p", f"127.0.0.1:{port}:8000", "--add-host=host.docker.internal:host-gateway",
                "--security-opt", "no-new-privileges", "--pids-limit", "512",
                *mock_env, image,
            ],
            timeout=60,
        )
        if run.returncode != 0:
            status = "DOCKER_RUN_FAIL"
            log_path.write_text(run.stdout)
        elif not _wait_ready(task_id, port, startup_timeout):
            status = "NOT_READY"
            logs = _run(["docker", "logs", container], timeout=30)
            log_path.write_text(logs.stdout)
        else:
            _warmup(task_id, port)
            env = _pytest_environment(f"http://127.0.0.1:{port}", pytest_mock_env)
            try:
                result = subprocess.run(
                    [
                        sys.executable, "-m", "pytest", *(str(path) for path in group.files),
                        "-p", "pytest_jsonreport.plugin",
                        "-v", "--tb=long", "--json-report", f"--json-report-file={report_path}",
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=pytest_timeout,
                    check=False,
                )
                log_path.write_text(result.stdout)
                if result.returncode != 0:
                    status = "PYTEST_FAILED"
            except subprocess.TimeoutExpired as exc:
                status = "PYTEST_TIMEOUT"
                output = exc.stdout or ""
                log_path.write_text(output if isinstance(output, str) else output.decode(errors="replace"))
    finally:
        _run(["docker", "rm", "-f", "-v", container], timeout=30)
        _stop_processes(mocks)

    try:
        passed, failed, skipped, total = _report_counts(report_path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        passed, failed, skipped, total = 0, 0, 0, 0
        if status == "OK":
            status = "INVALID_REPORT"
    if status == "OK" and not report_path.is_file():
        status = "NO_REPORT"
    if status == "OK" and total != group.expected_items:
        status = "COUNT_MISMATCH"
    all_pass = status == "OK" and passed == group.expected_items and failed == 0 and skipped == 0
    return GroupResult(
        group=group.name,
        status=status,
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=total,
        expected_items=group.expected_items,
        all_pass=all_pass,
        log=str(log_path.relative_to(output_dir)),
        report=str(report_path.relative_to(output_dir)),
    )


def evaluate(
    task_id: str,
    submission: Path,
    *,
    oracle: str = "final",
    output_dir: Path,
    port: int = 9400,
    startup_timeout: int = 120,
    pytest_timeout: int = 600,
    build_timeout: int = 900,
    keep_image: bool = False,
) -> dict:
    task(task_id)
    submission = submission.resolve()
    if not (submission / "Dockerfile").is_file():
        raise FileNotFoundError(f"submission must contain a Dockerfile: {submission}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    image = _safe_name(f"backendforge-{task_id}-{uuid.uuid4().hex[:10]}")
    build_log = output_dir / "build.log"
    try:
        try:
            build = _run(["docker", "build", "-t", image, str(submission)], timeout=build_timeout)
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            build_log.write_text(output if isinstance(output, str) else output.decode(errors="replace"))
            raise RuntimeError(f"Docker build timed out; see {build_log}") from exc
        build_log.write_text(build.stdout)
        if build.returncode != 0:
            raise RuntimeError(f"Docker build failed; see {build_log}")

        results = [
            _run_group(task_id, image, group, output_dir, port, startup_timeout, pytest_timeout)
            for group in _test_groups(task_id, oracle)
        ]
        payload = {
            "task": task_id,
            "oracle": oracle,
            "submission": str(submission),
            "groups": [asdict(result) for result in results],
            "passed": sum(result.passed for result in results),
            "total": sum(result.total for result in results),
            "expected_items": sum(result.expected_items for result in results),
            "task_success": all(result.all_pass for result in results),
        }
        (output_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
        return payload
    finally:
        if not keep_image:
            _run(["docker", "image", "rm", "-f", image], timeout=60)
