"""Tests for advanced PCB tools (Phase 8)."""

from __future__ import annotations

import json
import math

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


# ---------------------------------------------------------------------------
# Differential pair tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_differential_pair_creates_two_traces(client: CSTClient):
    """Verify VBA creates both _P and _N traces."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_differential_pair",
        {
            "name": "USB",
            "trace_width_mm": 0.15,
            "gap_mm": 0.15,
            "length_mm": 20,
            "layer": "Top",
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    assert "USB_P" in vba
    assert "USB_N" in vba
    assert "Brick" in vba


@pytest.mark.asyncio
async def test_differential_pair_impedance_calculation(client: CSTClient):
    """Verify differential impedance is calculated and in a reasonable range."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_differential_pair",
        {
            "name": "DIFF",
            "trace_width_mm": 0.12,
            "gap_mm": 0.2,
            "length_mm": 10,
            "layer": "Top",
            "epsilon_r": 4.4,
            "height_mm": 0.2,
        },
        client,
    )
    data = json.loads(result[0].text)
    imp = data["impedance"]
    # Differential impedance should be a positive number
    assert imp["differential_impedance_ohms"] > 0
    # Even mode should be >= odd mode
    assert imp["even_mode_z0_ohms"] >= imp["odd_mode_z0_ohms"]
    # Coupling coefficient should be between 0 and 1
    assert 0 <= imp["coupling_coefficient"] <= 1


# ---------------------------------------------------------------------------
# Via model tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_via_model_creates_barrel_and_pads(client: CSTClient):
    """Verify VBA creates barrel cylinder and pad bricks."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_via_model",
        {
            "name": "V1",
            "drill_diameter_mm": 0.3,
            "pad_diameter_mm": 0.6,
            "antipad_diameter_mm": 0.8,
            "start_layer": "Top",
            "end_layer": "Bottom",
            "x": 5.0,
            "y": 5.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    assert "V1_barrel" in vba
    assert "V1_pad_top" in vba
    assert "V1_pad_bot" in vba
    assert "Cylinder" in vba


@pytest.mark.asyncio
async def test_via_model_parasitic_estimates(client: CSTClient):
    """Verify parasitic L and C estimates are positive and reasonable."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_via_model",
        {
            "name": "V2",
            "drill_diameter_mm": 0.3,
            "pad_diameter_mm": 0.6,
            "antipad_diameter_mm": 0.8,
            "start_layer": "Top",
            "end_layer": "Bottom",
            "x": 0,
            "y": 0,
            "board_thickness_mm": 1.6,
            "epsilon_r": 4.4,
        },
        client,
    )
    data = json.loads(result[0].text)
    parasitics = data["parasitics"]
    # Inductance should be in reasonable range (0.1 to 5 nH for typical PCB via)
    assert 0.05 < parasitics["estimated_inductance_nh"] < 10.0
    # Capacitance should be in reasonable range (0.01 to 2 pF)
    assert 0.001 < parasitics["estimated_capacitance_pf"] < 5.0


@pytest.mark.asyncio
async def test_via_model_rejects_bad_dimensions(client: CSTClient):
    """Verify error when pad <= drill."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_via_model",
        {
            "name": "Bad",
            "drill_diameter_mm": 0.6,
            "pad_diameter_mm": 0.3,
            "antipad_diameter_mm": 0.8,
            "start_layer": "Top",
            "end_layer": "Bottom",
            "x": 0,
            "y": 0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "pad_diameter_mm" in data["message"]


# ---------------------------------------------------------------------------
# Via fence tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_via_fence_correct_count(client: CSTClient):
    """Verify correct number of vias for given spacing and length."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_via_fence",
        {
            "name": "Fence1",
            "x_start": 0,
            "y_start": 0,
            "x_end": 10,
            "y_end": 0,
            "via_spacing_mm": 1.0,
            "via_diameter_mm": 0.3,
            "pad_diameter_mm": 0.6,
        },
        client,
    )
    data = json.loads(result[0].text)
    # 10mm / 1mm spacing = 11 vias (0, 1, 2, ..., 10)
    assert data["num_vias"] == 11
    assert abs(data["total_length_mm"] - 10.0) < 0.01


