"""Tests for phased array synthesis tools.

Covers VBA generation (linear, planar, circular arrays, mutual coupling)
and pure-Python analytics (array factor, beam steering, taper, grating lobes).
"""

from __future__ import annotations

import json
import math

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig

C0 = 299792458.0  # speed of light m/s


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


# ===================================================================
# 1. Linear array tests
# ===================================================================


@pytest.mark.asyncio
async def test_linear_array_vba(client: CSTClient):
    """Linear array generates Transform.Translate VBA for each copy."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_linear",
        {"num_elements": 4, "spacing_mm": 30.0, "frequency_ghz": 5.0},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba_script", "")
    params = data.get("calculated_parameters", {})

    assert params["num_elements"] == 4
    assert params["spacing_mm"] == 30.0
    assert params["total_length_mm"] == 90.0
    # 3 copies should be generated (elements 2, 3, 4)
    assert vba.count("Transform") >= 3
    assert "Element_2" in vba
    assert "Element_4" in vba


@pytest.mark.asyncio
async def test_linear_array_y_axis(client: CSTClient):
    """Linear array along Y axis."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_linear",
        {"num_elements": 3, "spacing_mm": 20.0, "frequency_ghz": 10.0, "axis": "y"},
        client,
    )
    data = json.loads(result[0].text)
    params = data.get("calculated_parameters", {})
    assert params["axis"] == "y"
    assert params["total_length_mm"] == 40.0


@pytest.mark.asyncio
async def test_linear_array_spacing_wavelengths(client: CSTClient):
    """Verify spacing in wavelengths is correctly computed."""
    from mcp_cst_studio.tools.arrays import handle

    freq = 10.0  # GHz
    lam_mm = (C0 / (freq * 1e9)) * 1000  # ~30 mm
    spacing_mm = lam_mm / 2  # half wavelength

    result = await handle(
        "cst_array_linear",
        {"num_elements": 4, "spacing_mm": spacing_mm, "frequency_ghz": freq},
        client,
    )
    data = json.loads(result[0].text)
    params = data["calculated_parameters"]
    assert abs(params["spacing_wavelengths"] - 0.5) < 0.001


# ===================================================================
# 2. Planar array tests
# ===================================================================


