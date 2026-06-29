"""Tests for PCB tools."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_create_stackup(client: CSTClient):
    from mcp_cst_studio.tools.pcb import handle

    layers = [
        {"name": "Top", "type": "signal", "thickness_mm": 0.035, "material": "Copper", "epsilon_r": 1.0},
        {"name": "Prepreg", "type": "dielectric", "thickness_mm": 0.2, "material": "FR-4", "epsilon_r": 4.4},
        {"name": "Inner1", "type": "ground", "thickness_mm": 0.035, "material": "Copper", "epsilon_r": 1.0},
        {"name": "Core", "type": "dielectric", "thickness_mm": 1.0, "material": "FR-4", "epsilon_r": 4.4},
        {"name": "Inner2", "type": "ground", "thickness_mm": 0.035, "material": "Copper", "epsilon_r": 1.0},
        {"name": "Prepreg2", "type": "dielectric", "thickness_mm": 0.2, "material": "FR-4", "epsilon_r": 4.4},
        {"name": "Bottom", "type": "signal", "thickness_mm": 0.035, "material": "Copper", "epsilon_r": 1.0},
    ]
    result = await handle(
        "cst_pcb_create_stackup",
        {"layers": layers, "board_width_mm": 50, "board_length_mm": 50},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    assert "Brick" in vba or "brick" in vba.lower()


@pytest.mark.asyncio
async def test_create_trace(client: CSTClient):
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_create_trace",
        {
            "trace_type": "microstrip",
            "width_mm": 0.3,
            "length_mm": 10,
            "layer": "Top",
            "x_start": 0,
            "y_start": 0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    assert len(vba) > 20


@pytest.mark.asyncio
async def test_list_stackup_templates(client: CSTClient):
    from mcp_cst_studio.tools.pcb import handle

    result = await handle("cst_pcb_list_stackup_templates", {}, client)
    data = json.loads(result[0].text)
    assert "stackups" in data or "templates" in data or isinstance(data, list)
