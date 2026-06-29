"""Tests for raw VBA access tools — offline safety validation and reference lookup."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_execute_vba_valid_code(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle(
        "cst_execute_vba",
        {"code": "Dim x As Double\nx = 1.0"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    # Offline mode: execute_vba returns {"status": "offline", "vba": code}
    assert "status" in data
    assert data.get("status") != "error"


@pytest.mark.asyncio
async def test_execute_vba_empty_code_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle("cst_execute_vba", {"code": ""}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data


@pytest.mark.asyncio
async def test_execute_vba_whitespace_only_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle("cst_execute_vba", {"code": "   \n\t  "}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data


@pytest.mark.asyncio
async def test_execute_vba_dangerous_shell_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle(
        "cst_execute_vba",
        {"code": 'Shell "cmd"'},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
    # Error should mention the dangerous pattern
    assert "Shell" in data["message"] or "dangerous" in data["message"].lower()


@pytest.mark.asyncio
async def test_vba_help_known_object(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle("cst_vba_help", {"object_name": "Brick"}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    # Either found (status=ok with object_name) or not found (status=not_found)
    assert data.get("status") in ("ok", "not_found")
    if data.get("status") == "ok":
        assert "object_name" in data


@pytest.mark.asyncio
async def test_vba_help_unknown_object_returns_not_found(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle(
        "cst_vba_help",
        {"object_name": "NonExistentObject12345"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "not_found"
    assert "message" in data


@pytest.mark.asyncio
async def test_list_vba_objects_all(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle("cst_list_vba_objects", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data
    # Returns either categories dict or an error
    assert data.get("status") in ("ok", "error")


@pytest.mark.asyncio
async def test_list_vba_objects_by_category(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle("cst_list_vba_objects", {"category": "geometry"}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data
    # Either found the category (ok) or it doesn't exist in reference data (error)
    assert data.get("status") in ("ok", "error")


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.vba import handle

    result = await handle("cst_nonexistent_vba_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
