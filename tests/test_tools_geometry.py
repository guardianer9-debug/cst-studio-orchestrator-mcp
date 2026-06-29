"""Tests for geometry tools — verify VBA generation in offline mode."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_create_brick(client: CSTClient):
    from mcp_cst_studio.tools.geometry import handle

    result = await handle(
        "cst_create_brick",
        {
            "component": "Antenna",
            "name": "substrate",
            "material": "FR-4",
            "x_min": -20,
            "x_max": 20,
            "y_min": -20,
            "y_max": 20,
            "z_min": 0,
            "z_max": 1.6,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Brick" in vba
    assert '"substrate"' in vba
    assert '"Antenna"' in vba
    assert '"FR-4"' in vba
    assert ".Xrange" in vba
    assert ".Create" in vba


@pytest.mark.asyncio
async def test_create_cylinder(client: CSTClient):
    from mcp_cst_studio.tools.geometry import handle

    result = await handle(
        "cst_create_cylinder",
        {
            "component": "Feed",
            "name": "probe",
            "material": "PEC",
            "axis": "z",
            "outer_radius": 0.5,
            "inner_radius": 0,
            "center_x": 0,
            "center_y": 0,
            "range_min": 0,
            "range_max": 1.6,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Cylinder" in vba
    assert '"probe"' in vba


@pytest.mark.asyncio
async def test_create_sphere(client: CSTClient):
    from mcp_cst_studio.tools.geometry import handle

    result = await handle(
        "cst_create_sphere",
        {
            "component": "Radome",
            "name": "dome",
            "material": "Teflon",
            "center_x": 0,
            "center_y": 0,
            "center_z": 10,
            "radius": 25,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Sphere" in vba
    assert '"dome"' in vba


@pytest.mark.asyncio
async def test_invalid_name_rejected(client: CSTClient):
    from mcp_cst_studio.tools.geometry import handle

    result = await handle(
        "cst_create_brick",
        {
            "component": "Antenna",
            "name": "bad@name!",
            "x_min": 0,
            "x_max": 10,
            "y_min": 0,
            "y_max": 10,
            "z_min": 0,
            "z_max": 1,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert "error" in data or "error" in data.get("status", "")
