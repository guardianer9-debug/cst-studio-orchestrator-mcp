"""Tests for impedance matching network tools."""

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
# L-network tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l_network_50_to_100(client: CSTClient):
    """50 ohm to 100 ohm at 1 GHz: Q = sqrt(100/50 - 1) = 1."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_l_network",
        {
            "z_source_real": 50,
            "z_load_real": 100,
            "frequency_ghz": 1.0,
            "topology": "lowpass",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert abs(data["q_factor"] - 1.0) < 0.01


@pytest.mark.asyncio
async def test_l_network_highpass(client: CSTClient):
    """Highpass topology should produce series C and shunt L."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_l_network",
        {
            "z_source_real": 50,
            "z_load_real": 200,
            "frequency_ghz": 2.4,
            "topology": "highpass",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert data["topology"] == "highpass"
    # Highpass: series element is C, shunt element is L
    assert data["series_element"]["type"] == "C"
    assert data["shunt_element"]["type"] == "L"


@pytest.mark.asyncio
async def test_l_network_already_matched(client: CSTClient):
    """Identical real impedances should report already matched."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_l_network",
        {"z_source_real": 50, "z_load_real": 50, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data["q_factor"] == 0


@pytest.mark.asyncio
async def test_l_network_complex_load(client: CSTClient):
    """Complex load should include compensation elements."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_l_network",
        {
            "z_source_real": 50,
            "z_load_real": 100,
            "z_load_imag": 30,
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert "load_compensation" in data


@pytest.mark.asyncio
async def test_l_network_component_values(client: CSTClient):
    """Verify L-network component values are physically reasonable."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_l_network",
        {
            "z_source_real": 50,
            "z_load_real": 100,
            "frequency_ghz": 1.0,
            "topology": "lowpass",
        },
        client,
    )
    data = json.loads(result[0].text)
    cv = data["component_values"]

    # For 50->100 at 1 GHz lowpass:
    # Q=1, X_series = Q*R_small = 50 ohm, X_shunt = R_large/Q = 100 ohm
    # L = 50/(2*pi*1e9) = ~7.96 nH
    # C = 1/(2*pi*1e9*100) = ~1.59 pF
    assert "L_nH" in cv
    assert "shunt_C_pF" in cv
    assert 7.0 < cv["L_nH"] < 9.0
    assert 1.0 < cv["shunt_C_pF"] < 2.0


# ---------------------------------------------------------------------------
# Pi-network tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pi_network_basic(client: CSTClient):
    """Pi-network with default Q factor should succeed."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_pi_network",
        {"z_source_real": 50, "z_load_real": 200, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert data["topology"] == "pi"
    cv = data["component_values"]
    assert "C1_pF" in cv
    assert "L_nH" in cv
    assert "C2_pF" in cv


@pytest.mark.asyncio
async def test_pi_network_q_too_low(client: CSTClient):
    """Q factor below minimum should return an error."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_pi_network",
        {
            "z_source_real": 50,
            "z_load_real": 200,
            "frequency_ghz": 1.0,
            "q_factor": 0.5,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "too low" in data["message"].lower()


# ---------------------------------------------------------------------------
# T-network tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t_network_basic(client: CSTClient):
    """T-network should produce L1, C, L2 components."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_t_network",
        {"z_source_real": 50, "z_load_real": 75, "frequency_ghz": 2.4},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert data["topology"] == "t"
    cv = data["component_values"]
    assert "L1_nH" in cv
    assert "C_pF" in cv
    assert "L2_nH" in cv


# ---------------------------------------------------------------------------
# Stub matching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_matching_open(client: CSTClient):
    """Open stub matching should produce reasonable lengths."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_stub",
        {
            "z_load_real": 100,
            "z_load_imag": 50,
            "z0": 50,
            "frequency_ghz": 1.0,
            "stub_type": "open",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    # Stub length should be between 0 and lambda/2
    assert 0 <= data["stub_length_wavelengths"] < 0.5
    assert 0 <= data["distance_wavelengths"] < 0.5
    assert data["stub_length_mm"] > 0
    assert data["distance_from_load_mm"] >= 0


@pytest.mark.asyncio
async def test_stub_matching_short(client: CSTClient):
    """Short stub matching should also work."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_stub",
        {
            "z_load_real": 75,
            "z_load_imag": -25,
            "z0": 50,
            "frequency_ghz": 2.4,
            "stub_type": "short",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert data["stub_type"] == "short"


@pytest.mark.asyncio
async def test_stub_matching_already_matched(client: CSTClient):
    """Load already matched to Z0 should report no stub needed."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_stub",
        {"z_load_real": 50, "z_load_imag": 0, "z0": 50, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert data["stub_length_mm"] == 0


# ---------------------------------------------------------------------------
# Quarter-wave transformer tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quarter_wave_single(client: CSTClient):
    """Single-section: Z_t = sqrt(50 * 100) = 70.71 ohm."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_quarter_wave",
        {"z_source": 50, "z_load": 100, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    z_t = data["section_impedances_ohm"][0]
    expected = math.sqrt(50 * 100)
    assert abs(z_t - expected) < 0.01


@pytest.mark.asyncio
async def test_quarter_wave_multi_section(client: CSTClient):
    """Multi-section should produce increasing impedances from source to load."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_quarter_wave",
        {
            "z_source": 50,
            "z_load": 200,
            "frequency_ghz": 2.0,
            "num_sections": 3,
            "design": "maximally_flat",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    impedances = data["section_impedances_ohm"]
    assert len(impedances) == 3
    # Impedances should be monotonically increasing from Z_s toward Z_l
    for i in range(len(impedances) - 1):
        assert impedances[i] < impedances[i + 1]
    # All should be between Z_s and Z_l
    for z in impedances:
        assert 50 <= z <= 200


@pytest.mark.asyncio
async def test_quarter_wave_section_length(client: CSTClient):
    """Section length should be lambda/4."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_quarter_wave",
        {"z_source": 50, "z_load": 100, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    # lambda = c/f = 299.792 mm at 1 GHz
    expected_length = 299792458.0 / 1e9 * 1e3 / 4.0  # ~74.95 mm
    assert abs(data["section_length_mm"] - expected_length) < 0.1


# ---------------------------------------------------------------------------
# Lumped-element VBA tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_lumped_vba(client: CSTClient):
    """VBA should contain LumpedElement commands."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_create_lumped",
        {
            "components": [
                {"type": "L", "value": 10.0, "unit": "nH", "connection": "series"},
                {"type": "C", "value": 2.0, "unit": "pF", "connection": "shunt"},
            ],
            "frequency_ghz": 1.0,
            "port_impedance": 50,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", data.get("vba_script", ""))
    assert "LumpedElement" in vba
    assert data["component_count"] == 2


@pytest.mark.asyncio
async def test_create_lumped_invalid_type(client: CSTClient):
    """Invalid component type should return error."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_create_lumped",
        {
            "components": [
                {"type": "X", "value": 10, "unit": "nH", "connection": "series"},
            ],
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# Smith chart transform tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smith_transform_series_l(client: CSTClient):
    """Series L should increase reactance (imaginary part)."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_impedance_smith_transform",
        {
            "z_in_real": 50,
            "z_in_imag": 0,
            "z0": 50,
            "operation": "series_L",
            "value": 10.0,  # 10 nH
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert data["z_out_real"] == 50.0  # real part unchanged
    assert data["z_out_imag"] > 0  # reactance increased


@pytest.mark.asyncio
async def test_smith_transform_shunt_c(client: CSTClient):
    """Shunt C should change impedance."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_impedance_smith_transform",
        {
            "z_in_real": 100,
            "z_in_imag": 0,
            "z0": 50,
            "operation": "shunt_C",
            "value": 5.0,  # 5 pF
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    # Shunt C should reduce the real part (bring closer to Z0)
    assert data["z_out_real"] < 100.0
    assert "vswr" in data


@pytest.mark.asyncio
async def test_smith_transform_transmission_line(client: CSTClient):
    """90-degree TL on 50-ohm load with Z0=50 should stay at 50."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_impedance_smith_transform",
        {
            "z_in_real": 50,
            "z_in_imag": 0,
            "z0": 50,
            "operation": "transmission_line",
            "value": 90.0,  # 90 degrees
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    # Matched load stays matched after any length of TL
    assert abs(data["z_out_real"] - 50.0) < 0.1
    assert abs(data["z_out_imag"]) < 0.1


@pytest.mark.asyncio
async def test_smith_transform_vswr_and_return_loss(client: CSTClient):
    """VSWR and return loss should be computed correctly."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_impedance_smith_transform",
        {
            "z_in_real": 50,
            "z_in_imag": 0,
            "z0": 50,
            "operation": "series_L",
            "value": 0.0001,  # negligible inductance
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    # Nearly matched: VSWR close to 1
    assert data["vswr"] < 1.01
    assert data["return_loss_dB"] > 40  # very good match


# ---------------------------------------------------------------------------
# Microstrip impedance tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_microstrip_50_ohm(client: CSTClient):
    """~3 mm wide on 1.6 mm FR-4 should be approximately 50 ohm."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_microstrip_impedance",
        {
            "width_mm": 3.0,
            "height_mm": 1.6,
            "epsilon_r": 4.4,
            "frequency_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    # Should be close to 50 ohm (typically 47-53 ohm range)
    assert 40 < data["z0_ohm"] < 60


@pytest.mark.asyncio
async def test_microstrip_no_frequency(client: CSTClient):
    """Without frequency, should still return static impedance."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_microstrip_impedance",
        {"width_mm": 3.0, "height_mm": 1.6, "epsilon_r": 4.4},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert "z0_ohm" in data
    assert "wavelength_mm" not in data  # no frequency => no wavelength


@pytest.mark.asyncio
async def test_microstrip_dispersion(client: CSTClient):
    """High frequency should shift impedance due to dispersion."""
    from mcp_cst_studio.tools.matching import handle

    result_low = await handle(
        "cst_matching_microstrip_impedance",
        {"width_mm": 1.0, "height_mm": 0.5, "epsilon_r": 10.0, "frequency_ghz": 0.1},
        client,
    )
    result_high = await handle(
        "cst_matching_microstrip_impedance",
        {"width_mm": 1.0, "height_mm": 0.5, "epsilon_r": 10.0, "frequency_ghz": 20.0},
        client,
    )
    data_low = json.loads(result_low[0].text)
    data_high = json.loads(result_high[0].text)

    # Effective permittivity increases with frequency (Kirschning-Jansen)
    assert data_high["epsilon_eff"] > data_low["epsilon_eff"]


@pytest.mark.asyncio
async def test_microstrip_propagation_delay(client: CSTClient):
    """Propagation delay should be positive and reasonable."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_microstrip_impedance",
        {"width_mm": 3.0, "height_mm": 1.6, "epsilon_r": 4.4, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    # For FR-4, delay ~6-7 ps/mm
    assert 4 < data["propagation_delay_ps_mm"] < 10


# ---------------------------------------------------------------------------
# Edge case / error tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l_network_invalid_topology(client: CSTClient):
    """Invalid topology string should return error."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle(
        "cst_matching_l_network",
        {
            "z_source_real": 50,
            "z_load_real": 100,
            "frequency_ghz": 1.0,
            "topology": "bandpass",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_unknown_tool_name(client: CSTClient):
    """Unknown tool name should return error."""
    from mcp_cst_studio.tools.matching import handle

    result = await handle("cst_matching_nonexistent", {}, client)
    data = json.loads(result[0].text)
    assert data["status"] == "error"
