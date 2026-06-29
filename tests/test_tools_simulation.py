"""Tests for simulation control tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_run_simulation_default(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_run_simulation", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solver.Start" in vba
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_run_simulation_time_domain(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle(
        "cst_run_simulation",
        {"solver_type": "Time Domain"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver_type") == "Time Domain"


@pytest.mark.asyncio
async def test_run_simulation_async(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_run_simulation_async", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("mode") == "async"
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_get_simulation_status(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_get_simulation_status", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_pause_simulation(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_pause_simulation", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solver" in vba
    assert "Pause" in vba
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_stop_simulation(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_stop_simulation", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solver" in vba
    assert "Stop" in vba
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_invalid_solver_type_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle(
        "cst_run_simulation",
        {"solver_type": "InvalidSolver"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error" or "error" in data


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_nonexistent_simulation_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error" or "error" in data
