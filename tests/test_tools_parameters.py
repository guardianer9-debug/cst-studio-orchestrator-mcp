"""Tests for parametric design tools — verify VBA generation in offline mode."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_set_parameter(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_set_parameter",
        {"name": "width", "value": "10", "description": "Patch width"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "StoreParameter" in vba or "MakeSureParameterExists" in vba
    assert "width" in vba


@pytest.mark.asyncio
async def test_get_parameter(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_get_parameter",
        {"name": "width"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "RestoreParameter" in vba or "width" in vba


@pytest.mark.asyncio
async def test_list_parameters(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle("cst_list_parameters", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    # In offline mode execute_vba returns {"status": "offline", "vba": code}
    assert "status" in data


@pytest.mark.asyncio
async def test_delete_parameter(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_delete_parameter",
        {"name": "width"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "DeleteParameter" in vba
    assert "width" in vba


@pytest.mark.asyncio
async def test_parameter_sweep(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_parameter_sweep",
        {"parameter": "width", "start": 8, "stop": 12, "steps": 5},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "ParameterSweep" in vba
    assert "width" in vba


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle("cst_nonexistent_parameter_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
