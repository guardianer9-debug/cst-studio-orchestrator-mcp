"""Tests for transform tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_transform_translate(client: CSTClient):
    from mcp_cst_studio.tools.transforms import handle

    result = await handle(
        "cst_transform_translate",
        {"solid": "component1:box", "dx": 10, "dy": 0, "dz": 0},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Transform" in vba
    assert "TranslateX" in vba


@pytest.mark.asyncio
async def test_transform_rotate(client: CSTClient):
    from mcp_cst_studio.tools.transforms import handle

    result = await handle(
        "cst_transform_rotate",
        {
            "solid": "component1:box",
            "angle": 90,
            "axis": "z",
            "center_x": 0,
            "center_y": 0,
            "center_z": 0,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Angle" in vba
    # Rotating around z axis sets PlaneNormal to z
    assert "PlaneNormal" in vba


@pytest.mark.asyncio
async def test_transform_mirror(client: CSTClient):
    from mcp_cst_studio.tools.transforms import handle

    result = await handle(
        "cst_transform_mirror",
        {"solid": "component1:box", "plane": "xy"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "PlaneNormal" in vba


@pytest.mark.asyncio
async def test_transform_scale(client: CSTClient):
    from mcp_cst_studio.tools.transforms import handle

    result = await handle(
        "cst_transform_scale",
        {"solid": "component1:box", "scale_x": 2, "scale_y": 2, "scale_z": 1},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "ScaleX" in vba


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.transforms import handle

    result = await handle(
        "cst_transform_nonexistent",
        {"solid": "component1:box"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error" or "error" in data
