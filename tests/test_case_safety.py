"""Mock/offline regressions; these are not real CST or Agent acceptance."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.tools.cases import prepare_reference


@pytest.fixture
def live_mock(tmp_path):
    client = CSTClient(CSTConfig(connected=True, work_dir=str(tmp_path)))
    client._project = MagicMock()
    client._project_path = str(tmp_path / "model.cst")
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True):
        yield client


def test_default_connection_does_not_attach_to_user_session():
    sdk = MagicMock()
    sdk.interface.DesignEnvironment.return_value.pid.return_value = 123
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True), patch(
        "mcp_cst_studio.cst_client.cst", sdk, create=True
    ):
        client = CSTClient(CSTConfig())
        assert client.connect()["owned"] is True
        sdk.interface.DesignEnvironment.connect.assert_not_called()
        sdk.interface.running_design_environments.assert_not_called()
        client.disconnect()
        sdk.interface.DesignEnvironment.return_value.close.assert_called_once()


def test_attach_requires_pid_and_does_not_select_or_close_project():
    sdk = MagicMock()
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True), patch(
        "mcp_cst_studio.cst_client.cst", sdk, create=True
    ):
        client = CSTClient(CSTConfig(connection_mode="attach"))
        assert client.connect()["status"] == "error"
        sdk.interface.DesignEnvironment.connect.assert_not_called()
        client._config.pid = 456
        assert client.connect()["owned"] is False
        assert not client.has_project
        client.disconnect()
        sdk.interface.DesignEnvironment.connect.return_value.close.assert_not_called()


def test_unknown_solver_state_is_not_stopped(live_mock):
    live_mock._project.model3d.is_solver_running.side_effect = TimeoutError("busy")
    assert live_mock.solver_status()["running"] is None
    assert live_mock.solver_command("start")["status"] == "unknown"
    live_mock._project.model3d.start_solver.assert_not_called()
    with pytest.raises(TimeoutError):
        live_mock.is_solver_running()


def test_stop_is_request_until_observed(live_mock):
    model = live_mock._project.model3d
    model.is_solver_running.return_value = True
    model.get_solver_run_info.return_value = {"state": "RUNNING"}
    result = live_mock.solver_command("stop")
    assert result["status"] == "requested"
    assert result["observed"]["running"] is True
    model.abort_solver.assert_called_once_with(timeout=30)


def test_running_job_cannot_start_twice(live_mock):
    live_mock._project.model3d.is_solver_running.return_value = True
    assert live_mock.solver_command("start")["status"] == "error"
    live_mock._project.model3d.start_solver.assert_not_called()


@pytest.mark.asyncio
async def test_parameter_query_returns_live_expression_without_macro(live_mock):
    from mcp_cst_studio.tools.parameters import handle
    model = live_mock._project.model3d
    model.GetNumberOfParameters.return_value = 1
    model.GetParameterName.return_value = "length"
    model.GetParameterSValue.return_value = "2*40"
    model.GetParameterNValue.return_value = 80.0
    value = json.loads((await handle("cst_get_parameter", {"name": "length"}, live_mock))[0].text)
    assert value["parameters"] == [{"name": "length", "expression": "2*40", "value": 80.0}]
    model.add_to_history.assert_not_called()
    assert live_mock.read_parameters("missing")["status"] == "error"


def test_project_outside_workspace_is_rejected(live_mock, tmp_path):
    live_mock._de = MagicMock()
    path = str(tmp_path.parent / "original.cst")
    assert live_mock.open_project(path)["status"] == "error"
    assert live_mock.save_project(path)["status"] == "error"
    live_mock._de.open_project.assert_not_called()
    live_mock._project.save.assert_not_called()


def test_reference_attempts_do_not_overwrite_or_touch_source(tmp_path):
    source = tmp_path / "reference.cst"
    source.write_bytes(b"original")
    client = CSTClient(CSTConfig(work_dir=str(tmp_path / "runs")))
    receipt = prepare_reference(client, str(source), "try1")
    assert receipt["source_unchanged"]
    assert Path(receipt["project"]).read_bytes() == b"original"
    with pytest.raises(FileExistsError):
        prepare_reference(client, str(source), "try1")
    with pytest.raises(ValueError):
        prepare_reference(client, str(source), "../escape")
    assert source.read_bytes() == b"original"


def test_mesh_tools_present_in_registry():
    from mcp.server import Server
    from mcp_cst_studio.tools import register_all_tools, _registry
    register_all_tools(Server("test"), CSTClient(CSTConfig()))
    names = {t.name for t in _registry._tools}
    assert {"cst_set_mesh_properties", "cst_set_local_mesh_properties", "cst_readback", "cst_prepare_reference"} <= names
