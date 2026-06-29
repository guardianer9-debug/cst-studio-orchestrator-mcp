"""Tests for advanced result extraction tools — verify VBA generation in offline mode."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


# ---------------------------------------------------------------------------
# cst_get_s_parameter_phase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_s_parameter_phase_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_s_parameter_phase", {"port_in": 1, "port_out": 1}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("s_parameter") == "S1,1"
    assert data.get("data_type") == "phase"
    vba = data.get("vba_script", "")
    assert "S1,1" in vba
    assert "phase" in vba.lower() or "Phase" in vba


@pytest.mark.asyncio
async def test_get_s_parameter_phase_unwrap(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_s_parameter_phase",
        {"port_in": 1, "port_out": 2, "unwrap": True},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("unwrap") is True
    assert data.get("s_parameter") == "S2,1"
    vba = data.get("vba_script", "")
    assert "unwrap" in vba.lower() or "offset" in vba.lower()


# ---------------------------------------------------------------------------
# cst_get_group_delay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_group_delay_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_group_delay", {"port_in": 1, "port_out": 1}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("data_type") == "group_delay"
    vba = data.get("vba_script", "")
    assert "S1,1" in vba
    assert "tau" in vba.lower() or "group delay" in vba.lower()


@pytest.mark.asyncio
async def test_get_group_delay_different_ports(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_group_delay", {"port_in": 1, "port_out": 2}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("s_parameter") == "S2,1"
    vba = data.get("vba_script", "")
    assert "S2,1" in vba


# ---------------------------------------------------------------------------
# cst_get_pattern_cut
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_pattern_cut_e_plane(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_pattern_cut", {"frequency": 2.4, "plane": "E"}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("plane") == "E"
    assert data.get("frequency_ghz") == 2.4
    vba = data.get("vba_script", "")
    assert "FarfieldPlot" in vba or "farfield" in vba.lower()


@pytest.mark.asyncio
async def test_get_pattern_cut_h_plane(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_pattern_cut", {"frequency": 5.8, "plane": "H"}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("plane") == "H"
    vba = data.get("vba_script", "")
    assert "90" in vba  # H-plane uses phi=90


@pytest.mark.asyncio
async def test_get_pattern_cut_invalid_plane(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_pattern_cut",
        {"frequency": 2.4, "plane": "invalid"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "Invalid plane" in data.get("message", "")


# ---------------------------------------------------------------------------
# cst_get_cross_polarization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_cross_polarization_ludwig3(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_cross_polarization",
        {"frequency": 2.4, "definition": "Ludwig3"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("definition") == "Ludwig3"
    vba = data.get("vba_script", "")
    assert "ludwig3" in vba.lower()
    assert "copol" in vba.lower() or "crosspol" in vba.lower()


@pytest.mark.asyncio
async def test_get_cross_polarization_circular(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_cross_polarization",
        {"frequency": 5.0, "definition": "circular"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("definition") == "circular"
    vba = data.get("vba_script", "")
    assert "circular" in vba.lower()


@pytest.mark.asyncio
async def test_get_cross_polarization_invalid_definition(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_cross_polarization",
        {"frequency": 2.4, "definition": "wrong"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


# ---------------------------------------------------------------------------
# cst_get_axial_ratio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_axial_ratio_vs_angle(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_axial_ratio",
        {"frequency": 2.4, "mode": "vs_angle"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("mode") == "vs_angle"
    vba = data.get("vba_script", "")
    assert "Axial Ratio" in vba


@pytest.mark.asyncio
async def test_get_axial_ratio_vs_frequency(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_axial_ratio",
        {"frequency": 5.8, "mode": "vs_frequency", "theta_cut": 0, "phi_cut": 0},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("mode") == "vs_frequency"


@pytest.mark.asyncio
async def test_get_axial_ratio_invalid_mode(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_axial_ratio",
        {"frequency": 2.4, "mode": "bad_mode"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


# ---------------------------------------------------------------------------
# cst_get_surface_current
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_surface_current_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_surface_current", {"frequency": 2.4}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("frequency_ghz") == 2.4
    vba = data.get("vba_script", "")
    assert "Surface Current" in vba or "surface_current" in vba


@pytest.mark.asyncio
async def test_get_surface_current_with_component(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_surface_current",
        {"frequency": 5.0, "component": "Antenna"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    vba = data.get("vba_script", "")
    assert "Antenna" in vba


# ---------------------------------------------------------------------------
# cst_get_efficiency_breakdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_efficiency_breakdown_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_efficiency_breakdown", {"frequency": 2.4}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("data_type") == "efficiency_breakdown"
    vba = data.get("vba_script", "")
    assert "Radiation Efficiency" in vba or "rad. efficiency" in vba
    assert "Conductor Loss" in vba or "Dielectric Loss" in vba


@pytest.mark.asyncio
async def test_get_efficiency_breakdown_has_power_budget(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_efficiency_breakdown", {"frequency": 5.8}, client)
    data = json.loads(result[0].text)
    vba = data.get("vba_script", "")
    # Should reference the power budget tables
    assert "Power" in vba
    assert "Stimulated" in vba or "Accepted" in vba or "Radiated" in vba


# ---------------------------------------------------------------------------
# cst_get_time_domain_signal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_time_domain_signal_reflected(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_time_domain_signal",
        {"port": 1, "signal_type": "reflected"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("signal_type") == "reflected"
    assert "o1,1" in data.get("tree_path", "")
    vba = data.get("vba_script", "")
    assert "o1,1" in vba


@pytest.mark.asyncio
async def test_get_time_domain_signal_incident(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_time_domain_signal",
        {"port": 2, "signal_type": "incident"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("signal_type") == "incident"
    assert "i2" in data.get("tree_path", "")


@pytest.mark.asyncio
async def test_get_time_domain_signal_transmitted(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_time_domain_signal",
        {"port": 1, "signal_type": "transmitted", "port_out": 2},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert "o2,1" in data.get("tree_path", "")


@pytest.mark.asyncio
async def test_get_time_domain_signal_invalid_type(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_time_domain_signal",
        {"port": 1, "signal_type": "invalid"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


# ---------------------------------------------------------------------------
# cst_get_smith_chart_data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_smith_chart_data_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_smith_chart_data", {"port": 1}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("data_type") == "smith_chart"
    assert data.get("z0") == 50.0
    vba = data.get("vba_script", "")
    assert "S1,1" in vba
    assert "50" in vba


@pytest.mark.asyncio
async def test_get_smith_chart_data_custom_z0(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_smith_chart_data", {"port": 1, "z0": 75}, client)
    data = json.loads(result[0].text)
    assert data.get("z0") == 75
    vba = data.get("vba_script", "")
    assert "75" in vba


@pytest.mark.asyncio
async def test_get_smith_chart_data_invalid_z0(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_smith_chart_data", {"port": 1, "z0": -50}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "z0" in data.get("message", "").lower() or "impedance" in data.get("message", "").lower()


# ---------------------------------------------------------------------------
# cst_get_bandwidth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_bandwidth_s11_default(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_bandwidth", {"port": 1}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("data_type") == "bandwidth"
    assert data.get("threshold_db") == -10.0
    assert data.get("criterion") == "S11"
    vba = data.get("vba_script", "")
    assert "S1,1" in vba
    assert "-10" in vba


@pytest.mark.asyncio
async def test_get_bandwidth_vswr_criterion(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_bandwidth",
        {"port": 1, "threshold_db": 2.0, "criterion": "VSWR"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("criterion") == "VSWR"
    vba = data.get("vba_script", "")
    assert "vswr" in vba.lower() or "VSWR" in vba


@pytest.mark.asyncio
async def test_get_bandwidth_invalid_criterion(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_bandwidth",
        {"port": 1, "criterion": "invalid"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


# ---------------------------------------------------------------------------
# cst_get_radiation_pattern_3d
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_radiation_pattern_3d_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_radiation_pattern_3d",
        {"frequency": 2.4},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("frequency_ghz") == 2.4
    assert data.get("resolution_deg") == 5.0
    assert data.get("coordinate") == "spherical"
    vba = data.get("vba_script", "")
    assert "3D" in vba
    assert "FarfieldPlot" in vba or "farfield" in vba.lower()


@pytest.mark.asyncio
async def test_get_radiation_pattern_3d_cartesian(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_radiation_pattern_3d",
        {"frequency": 5.8, "resolution_deg": 2, "coordinate": "cartesian"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("coordinate") == "cartesian"
    vba = data.get("vba_script", "")
    assert "cartesian" in vba.lower()


@pytest.mark.asyncio
async def test_get_radiation_pattern_3d_invalid_resolution(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_radiation_pattern_3d",
        {"frequency": 2.4, "resolution_deg": -5},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


# ---------------------------------------------------------------------------
# cst_get_current_distribution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_distribution_basic(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_current_distribution", {"frequency": 2.4}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert data.get("frequency_ghz") == 2.4
    vba = data.get("vba_script", "")
    assert "Current" in vba
    assert "current_distribution" in vba or "current (f=" in vba


@pytest.mark.asyncio
async def test_get_current_distribution_with_component(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_current_distribution",
        {"frequency": 5.0, "component": "Substrate"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    vba = data.get("vba_script", "")
    assert "Substrate" in vba


# ---------------------------------------------------------------------------
# Edge cases and validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_port_number(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle(
        "cst_get_s_parameter_phase",
        {"port_in": 0, "port_out": 1},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


@pytest.mark.asyncio
async def test_invalid_frequency(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_pattern_cut", {"frequency": -1.0}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


@pytest.mark.asyncio
async def test_frequency_above_max(client: CSTClient):
    from mcp_cst_studio.tools.results import handle

    result = await handle("cst_get_surface_current", {"frequency": 2000.0}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
