"""Tests for result extraction tools — verify VBA generation in offline mode."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_get_s_parameters(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_s_parameters", {"port_in": 1, "port_out": 1}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    # Offline mode returns vba_script (not "vba") and status/tree info
    assert data.get("status") == "offline"
    vba = data.get("vba_script", "")
    assert "S1,1" in vba or "ASCIIExport" in vba or "SelectTreeItem" in vba


@pytest.mark.asyncio
async def test_get_farfield(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_farfield", {"frequency": 2.4}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    vba = data.get("vba_script", "")
    assert "FarfieldPlot" in vba


@pytest.mark.asyncio
async def test_add_field_monitor(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_add_field_monitor",
        {"name": "efield_2p4", "monitor_type": "Efield", "frequency": 2.4},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    # execute_vba returns {"status": "offline", "vba": code} — annotated with monitor metadata
    vba = data.get("vba", "")
    assert "Monitor" in vba
    assert "Efield" in vba or "FieldType" in vba


@pytest.mark.asyncio
async def test_get_impedance(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_impedance", {"port": 1}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    vba = data.get("vba_script", "")
    # VBA should reference Z-parameter result tree path
    assert "Z1,1" in vba or "Z-Parameters" in vba


@pytest.mark.asyncio
async def test_get_vswr(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_vswr", {"port": 1}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    # Result should contain VSWR tree path or formula comment
    vba = data.get("vba_script", "")
    assert "VSWR" in vba or "vswr" in vba.lower() or "s11_mag" in vba


@pytest.mark.asyncio
async def test_list_results(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_list_results", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data
    # Offline mode returns default result tree items
    assert "items" in data or "result_tree_structure" in data


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_nonexistent_result_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