@pytest.mark.asyncio
async def test_planar_array_rectangular(client: CSTClient):
    """Planar rectangular array generates correct number of copies."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_planar",
        {
            "num_x": 3, "num_y": 2,
            "spacing_x_mm": 15.0, "spacing_y_mm": 15.0,
            "frequency_ghz": 10.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    params = data.get("calculated_parameters", {})
    assert params["total_elements"] == 6
    assert params["lattice"] == "rectangular"

    vba = data.get("vba_script", "")
    # 5 copies (element 1 is original)
    assert "Element_6" in vba


@pytest.mark.asyncio
async def test_planar_array_triangular(client: CSTClient):
    """Triangular lattice offsets odd rows by dx/2."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_planar",
        {
            "num_x": 2, "num_y": 2,
            "spacing_x_mm": 20.0, "spacing_y_mm": 20.0,
            "lattice": "triangular",
            "frequency_ghz": 10.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["calculated_parameters"]["lattice"] == "triangular"
    assert data["calculated_parameters"]["total_elements"] == 4


# ===================================================================
# 3. Circular array tests
# ===================================================================


@pytest.mark.asyncio
async def test_circular_array_vba(client: CSTClient):
    """Circular array generates rotation transforms."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_circular",
        {"num_elements": 8, "radius_mm": 50.0, "frequency_ghz": 5.0},
        client,
    )
    data = json.loads(result[0].text)
    params = data["calculated_parameters"]
    assert params["num_elements"] == 8
    assert abs(params["angular_step_deg"] - 45.0) < 0.01

    vba = data.get("vba_script", "")
    assert "Rotate" in vba
    assert "Element_8" in vba


@pytest.mark.asyncio
async def test_circular_array_arc_spacing(client: CSTClient):
    """Arc spacing should be 2*R*sin(pi/N)."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_circular",
        {"num_elements": 6, "radius_mm": 100.0, "frequency_ghz": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    params = data["calculated_parameters"]
    expected_arc = 2 * 100.0 * math.sin(math.pi / 6)
    assert abs(params["arc_spacing_mm"] - expected_arc) < 0.01


# ===================================================================
# 4. Array factor computation tests
# ===================================================================


@pytest.mark.asyncio
async def test_array_factor_broadside_peak(client: CSTClient):
    """4-element broadside array has AF=4 (0 dB normalised) at theta=0."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_compute_factor",
        {"num_elements": 4, "spacing_wavelengths": 0.5, "scan_angle_deg": 0},
        client,
    )
    data = json.loads(result[0].text)
    # At theta=0, normalised AF should be 0 dB (peak)
    theta_list = data["theta_deg"]
    af_list = data["af_db"]
    idx_0 = theta_list.index(0.0)
    assert abs(af_list[idx_0] - 0.0) < 0.01


@pytest.mark.asyncio
async def test_array_factor_hpbw(client: CSTClient):
    """Array factor reports a reasonable HPBW for broadside array."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_compute_factor",
        {"num_elements": 8, "spacing_wavelengths": 0.5},
        client,
    )
    data = json.loads(result[0].text)
    hpbw = data["half_power_beamwidth_deg"]
    # For 8-element half-wave spaced array, HPBW ~ 12-15 degrees
    assert 5.0 < hpbw < 30.0


@pytest.mark.asyncio
async def test_array_factor_with_weights(client: CSTClient):
    """Array factor accepts custom amplitude weights."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_compute_factor",
        {
            "num_elements": 4,
            "spacing_wavelengths": 0.5,
            "amplitude_weights": [0.5, 1.0, 1.0, 0.5],
        },
        client,
    )
    data = json.loads(result[0].text)
    assert "af_db" in data
    assert len(data["theta_deg"]) > 10


@pytest.mark.asyncio
async def test_array_factor_scanned(client: CSTClient):
    """Array factor peak shifts when scan_angle_deg is set."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_compute_factor",
        {"num_elements": 8, "spacing_wavelengths": 0.5, "scan_angle_deg": 30},
        client,
    )
    data = json.loads(result[0].text)
    # Peak should be near 30 degrees
    af_list = data["af_db"]
    theta_list = data["theta_deg"]
    peak_idx = af_list.index(max(af_list))
    peak_theta = theta_list[peak_idx]
    assert abs(peak_theta - 30.0) < 3.0


@pytest.mark.asyncio
async def test_array_factor_sidelobe_level(client: CSTClient):
    """Uniform broadside array should have ~-13 dB sidelobe."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_compute_factor",
        {"num_elements": 16, "spacing_wavelengths": 0.5},
        client,
    )
    data = json.loads(result[0].text)
    psll = data["peak_sidelobe_level_db"]
    # Uniform array SLL is about -13.26 dB
    assert -16.0 < psll < -10.0


# ===================================================================
# 5. Beam steering tests
# ===================================================================


@pytest.mark.asyncio
async def test_beam_steering_broadside(client: CSTClient):
    """Broadside (0 deg) should give all-zero phases."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_beam_steering",
        {
            "num_elements": 4,
            "spacing_mm": 15.0,
            "frequency_ghz": 10.0,
            "scan_theta_deg": 0,
        },
        client,
    )
    data = json.loads(result[0].text)
    phases = data["phase_weights_deg"]
    assert len(phases) == 4
    for p in phases:
        assert abs(p) < 0.01


