"""Tests for project management tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_create_project(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle(
        "cst_create_project",
        {"path": "/tmp/test.cst", "project_type": "MWS"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba_script", "")
    assert "StoreTemplateSetting" in vba or "StoreTemplateBased" in vba or "Template" in vba
    assert "MW & RF & Optical" in vba or "MWS" in vba or "OpenNewProject" in vba


@pytest.mark.asyncio
async def test_open_project(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle(
        "cst_open_project",
        {"path": "/tmp/test.cst"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "vba_script" in data or "status" in data


@pytest.mark.asyncio
async def test_save_project(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle("cst_save_project", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "vba_script" in data or "status" in data


@pytest.mark.asyncio
async def test_close_project(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle("cst_close_project", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data


@pytest.mark.asyncio
async def test_project_info(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle("cst_project_info", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("mode") == "offline"


@pytest.mark.asyncio
async def test_connection_status(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle("cst_connection_status", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "mode" in data


@pytest.mark.asyncio
async def test_invalid_project_type(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle(
        "cst_create_project",
        {"path": "/tmp/test.cst", "project_type": "INVALID_TYPE"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error" or "error" in str(data).lower()


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.project import handle

    result = await handle("cst_nonexistent_project_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