@pytest.mark.asyncio
async def test_via_fence_multi_row(client: CSTClient):
    """Verify multiple rows multiply the via count."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_via_fence",
        {
            "name": "Fence2",
            "x_start": 0,
            "y_start": 0,
            "x_end": 5,
            "y_end": 0,
            "via_spacing_mm": 1.0,
            "via_diameter_mm": 0.3,
            "pad_diameter_mm": 0.6,
            "rows": 2,
        },
        client,
    )
    data = json.loads(result[0].text)
    # 6 vias per row * 2 rows = 12
    assert data["num_vias"] == 12
    assert data["num_rows"] == 2


# ---------------------------------------------------------------------------
# CPW transition tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cpw_transition_creates_tapered_geometry(client: CSTClient):
    """Verify VBA creates polygon-based tapered geometry."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_cpw_transition",
        {
            "name": "CPW_Trans",
            "cpw_width_mm": 1.0,
            "cpw_gap_mm": 0.5,
            "microstrip_width_mm": 1.5,
            "transition_length_mm": 5.0,
            "layer": "Top",
            "height_mm": 0.5,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    # Should have polygon and extrude commands for tapered geometry
    assert "Polygon" in vba
    assert "ExtrudeCurve" in vba
    # Should calculate both impedances
    assert data["cpw_impedance_ohms"] > 0
    assert data["microstrip_impedance_ohms"] > 0


@pytest.mark.asyncio
async def test_cpw_transition_impedances_reasonable(client: CSTClient):
    """Verify CPW and microstrip impedances are in reasonable range."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_cpw_transition",
        {
            "name": "Trans2",
            "cpw_width_mm": 1.5,
            "cpw_gap_mm": 0.3,
            "microstrip_width_mm": 2.0,
            "transition_length_mm": 8.0,
            "layer": "Top",
            "height_mm": 1.0,
            "epsilon_r": 4.4,
        },
        client,
    )
    data = json.loads(result[0].text)
    # Typical CPW impedances: 20-200 ohms
    assert 10 < data["cpw_impedance_ohms"] < 300
    # Typical microstrip impedances: 10-200 ohms
    assert 10 < data["microstrip_impedance_ohms"] < 300


# ---------------------------------------------------------------------------
# Coupling calculation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_coupling_coefficient_in_range(client: CSTClient):
    """Verify coupling coefficient is between 0 and 1."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_calculate_coupling",
        {
            "trace_width_mm": 0.15,
            "separation_mm": 0.15,
            "height_mm": 0.2,
            "epsilon_r": 4.4,
            "coupling_length_mm": 10.0,
            "frequency_ghz": 5.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert 0 < data["coupling_coefficient"] < 1
    assert data["even_mode_z0_ohms"] > data["odd_mode_z0_ohms"]
    # Crosstalk should be negative dB values
    assert data["near_end_crosstalk_db"] < 0
    assert data["far_end_crosstalk_db"] < 0


@pytest.mark.asyncio
async def test_coupling_decreases_with_separation(client: CSTClient):
    """Verify coupling decreases when traces are farther apart."""
    from mcp_cst_studio.tools.pcb import handle

    # Close traces
    result_close = await handle(
        "cst_pcb_calculate_coupling",
        {
            "trace_width_mm": 0.15,
            "separation_mm": 0.1,
            "height_mm": 0.2,
            "epsilon_r": 4.4,
            "coupling_length_mm": 10.0,
            "frequency_ghz": 5.0,
        },
        client,
    )
    data_close = json.loads(result_close[0].text)

    # Far traces
    result_far = await handle(
        "cst_pcb_calculate_coupling",
        {
            "trace_width_mm": 0.15,
            "separation_mm": 1.0,
            "height_mm": 0.2,
            "epsilon_r": 4.4,
            "coupling_length_mm": 10.0,
            "frequency_ghz": 5.0,
        },
        client,
    )
    data_far = json.loads(result_far[0].text)

    assert data_close["coupling_coefficient"] > data_far["coupling_coefficient"]


# ---------------------------------------------------------------------------
# SIW waveguide tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_siw_cutoff_frequency(client: CSTClient):
    """Verify SIW cutoff frequency against manual calculation."""
    from mcp_cst_studio.tools.pcb import handle

    width = 10.0  # mm
    via_d = 0.5  # mm
    via_pitch = 1.0  # mm
    er = 4.4

    result = await handle(
        "cst_pcb_siw_waveguide",
        {
            "name": "SIW1",
            "width_mm": width,
            "via_diameter_mm": via_d,
            "via_pitch_mm": via_pitch,
            "length_mm": 30,
            "layer": "Top",
            "epsilon_r": er,
            "height_mm": 1.5,
        },
        client,
    )
    data = json.loads(result[0].text)

    # Manual calculation
    w_eff = width - via_d ** 2 / (0.95 * via_pitch)
    c0 = 299792458.0
    fc_manual = c0 / (2.0 * w_eff * 1e-3 * math.sqrt(er)) / 1e9

    assert abs(data["analysis"]["cutoff_frequency_ghz"] - fc_manual) < 0.01
    assert data["analysis"]["effective_width_mm"] == round(w_eff, 4)


@pytest.mark.asyncio
async def test_siw_rejects_invalid_geometry(client: CSTClient):
    """Verify error when via parameters make effective width non-positive."""
    from mcp_cst_studio.tools.pcb import handle

    # Very large via diameter relative to pitch makes w_eff <= 0
    result = await handle(
        "cst_pcb_siw_waveguide",
        {
            "name": "Bad",
            "width_mm": 2.0,
            "via_diameter_mm": 2.0,
            "via_pitch_mm": 0.5,
            "length_mm": 10,
            "layer": "Top",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "non-positive" in data["message"]


@pytest.mark.asyncio
async def test_siw_creates_planes_and_vias(client: CSTClient):
    """Verify VBA creates top/bottom planes and via fences."""
    from mcp_cst_studio.tools.pcb import handle

    result = await handle(
        "cst_pcb_siw_waveguide",
        {
            "name": "SIW2",
            "width_mm": 8.0,
            "via_diameter_mm": 0.4,
            "via_pitch_mm": 0.8,
            "length_mm": 20,
            "layer": "Top",
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    # Top and bottom planes
    assert "SIW2_top" in vba
    assert "SIW2_bottom" in vba
    # Via fences on both sides
    assert "SIW2_via_left_0" in vba
    assert "SIW2_via_right_0" in vba
    assert "Cylinder" in vba
    assert "Brick" in vba
