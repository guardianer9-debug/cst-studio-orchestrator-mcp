"""Tests for material tools."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_create_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_material",
        {
            "name": "MySubstrate",
            "epsilon": 4.4,
            "mu": 1.0,
            "tan_d_e": 0.02,
            "conductivity": 0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"MySubstrate"' in vba
    assert ".Epsilon" in vba or ".Colour" in vba


@pytest.mark.asyncio
async def test_list_materials(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle("cst_list_materials", {"category": "metals"}, client)
    data = json.loads(result[0].text)
    assert "materials" in data or "metals" in data or isinstance(data, list) or "Copper" in str(data)


@pytest.mark.asyncio
async def test_create_lossy_metal(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_lossy_metal",
        {"name": "LossyCopper", "conductivity": 5.8e7},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert "Lossy metal" in vba or "lossy" in vba.lower()
