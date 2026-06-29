"""Tests for advanced / dispersive material tools."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


# ---------------------------------------------------------------------------
# Debye material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_debye_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_debye_material",
        {
            "name": "WetSoil",
            "epsilon_inf": 5.0,
            "delta_epsilon": 20.0,
            "relaxation_time_ps": 9.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"WetSoil"' in vba
    assert "Debye 1st Order" in vba
    assert ".EpsilonInfinity" in vba
    assert ".DispEps" in vba
    assert ".DispCoeff0Eps" in vba


@pytest.mark.asyncio
async def test_create_debye_material_2nd_order(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_debye_material",
        {
            "name": "Water",
            "epsilon_inf": 4.9,
            "delta_epsilon": 75.0,
            "relaxation_time_ps": 8.3,
            "order": 2,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Debye 2nd Order" in vba


@pytest.mark.asyncio
async def test_create_debye_material_with_tan_d(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_debye_material",
        {
            "name": "LossySoil",
            "epsilon_inf": 3.0,
            "delta_epsilon": 10.0,
            "relaxation_time_ps": 12.0,
            "tan_d": 0.05,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert ".TanDe" in vba
    props = data["properties"]
    assert props["tan_d"] == 0.05


@pytest.mark.asyncio
async def test_create_debye_material_invalid_epsilon_inf(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_debye_material",
        {
            "name": "Bad",
            "epsilon_inf": -1.0,
            "delta_epsilon": 5.0,
            "relaxation_time_ps": 9.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# Lorentz material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_lorentz_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_lorentz_material",
        {
            "name": "OpticalGlass",
            "epsilon_inf": 2.25,
            "delta_epsilon": 1.5,
            "resonant_freq_ghz": 300.0,
            "damping_freq_ghz": 10.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"OpticalGlass"' in vba
    assert "Lorentz" in vba
    assert ".LorentzEpsInf" in vba
    assert ".LorentzDispEps" in vba
    assert ".LorentzFreqEps" in vba
    assert ".LorentzGamma0Eps" in vba


@pytest.mark.asyncio
async def test_create_lorentz_material_invalid_freq(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_lorentz_material",
        {
            "name": "Bad",
            "epsilon_inf": 2.0,
            "delta_epsilon": 1.0,
            "resonant_freq_ghz": -5.0,
            "damping_freq_ghz": 1.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# Drude material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_drude_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_drude_material",
        {
            "name": "DrudeGold",
            "plasma_freq_ghz": 2175000.0,
            "collision_freq_ghz": 6500.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"DrudeGold"' in vba
    assert "Drude" in vba
    assert ".DrudeFreqEps" in vba
    assert ".DrudeGammaEps" in vba


# ---------------------------------------------------------------------------
# Ferrite material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_ferrite_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_ferrite_material",
        {
            "name": "YIG",
            "epsilon_r": 15.0,
            "saturation_magnetization_ka_m": 140.0,
            "linewidth_oe": 25.0,
            "applied_field_ka_m": 80.0,
            "field_direction": "z",
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"YIG"' in vba
    assert "SetGyroMagneticModel" in vba
    assert "GyroMagneticSaturation" in vba
    assert "GyroMagneticLineWidth" in vba
    assert "GyroMagneticAppliedField" in vba
    assert "GyroMagneticFieldDirection" in vba


@pytest.mark.asyncio
async def test_create_ferrite_material_invalid_direction(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_ferrite_material",
        {
            "name": "BadFerrite",
            "epsilon_r": 12.0,
            "saturation_magnetization_ka_m": 300.0,
            "linewidth_oe": 100.0,
            "field_direction": "q",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# Temperature-dependent material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_temperature_dependent_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_temperature_dependent_material",
        {
            "name": "ThermalFR4",
            "epsilon_r": 4.4,
            "conductivity": 0.0,
            "temp_coeff_epsilon_ppm_k": -200.0,
            "temp_coeff_conductivity": 0.004,
            "reference_temp_c": 25.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"ThermalFR4"' in vba
    assert "ReferenceTemperature" in vba
    assert "TempCoeffEpsilon" in vba
    assert "TempCoeffConductivity" in vba
    props = data["properties"]
    assert props["epsilon_r"] == 4.4
    assert props["temp_coeff_epsilon_ppm_k"] == -200.0


# ---------------------------------------------------------------------------
# Cole-Cole material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_cole_cole_material(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_cole_cole_material",
        {
            "name": "MuscleTissue",
            "epsilon_inf": 4.0,
            "delta_epsilon": 50.0,
            "relaxation_time_ps": 7.2,
            "alpha": 0.1,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Material" in vba
    assert '"MuscleTissue"' in vba
    assert "Cole Cole 1st Order" in vba
    assert ".Alpha" in vba
    assert ".DispEps" in vba
    props = data["properties"]
    assert props["alpha"] == 0.1


@pytest.mark.asyncio
async def test_create_cole_cole_material_invalid_alpha(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_cole_cole_material",
        {
            "name": "BadTissue",
            "epsilon_inf": 4.0,
            "delta_epsilon": 50.0,
            "relaxation_time_ps": 7.2,
            "alpha": 1.5,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_create_cole_cole_material_alpha_zero(client: CSTClient):
    """Alpha=0 should reduce to Debye model (valid edge case)."""
    from mcp_cst_studio.tools.materials import handle

    result = await handle(
        "cst_create_cole_cole_material",
        {
            "name": "DebyeEquivalent",
            "epsilon_inf": 3.0,
            "delta_epsilon": 20.0,
            "relaxation_time_ps": 9.0,
            "alpha": 0.0,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert "vba" in data
    assert data["properties"]["alpha"] == 0.0


# ---------------------------------------------------------------------------
# Ferrite database listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_ferrite_materials(client: CSTClient):
    from mcp_cst_studio.tools.materials import handle

    result = await handle("cst_list_ferrite_materials", {}, client)
    data = json.loads(result[0].text)
    assert data["tool"] == "cst_list_ferrite_materials"
    assert data["count"] == 5
    ferrites = data["ferrites"]
    names = [f["name"] for f in ferrites]
    assert "YIG (Yttrium Iron Garnet)" in names
    assert "NiZn Ferrite" in names
    # Verify structure of each entry
    for f in ferrites:
        assert "epsilon_r" in f
        assert "saturation_magnetization_ka_m" in f
        assert "linewidth_oe" in f
        assert "notes" in f
