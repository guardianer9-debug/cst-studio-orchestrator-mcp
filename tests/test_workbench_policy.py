from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.operation_policy import check_paused, check_external_change, remember_file
from mcp_cst_studio.session_workspace import bind
from mcp_cst_studio.task_runner import start_task
from mcp_cst_studio.workbench_service import create_app


@pytest.mark.parametrize("name,args", [
    ("cst_run_task", {"task": "Tran1"}), ("cst_run_simulation_async", {}),
    ("cst_execute_vba", {"code": 'With Solver\n .Start\nEnd With'}),
    ("cst_schematic_create_transient_task", {"update": True}),
    ("cst_schematic_call", {"object_name": "SimulationTask", "method_name": "Update"}),
    ("cst_schematic_call", {"object_name": "Solver", "method_name": "StartSolver"}),
])
def test_paused_policy_prevents_implicit_execution(name, args):
    client = CSTClient(CSTConfig(simulation_paused=True))
    with pytest.raises(ValueError):
        check_paused(client, name, args)


def test_paused_runner_never_creates_job(tmp_path):
    client = CSTClient(CSTConfig(work_dir=str(tmp_path), simulation_paused=True))
    with pytest.raises(ValueError, match="paused"):
        start_task(client, "Tran1")
    assert not list(tmp_path.rglob("request.json"))


def test_external_save_cannot_be_overwritten(tmp_path):
    path = tmp_path / "test.cst"
    path.write_bytes(b"first")
    client = CSTClient(CSTConfig(work_dir=str(tmp_path), session_dir=str(tmp_path)))
    client._project_path = str(path)
    remember_file(client)
    path.write_bytes(b"manual edit")
    with pytest.raises(ValueError, match="changed outside"):
        check_external_change(client)
    with pytest.raises(ValueError, match="changed outside"):
        client.save_project()
    assert path.read_bytes() == b"manual edit"


def test_shared_backend_auth_and_metadata_do_not_launch_cst(tmp_path, monkeypatch):
    root = bind(tmp_path, "stable")
    monkeypatch.setenv("CST_WORK_DIR", str(root))
    monkeypatch.setenv("CST_SESSION_DIR", str(root))
    monkeypatch.setenv("CST_CONNECTION_MODE", "offline")
    monkeypatch.setenv("CST_SIMULATION_PAUSED", "1")
    with patch.object(CSTClient, "connect", side_effect=AssertionError("must not start CST")):
        with TestClient(create_app(root, "stable", "private-test-token")) as browser:
            assert browser.get("/health").status_code == 403
            headers = {"Authorization": "Bearer private-test-token"}
            assert browser.get("/health", headers={**headers, "Origin": "http://evil.invalid"}).status_code == 403
            assert browser.get("/health", headers=headers).json()["cst_connected"] is False
            response = browser.post("/action", headers=headers, json={"tool": "cst_refresh_view", "project": None})
            assert response.json()["isError"] is True
            assert not list(root.rglob("*.cst"))
            assert not (root / "运行").exists()


def test_result_refresh_records_unknown_association_and_never_solves(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from mcp_cst_studio.tools import cases
    root = bind(tmp_path, "result-session")
    project = root / "工程" / "test.cst"
    project.write_bytes(b"native saved project")
    client = SimpleNamespace(connected=True, project_path=str(project),
        _config=CSTConfig(work_dir=str(root), session_dir=str(root)),
        list_results=lambda domain: {"status": "ok", "items": ["1D Results\\S-Parameters\\S1,1"]} if domain == "3d" else {"status": "ok", "items": []},
        get_result=lambda path, domain: {"status": "ok", "project": str(project), "domain": domain, "tree_path": path, "run_id": 0, "data": {"x": [1], "real": [.5], "imag": [0]}})
    monkeypatch.setattr(cases, "publish_view", lambda *args, **kwargs: {"status": "published", "save_requested": kwargs["save"]})
    result = cases.refresh_results(client, "manual")
    assert result["curves_read"] == 1
    assert result["model_result_association"] == "unverified"
    assert result["view"]["save_requested"] is False
    assert not (root / "运行").exists()


@pytest.mark.asyncio
async def test_reload_refuses_active_solver_without_closing(tmp_path):
    import json
    from unittest.mock import MagicMock
    from mcp_cst_studio.tools.cases import handle
    client = CSTClient(CSTConfig(work_dir=str(tmp_path)))
    client._project = MagicMock()
    client.solver_status = lambda: {"running": True}
    result = json.loads((await handle("cst_reload_project", {"path": str(tmp_path / "x.cst")}, client))[0].text)
    assert result["status"] == "error"
    client._project.close.assert_not_called()
