"""Tests for mesh control tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_set_mesh_type(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_set_mesh_type",
        {"mesh_type": "Hexahedral"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Mesh" in vba
    assert data.get("status") == "offline"
    assert data.get("mesh_type") == "Hexahedral"


@pytest.mark.asyncio
async def test_set_mesh_density(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_set_mesh_density",
        {
            "cells_per_wavelength": 10,
            "min_cells": 5,
            "ratio_limit": 0.1,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    # VBABuilder("Mesh") sets LinesPerWavelength / MinimumStepNumber / RatioLimit
    assert "Mesh" in vba
    assert data.get("status") == "offline"
    assert data.get("cells_per_wavelength") == 10


@pytest.mark.asyncio
async def test_add_mesh_refinement(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_add_mesh_refinement",
        {
            "component": "Antenna",
            "solid": "patch",
            "refinement_factor": 2.0,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    # VBABuilder uses "MeshAdaption3D"
    assert "MeshAdaption3D" in vba or "Mesh" in vba
    assert data.get("status") == "offline"
    assert data.get("component") == "Antenna"
    assert data.get("solid") == "patch"


@pytest.mark.asyncio
async def test_get_mesh_info(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle("cst_get_mesh_info", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data
    # Offline mode returns descriptive info
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle("cst_nonexistent_mesh_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
