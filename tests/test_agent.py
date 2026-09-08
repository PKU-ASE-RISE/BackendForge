"""Runner regression tests; no model API calls or Docker daemon required."""

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("minisweagent")
from backendforge.agent import run_task


@pytest.mark.parametrize("exit_status,expected", [("Submitted", "DONE"), ("LimitsExceeded", "INCOMPLETE")])
def test_exports_submission_and_cleans_container(tmp_path, exit_status, expected):
    args = Namespace(model="openai/test", model_kwargs={}, api_base="", temperature=0,
                     timeout=120, step_limit=500, runtime_image="test-runtime")
    env = MagicMock()
    env.container_id = "test-container"
    env.execute.return_value = {"returncode": 0, "output": ""}
    agent = MagicMock(n_calls=2, cost=0.0)
    agent.run.return_value = {"exit_status": exit_status}
    copied = []

    def docker_run(command, **kwargs):
        if command[1] == "cp":
            copied.append(command[2])
            if command[2] == "test-container:/workspace/.":
                (tmp_path / "task/code/Dockerfile").write_text("FROM scratch\n")

    with patch("minisweagent.models.litellm_model.LitellmModel"), \
         patch("minisweagent.environments.docker.DockerEnvironment", return_value=env), \
         patch("minisweagent.agents.default.DefaultAgent", return_value=agent), \
         patch("backendforge.agent.subprocess.run", side_effect=docker_run):
        result = run_task("actualbudget", tmp_path / "task", args)
    assert result["status"] == expected
    assert [path.rsplit("/", 1)[-1] for path in copied[:2]] == ["spec.md", "openapi.yaml"]
    assert len(copied) == 3
    env.cleanup.assert_called_once()


def test_model_error_still_exports_partial_code_and_cleans(tmp_path):
    args = Namespace(model="openai/test", model_kwargs={}, api_base="", temperature=0,
                     timeout=120, step_limit=500, runtime_image="test-runtime")
    env = MagicMock()
    env.container_id = "test-container"
    env.execute.return_value = {"returncode": 0, "output": ""}
    agent = MagicMock(n_calls=1, cost=0.0)
    agent.run.side_effect = RuntimeError("model unavailable")
    with patch("minisweagent.models.litellm_model.LitellmModel"), \
         patch("minisweagent.environments.docker.DockerEnvironment", return_value=env), \
         patch("minisweagent.agents.default.DefaultAgent", return_value=agent), \
         patch("backendforge.agent.subprocess.run") as docker:
        result = run_task("actualbudget", tmp_path / "task", args)
    assert result["status"] == "ERROR"
    assert result["error"] == "model unavailable"
    assert docker.call_args.args[0][2] == "test-container:/workspace/."
    env.cleanup.assert_called_once()
