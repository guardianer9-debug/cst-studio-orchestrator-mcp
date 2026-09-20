"""Offline guards around the real-process task runner; no CST is launched."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio import task_runner as runner


def test_reused_pid_is_never_terminated():
    process = MagicMock(pid=123)
    process.create_time.return_value = 20
    with patch("psutil.Process", return_value=process):
        with pytest.raises(RuntimeError, match="reused"):
            runner.terminate_owned({"owned_pid": 123, "process_created": 10})
    process.kill.assert_not_called()
    process.children.assert_not_called()


def test_termination_targets_only_owned_tree():
    owner, child = MagicMock(pid=123), MagicMock(pid=124)
    owner.create_time.return_value = 10
    owner.children.return_value = [child]
    with patch("psutil.Process", return_value=owner) as lookup, patch("psutil.wait_procs", return_value=([], [])):
        result = runner.terminate_owned({"owned_pid": 123, "process_created": 10})
    lookup.assert_called_once_with(123)
    owner.kill.assert_called_once()
    child.kill.assert_called_once()
    assert result["state"] == "terminated"
    assert result["termination_mode"] == "owned_process_tree"


def test_unknown_job_blocks_new_operations(tmp_path):
    client = CSTClient(CSTConfig())
    client._task_job = tmp_path
    runner.write(tmp_path / "status.json", {"state": "unknown", "job_id": "case"})
    result = runner.task_status(client)
    assert result["status"] == "unknown"
    assert result["running"] is None
    assert client.disconnect()["status"] == "job_running"


def test_cancel_is_only_a_request(tmp_path):
    client = CSTClient(CSTConfig())
    client._task_job = tmp_path
    runner.write(tmp_path / "status.json", {"state": "executing", "job_id": "case"})
    assert runner.cancel_task(client)["status"] == "requested"
    assert runner.task_status(client)["running"] is True
    assert (tmp_path / "cancel.json").exists()


def test_finished_job_does_not_get_cancelled(tmp_path):
    client = CSTClient(CSTConfig())
    client._task_job = tmp_path
    runner.write(tmp_path / "status.json", {"state": "succeeded", "job_id": "case"})
    assert runner.cancel_task(client)["state"] == "succeeded"
    assert not (tmp_path / "cancel.json").exists()


def test_task_never_runs_in_borrowed_environment():
    client = CSTClient(CSTConfig())
    client._project = MagicMock()
    with pytest.raises(ValueError, match="owned"):
        runner.start_task(client, "Tran1")


def test_job_limits_and_frozen_executor(tmp_path):
    client = CSTClient(CSTConfig(work_dir=str(tmp_path)))
    client._owns_environment = True
    client._project = MagicMock()
    client._project_path = str(tmp_path / "model.cst")
    client._de = MagicMock()
    client._de.pid.return_value = 123
    client.save_project = MagicMock(return_value={"status": "saved"})
    process = MagicMock()
    process.create_time.return_value = 10
    with patch("psutil.Process", return_value=process), patch.object(runner.subprocess, "Popen") as spawn:
        with pytest.raises(ValueError, match="limits"):
            runner.start_task(client, "Tran1", 3601)
        result = runner.start_task(client, "Tran1", 60, 2)
    assert result["state"] == "queued"
    job = client._task_job
    assert (job / "runner.py").is_file()
    assert json.loads((job / "request.json").read_text())["max_rss_gb"] == 2
    assert spawn.call_args.args[0][1] == str(job / "runner.py")


@pytest.mark.asyncio
async def test_registry_rejects_mutation_while_task_owns_project(tmp_path):
    from mcp_cst_studio.tools import ToolRegistry
    from mcp_cst_studio.tools.cases import TOOLS, handle
    client = CSTClient(CSTConfig())
    client._task_job = tmp_path
    runner.write(tmp_path / "status.json", {"state": "unknown", "job_id": "case"})
    registry = ToolRegistry()
    registry.add_module(TOOLS, handle, client)
    result = await registry._handlers["cst_readback"]("cst_readback", {})
    assert json.loads(result[0].text)["status"] == "error"


def test_schematic_delete_requires_explicit_target():
    client = CSTClient(CSTConfig(connected=True))
    client._project = MagicMock()
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True):
        result = client.schematic_call(object_name="Block", method_name="Delete")
        assert result["status"] == "error"
        client._project.schematic.Block.Delete.assert_not_called()
        result = client.schematic_call(object_name="Block", method_name="Delete", target_name="GND3")
        assert result["status"] == "executed"
        client._project.schematic.Block.Name.assert_called_once_with("GND3")


def test_raw_task_update_is_rejected():
    client = CSTClient(CSTConfig(connected=True))
    client._project = MagicMock()
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True):
        result = client.schematic_call(object_name="SimulationTask", method_name="Update")
    assert result["status"] == "error"
    client._project.schematic.SimulationTask.Update.assert_not_called()
