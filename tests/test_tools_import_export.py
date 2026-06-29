"""Tests for import/export tools — verify VBA generation in offline mode."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_import_cad(client: CSTClient):
    from mcp_cst_studio.tools.import_export import handle

    result = await handle(
        "cst_import_cad",
        {"file_path": "/tmp/model.step", "format": "stp", "component": "Import"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    # VBA should reference STEP import object and the file path
    assert "STEP" in vba or "Read" in vba
    assert "/tmp/model.step" in vba or "model.step" in vba


@pytest.mark.asyncio
async def test_export_cad(client: CSTClient):
    from mcp_cst_studio.tools.import_export import handle

    result = await handle(
        "cst_export_cad",
        {"file_path": "/tmp/output.step", "format": "stp"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "STEP" in vba or "Write" in vba
    assert "/tmp/output.step" in vba or "output.step" in vba


@pytest.mark.asyncio
async def test_import_touchstone(client: CSTClient):
    from mcp_cst_studio.tools.import_export import handle

    result = await handle(
        "cst_import_touchstone",
        {"file_path": "/tmp/data.s2p", "port_number": 1},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "TouchstoneImport" in vba or "Touchstone" in vba
    assert "/tmp/data.s2p" in vba or "data.s2p" in vba


@pytest.mark.asyncio
async def test_export_touchstone(client: CSTClient):
    from mcp_cst_studio.tools.import_export import handle

    result = await handle(
        "cst_export_touchstone",
        {"file_path": "/tmp/output.s2p"},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "TouchstoneExport" in vba or "Touchstone" in vba
    assert "/tmp/output.s2p" in vba or "output.s2p" in vba


@pytest.mark.asyncio
async def test_export_farfield(client: CSTClient):
    from mcp_cst_studio.tools.import_export import handle

    result = await handle(
        "cst_export_farfield",
        {"file_path": "/tmp/farfield.csv", "frequency": 2.4},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "FarfieldPlot" in vba or "farfield" in vba.lower()
    assert "/tmp/farfield.csv" in vba or "farfield.csv" in vba


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.import_export import handle

    result = await handle("cst_nonexistent_import_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