@pytest.mark.asyncio
async def test_beam_steering_30deg(client: CSTClient):
    """Verify progressive phase for 30-deg scan at half-wavelength spacing."""
    from mcp_cst_studio.tools.arrays import handle

    freq = 10.0
    lam_mm = (C0 / (freq * 1e9)) * 1000
    spacing = lam_mm / 2  # half wavelength

    result = await handle(
        "cst_array_beam_steering",
        {
            "num_elements": 4,
            "spacing_mm": spacing,
            "frequency_ghz": freq,
            "scan_theta_deg": 30,
        },
        client,
    )
    data = json.loads(result[0].text)
    phases = data["phase_weights_deg"]

    # Progressive phase: beta = -k*d*sin(30) = -pi/2 * sin(30) = -(2pi/lam)*(lam/2)*0.5 = -pi/2 rad = -90 deg
    # Phase for element n: n * (-90) deg, mod 360
    expected_progressive = -90.0
    for n in range(4):
        expected = (expected_progressive * n) % 360.0
        assert abs(phases[n] - expected) < 0.5, (
            f"Element {n}: expected {expected:.1f}, got {phases[n]:.1f}"
        )


@pytest.mark.asyncio
async def test_beam_steering_vba_has_port(client: CSTClient):
    """Beam steering VBA should contain Port phase configuration."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_beam_steering",
        {
            "num_elements": 4,
            "spacing_mm": 15.0,
            "frequency_ghz": 10.0,
            "scan_theta_deg": 20,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba_script", "")
    assert "Port" in vba
    assert "PhaseShift" in vba


# ===================================================================
# 6. Taper design tests
# ===================================================================


@pytest.mark.asyncio
async def test_taper_uniform(client: CSTClient):
    """Uniform taper returns all 1.0 weights."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_taper_design",
        {"num_elements": 8, "taper_type": "uniform"},
        client,
    )
    data = json.loads(result[0].text)
    weights = data["amplitude_weights"]
    assert len(weights) == 8
    for w in weights:
        assert abs(w - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_taper_hamming(client: CSTClient):
    """Hamming taper has correct shape: edges < center."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_taper_design",
        {"num_elements": 8, "taper_type": "hamming"},
        client,
    )
    data = json.loads(result[0].text)
    weights = data["amplitude_weights"]
    assert len(weights) == 8
    # Hamming: w(0) = 0.54 - 0.46 = 0.08 (normalised to peak)
    # Center elements should be 1.0 (peak)
    assert weights[0] < weights[3]  # edge < center
    assert weights[7] < weights[4]  # edge < center
    # Peak should be 1.0
    assert abs(max(weights) - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_taper_hanning(client: CSTClient):
    """Hanning taper has zero at edges."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_taper_design",
        {"num_elements": 8, "taper_type": "hanning"},
        client,
    )
    data = json.loads(result[0].text)
    weights = data["amplitude_weights"]
    # Hanning: w(0) = 0.5*(1-cos(0)) = 0, so first/last weights should be ~0
    assert weights[0] < 0.01
    assert weights[7] < 0.01


@pytest.mark.asyncio
async def test_taper_efficiency_less_than_one(client: CSTClient):
    """Non-uniform taper efficiency should be < 1."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_taper_design",
        {"num_elements": 16, "taper_type": "hamming"},
        client,
    )
    data = json.loads(result[0].text)
    assert 0.0 < data["taper_efficiency"] < 1.0


@pytest.mark.asyncio
async def test_taper_taylor(client: CSTClient):
    """Taylor taper generates valid weights."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_taper_design",
        {"num_elements": 10, "taper_type": "taylor", "sidelobe_level_db": -25},
        client,
    )
    data = json.loads(result[0].text)
    weights = data["amplitude_weights"]
    assert len(weights) == 10
    assert abs(max(weights) - 1.0) < 1e-6
    # Taylor weights should be symmetric
    for i in range(5):
        assert abs(weights[i] - weights[9 - i]) < 0.01


