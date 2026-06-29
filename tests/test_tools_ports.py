"""Tests for port tools -- verify VBA generation and Coordinates parameter."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_waveguide_port_default_coordinates_free(client: CSTClient):
    """Waveguide port should default to Coordinates='Free'."""
    from mcp_cst_studio.tools.ports import handle

    result = await handle(
        "cst_add_waveguide_port",
        {
            "port_number": 1,
            "orientation": "ymin",
            "x_min": -5,
            "x_max": 5,
            "y_min": -10,
            "y_max": -10,
            "z_min": -3,
            "z_max": 3,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert '.Coordinates "Free"' in vba
    assert '.Orientation "ymin"' in vba
    assert ".Create" in vba


@pytest.mark.asyncio
async def test_waveguide_port_explicit_coordinates(client: CSTClient):
    """Waveguide port should accept explicit Coordinates modes."""
    from mcp_cst_studio.tools.ports import handle

    for coord_mode in ("Free", "Full"):
        result = await handle(
            "cst_add_waveguide_port",
            {
                "port_number": 1,
                "orientation": "zmin",
                "x_min": -10,
                "x_max": 10,
                "y_min": -5,
                "y_max": 5,
                "z_min": 0,
                "z_max": 0,
                "coordinates": coord_mode,
            },
            client,
        )
        data = json.loads(result[0].text)
        vba = data.get("vba", "")
        assert f'.Coordinates "{coord_mode}"' in vba


@pytest.mark.asyncio
async def test_waveguide_port_invalid_coordinates(client: CSTClient):
    """Waveguide port should reject invalid Coordinates values."""
    from mcp_cst_studio.tools.ports import handle

    result = await handle(
        "cst_add_waveguide_port",
        {
            "port_number": 1,
            "orientation": "ymin",
            "x_min": -5,
            "x_max": 5,
            "y_min": -10,
            "y_max": -10,
            "z_min": -3,
            "z_max": 3,
            "coordinates": "Invalid",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "coordinates" in data["message"].lower() or "Coordinates" in data["message"]


@pytest.mark.asyncio
async def test_waveguide_port_all_orientations(client: CSTClient):
    """Waveguide port should accept all valid orientations."""
    from mcp_cst_studio.tools.ports import handle

    for orient in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
        result = await handle(
            "cst_add_waveguide_port",
            {
                "port_number": 1,
                "orientation": orient,
                "x_min": -5,
                "x_max": 5,
                "y_min": -10,
                "y_max": 10,
                "z_min": -3,
                "z_max": 3,
            },
            client,
        )
        data = json.loads(result[0].text)
        vba = data.get("vba", "")
        assert f'.Orientation "{orient}"' in vba


@pytest.mark.asyncio
async def test_discrete_port_basic(client: CSTClient):
    """Discrete port should generate valid VBA."""
    from mcp_cst_studio.tools.ports import handle

    result = await handle(
        "cst_add_discrete_port",
        {
            "port_number": 1,
            "x1": 0,
            "y1": 0,
            "z1": 0,
            "x2": 0,
            "y2": 0,
            "z2": 1.6,
            "impedance": 50,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "DiscretePort" in vba
    assert ".Create" in vba


@pytest.mark.asyncio
async def test_add_plane_wave(client: CSTClient):
    from mcp_cst_studio.tools.ports import handle

    result = await handle(
        "cst_add_plane_wave",
        {"theta": 0, "phi": 0, "polarization": "linear"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "PlaneWave" in vba


@pytest.mark.asyncio
async def test_list_ports(client: CSTClient):
    from mcp_cst_studio.tools.ports import handle

    result = await handle("cst_list_ports", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data


@pytest.mark.asyncio
async def test_delete_port(client: CSTClient):
    from mcp_cst_studio.tools.ports import handle

    result = await handle("cst_delete_port", {"port_number": 1}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Port" in vba
    assert "Delete" in vba


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.ports import handle

    result = await handle("cst_nonexistent_port_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
