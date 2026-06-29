"""Connected-mode tests — verify VBA dispatch hits modeler, not schematic.

Uses the ``mock_client`` fixture from conftest.py which patches CST_AVAILABLE
and provides a MagicMock project with ``modeler.execute_vba_code`` returning "ok".
"""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse(result) -> dict:
    """Extract the JSON dict from a list[TextContent] handler response."""
    assert len(result) >= 1
    return json.loads(result[0].text)


def _assert_executed(data: dict) -> None:
    """Assert a connected-mode VBA execution response."""
    assert data.get("status") == "executed", (
        f"Expected status='executed' in connected mode, got: {data}"
    )


# ===================================================================
# CSTClient unit tests (connected mode)
# ===================================================================


class TestClientExecuteVBA:
    """Test execute_vba dispatches to model3d.add_to_history."""

    def test_model3d_called(self, mock_client: CSTClient):
        result = mock_client.execute_vba("Sub Main\nEnd Sub")
        assert result["status"] == "executed"
        mock_client._project.model3d.add_to_history.assert_called_once()
        # Verify VBA code is the second positional arg
        call_args = mock_client._project.model3d.add_to_history.call_args
        assert call_args[0][1] == "Sub Main\nEnd Sub"

    def test_schematic_not_called(self, mock_client: CSTClient):
        mock_client.execute_vba("Sub Main\nEnd Sub")
        mock_client._project.schematic.execute_vba_code.assert_not_called()

    def test_model3d_exception_returns_error(self, mock_client: CSTClient):
        mock_client._project.model3d.add_to_history.side_effect = RuntimeError(
            "CST error"
        )
        result = mock_client.execute_vba("Sub Main\nEnd Sub")
        assert result["status"] == "error"
        assert "CST error" in result["message"]

    def test_model3d_attribute_error_falls_back_to_schematic(
        self, mock_client: CSTClient
    ):
        mock_client._project.model3d.add_to_history.side_effect = AttributeError(
            "no model3d"
        )
        mock_client._project.schematic.execute_vba_code.return_value = "ok"
        result = mock_client.execute_vba("Sub Main\nEnd Sub")
        assert result["status"] == "executed"
        mock_client._project.schematic.execute_vba_code.assert_called_once()

    def test_result_string_returned(self, mock_client: CSTClient):
        mock_client._project.model3d.add_to_history.return_value = "42"
        result = mock_client.execute_vba("Sub Main\nEnd Sub")
        assert result["result"] == "42"

    def test_none_result_returns_ok(self, mock_client: CSTClient):
        mock_client._project.model3d.add_to_history.return_value = None
        result = mock_client.execute_vba("Sub Main\nEnd Sub")
        assert result["result"] == "ok"


class TestClientNewProject:
    """Test new_project respects project_type parameter."""

    def test_mws_project_type(self, mock_client: CSTClient):
        mock_client._de = mock_client._project  # reuse mock as DE
        result = mock_client.new_project("/tmp/test.cst", "MWS")
        assert result["status"] == "created"
        assert result["type"] == "MWS"

    def test_ems_project_type(self, mock_client: CSTClient):
        from unittest.mock import MagicMock

        de = MagicMock()
        de.new_ems.return_value = MagicMock()
        de.new_ems.return_value.save.return_value = None
        mock_client._de = de
        result = mock_client.new_project("/tmp/test.cst", "EMS")
        assert result["status"] == "created"
        assert result["type"] == "EMS"
        de.new_ems.assert_called_once()


# ===================================================================
# Tool module connected-mode tests
# ===================================================================