@pytest.mark.asyncio
async def test_taper_chebyshev(client: CSTClient):
    """Chebyshev taper generates valid symmetric weights."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_taper_design",
        {"num_elements": 8, "taper_type": "chebyshev", "sidelobe_level_db": -30},
        client,
    )
    data = json.loads(result[0].text)
    weights = data["amplitude_weights"]
    assert len(weights) == 8
    # Chebyshev weights should be symmetric
    for i in range(4):
        assert abs(weights[i] - weights[7 - i]) < 0.01


# ===================================================================
# 7. Grating lobe analysis tests
# ===================================================================


@pytest.mark.asyncio
async def test_grating_no_lobes_half_wave(client: CSTClient):
    """d/lambda=0.5 with 60-deg scan should have no grating lobes."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_grating_lobe_analysis",
        {"spacing_wavelengths": 0.5, "max_scan_angle_deg": 60},
        client,
    )
    data = json.loads(result[0].text)
    assert data["has_grating_lobes"] is False


@pytest.mark.asyncio
async def test_grating_lobes_full_wave(client: CSTClient):
    """d/lambda=1.0 should have grating lobes for any scan angle."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_grating_lobe_analysis",
        {"spacing_wavelengths": 1.0, "max_scan_angle_deg": 0},
        client,
    )
    data = json.loads(result[0].text)
    # d/lambda=1.0 vs max_safe = 1/(1+sin(0)) = 1.0
    # Condition is d >= max_safe, so 1.0 >= 1.0 => True
    assert data["has_grating_lobes"] is True


@pytest.mark.asyncio
async def test_grating_max_safe_spacing(client: CSTClient):
    """Max safe spacing should be 1/(1+sin(theta_max))."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_grating_lobe_analysis",
        {"spacing_wavelengths": 0.5, "max_scan_angle_deg": 30},
        client,
    )
    data = json.loads(result[0].text)
    expected = 1.0 / (1.0 + math.sin(math.radians(30)))
    assert abs(data["max_safe_spacing_wavelengths"] - expected) < 0.001


# ===================================================================
# 8. Mutual coupling tests
# ===================================================================


@pytest.mark.asyncio
async def test_mutual_coupling_vba(client: CSTClient):
    """Mutual coupling setup generates FDSolver and Port VBA."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_mutual_coupling",
        {"num_ports": 4},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba_script", "")
    assert "FDSolver" in vba
    assert "Port" in vba
    assert data["num_ports"] == 4
    assert data["port_numbers"] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_mutual_coupling_custom_ports(client: CSTClient):
    """Mutual coupling with explicit port numbers."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_mutual_coupling",
        {"num_ports": 3, "port_numbers": [2, 5, 7]},
        client,
    )
    data = json.loads(result[0].text)
    assert data["port_numbers"] == [2, 5, 7]
    assert "S(2,5) - coupling" in data["coupling_matrix_entries"]
    assert "S(2,2) - reflection" in data["coupling_matrix_entries"]


@pytest.mark.asyncio
async def test_mutual_coupling_s_param_count(client: CSTClient):
    """Number of unique S-parameters should be N*(N+1)/2."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_mutual_coupling",
        {"num_ports": 4},
        client,
    )
    data = json.loads(result[0].text)
    expected_count = 4 * 5 // 2  # 10
    assert data["total_s_parameters"] == expected_count


# ===================================================================
# Error handling tests
# ===================================================================


@pytest.mark.asyncio
async def test_unknown_tool_error(client: CSTClient):
    """Unknown tool name returns error."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle("cst_array_nonexistent", {}, client)
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "Unknown" in data["message"]


@pytest.mark.asyncio
async def test_invalid_axis_error(client: CSTClient):
    """Invalid axis returns error."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_linear",
        {"num_elements": 4, "spacing_mm": 10.0, "frequency_ghz": 5.0, "axis": "z"},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_mismatched_weights_error(client: CSTClient):
    """Mismatched weight count returns error."""
    from mcp_cst_studio.tools.arrays import handle

    result = await handle(
        "cst_array_compute_factor",
        {
            "num_elements": 4,
            "spacing_wavelengths": 0.5,
            "amplitude_weights": [1.0, 1.0],  # wrong count
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "length" in data["message"]
