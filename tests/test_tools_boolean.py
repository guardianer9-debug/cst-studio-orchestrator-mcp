"""Tests for boolean operation tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_boolean_add(client: CSTClient):
    from mcp_cst_studio.tools.boolean import handle

    result = await handle(
        "cst_boolean_add",
        {"solid1": "component1:solid1", "solid2": "component1:solid2"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solid.Add" in vba


@pytest.mark.asyncio
async def test_boolean_subtract(client: CSTClient):
    from mcp_cst_studio.tools.boolean import handle

    result = await handle(
        "cst_boolean_subtract",
        {"solid1": "component1:solid1", "solid2": "component1:solid2"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solid.Subtract" in vba


@pytest.mark.asyncio
async def test_boolean_intersect(client: CSTClient):
    from mcp_cst_studio.tools.boolean import handle

    result = await handle(
        "cst_boolean_intersect",
        {"solid1": "component1:solid1", "solid2": "component1:solid2"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solid.Intersect" in vba


@pytest.mark.asyncio
async def test_boolean_insert(client: CSTClient):
    from mcp_cst_studio.tools.boolean import handle

    result = await handle(
        "cst_boolean_insert",
        {"solid1": "component1:solid1", "solid2": "component1:solid2"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solid.Insert" in vba


@pytest.mark.asyncio
async def test_invalid_solid_name_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.boolean import handle

    result = await handle(
        "cst_boolean_add",
        {"solid1": "bad@name", "solid2": "component1:solid2"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error" or "error" in str(data).lower()


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.boolean import handle

    result = await handle(
        "cst_boolean_nonexistent",
        {"solid1": "component1:solid1", "solid2": "component1:solid2"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error" or "error" in data
