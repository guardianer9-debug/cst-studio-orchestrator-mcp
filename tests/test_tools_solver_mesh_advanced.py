"""Tests for advanced solver, mesh, and boundary control tools (Phase 7)."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


# ---- Solver: cst_configure_eigenmode_advanced ----

@pytest.mark.asyncio
async def test_eigenmode_advanced_defaults(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle("cst_configure_eigenmode_advanced", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "EigenmodeSolver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver") == "Eigenmode (Advanced)"
    assert data.get("num_modes") == 5
    assert data.get("accuracy") == 1e-6
    assert data.get("solver_order") == 1


@pytest.mark.asyncio
async def test_eigenmode_advanced_with_frequency_estimate(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_eigenmode_advanced",
        {"num_modes": 10, "frequency_estimate_ghz": 2.45, "solver_order": 2},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "SetFrequencyTarget" in vba
    assert data.get("num_modes") == 10
    assert data.get("frequency_estimate_ghz") == 2.45
    assert data.get("solver_order") == 2


@pytest.mark.asyncio
async def test_eigenmode_advanced_invalid_num_modes(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_eigenmode_advanced",
        {"num_modes": 100},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "num_modes" in data.get("message", "")


# ---- Solver: cst_configure_ie_solver_advanced ----

@pytest.mark.asyncio
async def test_ie_solver_advanced_defaults(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle("cst_configure_ie_solver_advanced", {}, client)
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "IESolver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver") == "Integral Equation (Advanced)"
    assert data.get("preconditioner") == "ILU"
    assert data.get("mlfmm") is True


@pytest.mark.asyncio
async def test_ie_solver_advanced_custom(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_ie_solver_advanced",
        {
            "accuracy": 1e-4,
            "max_iterations": 500,
            "preconditioner": "Multilevel",
            "low_frequency_stabilization": True,
            "mlfmm": False,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "SetPreconditionerType" in vba
    assert "SetMLFMM" in vba
    assert data.get("preconditioner") == "Multilevel"
    assert data.get("low_frequency_stabilization") is True
    assert data.get("mlfmm") is False


@pytest.mark.asyncio
async def test_ie_solver_advanced_invalid_preconditioner(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_ie_solver_advanced",
        {"preconditioner": "InvalidType"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "preconditioner" in data.get("message", "").lower()


# ---- Solver: cst_configure_multilayer_solver ----

@pytest.mark.asyncio
async def test_multilayer_solver_defaults(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_multilayer_solver",
        {"f_min": 1.0, "f_max": 10.0},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "FDSolver" in vba
    assert "UseMultilayerSolver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver") == "Multilayer (Frequency Domain)"
    assert data.get("f_min_ghz") == 1.0
    assert data.get("f_max_ghz") == 10.0
    assert data.get("num_samples") == 501


@pytest.mark.asyncio
async def test_multilayer_solver_f_min_gte_f_max(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_multilayer_solver",
        {"f_min": 10.0, "f_max": 1.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "f_min" in data.get("message", "")


# ---- Mesh: cst_get_mesh_quality ----

@pytest.mark.asyncio
async def test_get_mesh_quality(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle("cst_get_mesh_quality", {}, client)
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"
    assert "expected_fields" in data
    assert "total_cells" in data["expected_fields"]
    assert "max_aspect_ratio" in data["expected_fields"]


# ---- Mesh: cst_set_pml_properties ----

@pytest.mark.asyncio
async def test_set_pml_properties_defaults(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle("cst_set_pml_properties", {}, client)
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Boundary" in vba
    assert data.get("status") == "offline"
    assert data.get("num_layers") == 4
    assert data.get("reflection_level_db") == -40


@pytest.mark.asyncio
async def test_set_pml_properties_custom(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_set_pml_properties",
        {"num_layers": 8, "reflection_level_db": -60},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("num_layers") == 8
    assert data.get("reflection_level_db") == -60


@pytest.mark.asyncio
async def test_set_pml_properties_invalid_layers(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_set_pml_properties",
        {"num_layers": 2},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "num_layers" in data.get("message", "")


# ---- Mesh: cst_add_fixpoint_mesh ----

@pytest.mark.asyncio
async def test_add_fixpoint_mesh(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_add_fixpoint_mesh",
        {"x": 1.0, "y": 2.0, "z": 3.0},
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Mesh" in vba
    assert data.get("status") == "offline"
    assert data.get("x") == 1.0
    assert data.get("y") == 2.0
    assert data.get("z") == 3.0


@pytest.mark.asyncio
async def test_add_fixpoint_mesh_with_name(client: CSTClient):
    from mcp_cst_studio.tools.mesh import handle

    result = await handle(
        "cst_add_fixpoint_mesh",
        {"x": 0, "y": 0, "z": 0, "name": "probe1"},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("name") == "probe1"
    vba = data.get("vba", "")
    assert "FixedPointName" in vba


# ---- Boundaries: cst_set_periodic_boundary ----

@pytest.mark.asyncio
async def test_set_periodic_boundary_defaults(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle("cst_set_periodic_boundary", {}, client)
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Boundary" in vba
    assert "periodic" in vba
    assert data.get("status") == "offline"
    assert data.get("boundary_type") == "periodic"
    assert data.get("phase_x_deg") == 0
    assert data.get("phase_y_deg") == 0


@pytest.mark.asyncio
async def test_set_periodic_boundary_with_phase(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_periodic_boundary",
        {"phase_x_deg": 30.0, "phase_y_deg": 45.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("phase_x_deg") == 30.0
    assert data.get("phase_y_deg") == 45.0


# ---- Boundaries: cst_set_floquet_port_advanced ----

@pytest.mark.asyncio
async def test_set_floquet_port_advanced_defaults(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle("cst_set_floquet_port_advanced", {}, client)
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "FloquetPort" in vba
    assert data.get("status") == "offline"
    assert data.get("num_modes") == 2
    assert data.get("scan_theta_deg") == 0
    assert data.get("scan_phi_deg") == 0


@pytest.mark.asyncio
async def test_set_floquet_port_advanced_with_scan(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_floquet_port_advanced",
        {"num_modes": 10, "scan_theta_deg": 30.0, "scan_phi_deg": 60.0},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("num_modes") == 10
    assert data.get("scan_theta_deg") == 30.0
    assert data.get("scan_phi_deg") == 60.0


@pytest.mark.asyncio
async def test_set_floquet_port_advanced_invalid_modes(client: CSTClient):
    from mcp_cst_studio.tools.boundaries import handle

    result = await handle(
        "cst_set_floquet_port_advanced",
        {"num_modes": 1},
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "num_modes" in data.get("message", "")


# ---- Ports: cst_add_multipin_port ----

@pytest.mark.asyncio
async def test_add_multipin_port(client: CSTClient):
    from mcp_cst_studio.tools.ports import handle

    result = await handle(
        "cst_add_multipin_port",
        {
            "port_number": 1,
            "orientation": "zmin",
            "x_min": -10,
            "x_max": 10,
            "y_min": -10,
            "y_max": 10,
            "z_min": 0,
            "z_max": 0,
            "num_modes": 4,
        },
        client,
    )
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Port" in vba
    assert "NumberOfModes" in vba
    assert data.get("status") == "offline"
    assert data.get("port_type") == "multipin"
    assert data.get("port_number") == 1
    assert data.get("num_modes") == 4


@pytest.mark.asyncio
async def test_add_multipin_port_invalid_modes(client: CSTClient):
    from mcp_cst_studio.tools.ports import handle

    result = await handle(
        "cst_add_multipin_port",
        {
            "port_number": 1,
            "orientation": "zmin",
            "x_min": -10,
            "x_max": 10,
            "y_min": -10,
            "y_max": 10,
            "z_min": 0,
            "z_max": 0,
            "num_modes": 15,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "num_modes" in data.get("message", "")