class TestGeometryConnected:
    @pytest.mark.asyncio
    async def test_create_brick(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.geometry import handle

        result = await handle(
            "cst_create_brick",
            {
                "component": "Antenna",
                "name": "patch",
                "material": "PEC",
                "x_min": -10,
                "x_max": 10,
                "y_min": -10,
                "y_max": 10,
                "z_min": 0,
                "z_max": 0.035,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)
        mock_client._project.model3d.add_to_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_cylinder(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.geometry import handle

        result = await handle(
            "cst_create_cylinder",
            {
                "component": "Feed",
                "name": "probe",
                "material": "PEC",
                "axis": "z",
                "outer_radius": 0.5,
                "inner_radius": 0,
                "range_min": 0,
                "range_max": 1.6,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_create_sphere(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.geometry import handle

        result = await handle(
            "cst_create_sphere",
            {
                "component": "Antenna",
                "name": "ball",
                "material": "PEC",
                "center_x": 0,
                "center_y": 0,
                "center_z": 0,
                "radius": 5,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestBooleanConnected:
    @pytest.mark.asyncio
    async def test_boolean_add(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.boolean import handle

        result = await handle(
            "cst_boolean_add",
            {"solid1": "component1:solid1", "solid2": "component1:solid2"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_boolean_subtract(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.boolean import handle

        result = await handle(
            "cst_boolean_subtract",
            {"solid1": "component1:solid1", "solid2": "component1:solid2"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestTransformsConnected:
    @pytest.mark.asyncio
    async def test_translate(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.transforms import handle

        result = await handle(
            "cst_transform_translate",
            {"solid": "Antenna:patch", "dx": 5, "dy": 0, "dz": 0},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_rotate(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.transforms import handle

        result = await handle(
            "cst_transform_rotate",
            {"solid": "Antenna:patch", "angle": 45, "axis": "z", "center_x": 0, "center_y": 0, "center_z": 0},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestMaterialsConnected:
    @pytest.mark.asyncio
    async def test_create_material(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.materials import handle

        result = await handle(
            "cst_create_material",
            {"name": "Rogers4003C", "epsilon_r": 3.55, "mu_r": 1.0, "tan_d_e": 0.0027},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_assign_material(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.materials import handle

        result = await handle(
            "cst_assign_material",
            {"solid": "Antenna:substrate", "material": "Rogers4003C"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestPortsConnected:
    @pytest.mark.asyncio
    async def test_add_waveguide_port(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.ports import handle

        result = await handle(
            "cst_add_waveguide_port",
            {
                "port_number": 1,
                "orientation": "zmin",
                "x_min": -5,
                "x_max": 5,
                "y_min": -5,
                "y_max": 5,
                "z_min": 0,
                "z_max": 0,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_add_discrete_port(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.ports import handle

        result = await handle(
            "cst_add_discrete_port",
            {
                "port_number": 1,
                "x1": 0, "y1": 0, "z1": 0,
                "x2": 0, "y2": 0, "z2": 1.6,
                "impedance": 50,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestBoundariesConnected:
    @pytest.mark.asyncio
    async def test_set_boundary(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.boundaries import handle

        result = await handle(
            "cst_set_boundary",
            {
                "x_min": "open",
                "x_max": "open",
                "y_min": "open",
                "y_max": "open",
                "z_min": "electric",
                "z_max": "open",
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_set_frequency_range(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.boundaries import handle

        result = await handle(
            "cst_set_frequency_range",
            {"f_min": 1.0, "f_max": 5.0},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestMeshConnected:
    @pytest.mark.asyncio
    async def test_set_mesh_type(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.mesh import handle

        result = await handle(
            "cst_set_mesh_type",
            {"mesh_type": "Hexahedral"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_set_mesh_density(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.mesh import handle

        result = await handle(
            "cst_set_mesh_density",
            {"cells_per_wavelength": 20},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_add_mesh_refinement(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.mesh import handle

        result = await handle(
            "cst_add_mesh_refinement",
            {"component": "Antenna", "solid": "patch", "refinement_factor": 4},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestSolversConnected:
    @pytest.mark.asyncio
    async def test_configure_time_domain(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.solvers import handle

        result = await handle(
            "cst_configure_time_domain_solver",
            {"accuracy": -40, "max_time_steps": 20000},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_configure_frequency_domain(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.solvers import handle

        result = await handle(
            "cst_configure_frequency_domain_solver",
            {"f_min": 1.0, "f_max": 5.0, "samples": 501},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestSimulationConnected:
    @pytest.mark.asyncio
    async def test_run_simulation(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.simulation import handle

        result = await handle(
            "cst_run_simulation",
            {"solver_type": "Time Domain"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_stop_simulation(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.simulation import handle

        result = await handle(
            "cst_stop_simulation",
            {},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestResultsConnected:
    """Results tools use client.get_result() in connected mode (not execute_vba).

    Since cst.results is not available in the test env, get_result raises.
    We verify the tool doesn't return 'offline' status (it enters the
    connected branch) and handles the error gracefully.
    Field monitors use execute_vba, so they should return 'executed'.
    """

    @pytest.mark.asyncio
    async def test_get_s_parameters_enters_connected_branch(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.results import handle

        result = await handle(
            "cst_get_s_parameters",
            {"port_in": 1, "port_out": 1},
            mock_client,
        )
        data = _parse(result)
        # In connected mode, get_result is called (not offline VBA generation)
        assert data.get("status") != "offline"

    @pytest.mark.asyncio
    async def test_get_farfield_enters_connected_branch(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.results import handle

        result = await handle(
            "cst_get_farfield",
            {"frequency": 2.45},
            mock_client,
        )
        data = _parse(result)
        assert data.get("status") != "offline"

    @pytest.mark.asyncio
    async def test_get_vswr_enters_connected_branch(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.results import handle

        result = await handle(
            "cst_get_vswr",
            {},
            mock_client,
        )
        data = _parse(result)
        assert data.get("status") != "offline"

    @pytest.mark.asyncio
    async def test_add_field_monitor(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.results import handle

        result = await handle(
            "cst_add_field_monitor",
            {"monitor_type": "Efield", "frequency": 2.45},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestImportExportConnected:
    @pytest.mark.asyncio
    async def test_import_cad(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.import_export import handle

        result = await handle(
            "cst_import_cad",
            {"file_path": "/tmp/model.step", "format": "stp", "component": "Import"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_export_touchstone(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.import_export import handle

        result = await handle(
            "cst_export_touchstone",
            {"file_path": "/tmp/antenna.s1p", "format": "s1p"},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestParametersConnected:
    @pytest.mark.asyncio
    async def test_set_parameter(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.parameters import handle

        result = await handle(
            "cst_set_parameter",
            {"name": "patch_length", "value": 30.0},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_parameter_sweep(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.parameters import handle

        result = await handle(
            "cst_parameter_sweep",
            {
                "parameter": "patch_length",
                "start": 25,
                "stop": 35,
                "steps": 11,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_optimizer(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.parameters import handle

        result = await handle(
            "cst_optimizer",
            {
                "goal_type": "minimize",
                "result_path": "1D Results\\S-Parameters\\S1,1",
                "parameters": [
                    {"name": "patch_length", "min": 25, "max": 35},
                ],
                "method": "Trust Region",
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestAntennaTemplatesConnected:
    """Antenna templates are pure computation — they return vba_script
    regardless of connected/offline mode. Verify VBA is generated.
    """

    @pytest.mark.asyncio
    async def test_patch_antenna(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.antenna_templates import handle

        result = await handle(
            "cst_antenna_patch",
            {"frequency_ghz": 2.45, "epsilon_r": 4.4, "substrate_height_mm": 1.6},
            mock_client,
        )
        data = _parse(result)
        assert "vba_script" in data
        assert "Brick" in data["vba_script"]
        assert "calculated_parameters" in data

    @pytest.mark.asyncio
    async def test_dipole_antenna(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.antenna_templates import handle

        result = await handle(
            "cst_antenna_dipole",
            {"frequency_ghz": 1.0},
            mock_client,
        )
        data = _parse(result)
        assert "vba_script" in data
        assert "Cylinder" in data["vba_script"]

    @pytest.mark.asyncio
    async def test_horn_antenna(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.antenna_templates import handle

        result = await handle(
            "cst_antenna_horn",
            {"frequency_ghz": 10.0, "gain_dbi": 15},
            mock_client,
        )
        data = _parse(result)
        assert "vba_script" in data
        assert "Loft" in data["vba_script"]


class TestPCBConnected:
    @pytest.mark.asyncio
    async def test_create_stackup(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.pcb import handle

        result = await handle(
            "cst_pcb_create_stackup",
            {
                "layers": [
                    {"name": "Top", "type": "signal", "thickness_mm": 0.035, "material": "Copper", "epsilon_r": 1.0},
                    {"name": "Core", "type": "dielectric", "thickness_mm": 1.5, "material": "FR-4", "epsilon_r": 4.4},
                    {"name": "Bottom", "type": "ground", "thickness_mm": 0.035, "material": "Copper", "epsilon_r": 1.0},
                ],
                "board_width_mm": 50,
                "board_length_mm": 50,
            },
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)

    @pytest.mark.asyncio
    async def test_create_trace(self, mock_client: CSTClient):
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
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


class TestVBAConnected:
    @pytest.mark.asyncio
    async def test_execute_vba(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.vba import handle

        result = await handle(
            "cst_execute_vba",
            {"code": "MsgBox \"Hello\""},
            mock_client,
        )
        data = _parse(result)
        _assert_executed(data)


# ===================================================================
# Error handling in connected mode
# ===================================================================


class TestConnectedModeErrors:
    @pytest.mark.asyncio
    async def test_geometry_error_propagated(self, mock_client: CSTClient):
        """When model3d.add_to_history raises, the error should propagate."""
        mock_client._project.model3d.add_to_history.side_effect = RuntimeError(
            "CST internal error"
        )
        from mcp_cst_studio.tools.geometry import handle

        result = await handle(
            "cst_create_brick",
            {
                "component": "Test",
                "name": "fail",
                "material": "PEC",
                "x_min": 0, "x_max": 1,
                "y_min": 0, "y_max": 1,
                "z_min": 0, "z_max": 1,
            },
            mock_client,
        )
        data = _parse(result)
        assert data["status"] == "error"
        assert "CST internal error" in data["message"]

    @pytest.mark.asyncio
    async def test_antenna_invalid_input_returns_error(self, mock_client: CSTClient):
        """Antenna templates return error on invalid input."""
        from mcp_cst_studio.tools.antenna_templates import handle

        result = await handle(
            "cst_antenna_patch",
            {"frequency_ghz": -1, "epsilon_r": 4.4, "substrate_height_mm": 1.6},
            mock_client,
        )
        data = _parse(result)
        assert data.get("status") == "error"


# ===================================================================
# VBA content verification in connected mode
# ===================================================================


class TestVBAContentInConnectedMode:
    """Verify that the correct VBA is sent to modeler.execute_vba_code."""

    @pytest.mark.asyncio
    async def test_brick_vba_has_correct_objects(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.geometry import handle

        await handle(
            "cst_create_brick",
            {
                "component": "Antenna",
                "name": "substrate",
                "material": "FR-4",
                "x_min": -20, "x_max": 20,
                "y_min": -20, "y_max": 20,
                "z_min": 0, "z_max": 1.6,
            },
            mock_client,
        )
        vba = mock_client._project.model3d.add_to_history.call_args[0][1]
        assert "With Brick" in vba
        assert '"substrate"' in vba
        assert '"Antenna"' in vba
        assert '"FR-4"' in vba
        assert ".Create" in vba

    @pytest.mark.asyncio
    async def test_boundary_vba_correct(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.boundaries import handle

        await handle(
            "cst_set_frequency_range",
            {"f_min": 2.0, "f_max": 3.0},
            mock_client,
        )
        vba = mock_client._project.model3d.add_to_history.call_args[0][1]
        assert "FrequencyRange" in vba

    @pytest.mark.asyncio
    async def test_solver_vba_correct(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.solvers import handle

        await handle(
            "cst_configure_time_domain_solver",
            {"accuracy": -30},
            mock_client,
        )
        vba = mock_client._project.model3d.add_to_history.call_args[0][1]
        assert "Solver" in vba

    @pytest.mark.asyncio
    async def test_material_vba_correct(self, mock_client: CSTClient):
        from mcp_cst_studio.tools.materials import handle

        await handle(
            "cst_create_material",
            {"name": "TestMat", "epsilon_r": 2.2},
            mock_client,
        )
        vba = mock_client._project.model3d.add_to_history.call_args[0][1]
        assert "Material" in vba
        assert '"TestMat"' in vba
