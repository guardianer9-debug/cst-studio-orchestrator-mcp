"""Tests for boundary condition tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_set_boundary(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_boundary",
        {
            "x_min": "open",
            "x_max": "open",
            "y_min": "open",
            "y_max": "open",
            "z_min": "electric",
            "z_max": "open",
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Boundary" in vba
    assert data.get("status") == "offline"
    # Verify boundary values are echoed back
    assert data.get("boundaries", {}).get("z_min") == "electric"


@pytest.mark.asyncio
async def test_set_background(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_background",
        {"material": "Normal"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Background" in vba
    assert data.get("status") == "offline"
    assert data.get("background", {}).get("material") == "Normal"


@pytest.mark.asyncio
async def test_set_symmetry(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_symmetry",
        {"x_plane": "none", "y_plane": "none", "z_plane": "none"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Boundary" in vba
    assert "Symmetry" in vba or "symmetry" in vba.lower()
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_set_frequency_range(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_frequency_range",
        {"f_min": 1.0, "f_max": 5.0},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    # VBA uses VBABuilder("Solver") with FrequencyRange
    assert "Solver" in vba or "FrequencyRange" in vba or "1.0" in vba
    assert data.get("status") == "offline"
    freq = data.get("frequency_range", {})
    assert freq.get("f_min_ghz") == 1.0
    assert freq.get("f_max_ghz") == 5.0


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle("cst_nonexistent_boundary_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
