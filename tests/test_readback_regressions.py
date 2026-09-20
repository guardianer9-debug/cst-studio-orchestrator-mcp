"""Regressions discovered by real Pi/CST case runs; offline mocks only."""
import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient


@pytest.fixture
def client():
    value = CSTClient(CSTConfig(connected=True))
    value._project = MagicMock()
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True):
        yield value


@pytest.mark.asyncio
async def test_mesh_query_never_updates_or_writes_history(client):
    from mcp_cst_studio.tools.mesh import handle
    client._project.model3d.Mesh.GetNumberOfMeshCells.return_value = 0
    client._project.model3d.Mesh.GetMeshType.return_value = "PBA"
    result = json.loads((await handle("cst_get_mesh_info", {}, client))[0].text)
    assert result == {"status": "ok", "cells": 0, "mesh_type": "PBA", "mesh_present": False, "generated_by_this_call": False}
    client._project.model3d.add_to_history.assert_not_called()
    client._project.model3d.Mesh.Update.assert_not_called()


def test_port_number_and_impedance_come_from_live_data(client):
    model = client._project.model3d
    model.Solver.GetNumberOfPorts.return_value = 1
    model.get_tree_items.return_value = ["Ports", "Ports\\port7 (feed)"]
    model.DiscretePort.GetProperties.return_value = (True, "SParameter", 73.0, 1.0, 1.0, 0.0, 0.0, True)
    result = client.list_ports()
    assert result["ports"][0]["number"] == 7
    assert result["ports"][0]["impedance"] == 73.0
    model.add_to_history.assert_not_called()


def test_interactive_and_postprocessing_history_is_rejected(client):
    for code in ['MsgBox "ports"', 'With FarfieldPlot\n.Reset\nEnd With', 'ASCIIExport.Execute']:
        assert client.execute_vba(code)["status"] == "error"
    client._project.model3d.add_to_history.assert_not_called()


def test_delete_status_cannot_be_overwritten_by_dialog_status(client):
    client.dismiss_dialogs = MagicMock(return_value={"status": "unsupported"})
    assert client.delete_results()["status"] == "ok"
    client.dismiss_dialogs.assert_not_called()
    client._project.model3d.DeleteResults.side_effect = RuntimeError("blocked")
    assert client.delete_results()["status"] == "error"


@pytest.mark.asyncio
async def test_s_parameter_db_is_computed_from_complex_values(client):
    from mcp_cst_studio.tools.results import handle
    client.get_result = MagicMock(return_value={"status": "ok", "data": {"x": [1, 2], "real": [.5, 0], "imag": [0, 1]}})
    result = json.loads((await handle("cst_get_s_parameters", {"format": "db"}, client))[0].text)
    assert result["data"]["y"] == pytest.approx([-6.020599913279624, 0])
    assert result["data"]["real"] == [.5, 0]
