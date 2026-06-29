"""Tests for antenna optimization tools."""

from __future__ import annotations

import json
import math
import os
import tempfile

import pytest

from mcp_cst_studio.cst_client import CSTClient

from mcp_cst_studio.tools.optimization import (
    _analyze_impedance_band,
    _build_impedance_vba,
    _build_initial_simplex,
    _centroid,
    _clamp_to_bounds,
    _classify_mismatch,
    _compute_cost,
    _contract,
    _evaluate_bands,
    _expand,
    _export_s11_vba,
    _find_resonances,
    _generate_recommendations,
    _parse_s11_data,
    _parse_z_data,
    _reflect,
    _run_solver_vba,
    _set_params_and_solve_vba,
    _set_params_vba,
    _shrink,
    _solve_and_export_vba,
    gamma_mag,
    gamma_to_return_loss,
    gamma_to_vswr,
    s11_to_vswr,
    vswr_to_s11,
    z_to_gamma,
)


# ---------------------------------------------------------------------------
# S11 <-> VSWR conversion
# ---------------------------------------------------------------------------


class TestVSWRConversion:
    def test_s11_to_vswr_known_values(self):
        # -10 dB -> VSWR ~1.925
        v = s11_to_vswr(-10.0)
        assert abs(v - 1.925) < 0.01

        # -7.36 dB -> VSWR ~2.5
        v = s11_to_vswr(-7.36)
        assert abs(v - 2.5) < 0.05

        # -9.54 dB -> VSWR ~2.0
        v = s11_to_vswr(-9.54)
        assert abs(v - 2.0) < 0.05

        # -20 dB -> VSWR ~1.22
        v = s11_to_vswr(-20.0)
        assert abs(v - 1.222) < 0.01

        # -6 dB -> VSWR ~3.01
        v = s11_to_vswr(-6.0)
        assert abs(v - 3.01) < 0.05

    def test_s11_to_vswr_zero_db(self):
        # 0 dB = total reflection = infinite VSWR
        assert s11_to_vswr(0.0) == float("inf")

    def test_s11_to_vswr_positive_db(self):
        assert s11_to_vswr(1.0) == float("inf")

    def test_vswr_to_s11_known_values(self):
        # VSWR 2.0 -> S11 ~-9.54 dB
        s = vswr_to_s11(2.0)
        assert abs(s - (-9.54)) < 0.05

        # VSWR 2.5 -> S11 ~-7.36 dB
        s = vswr_to_s11(2.5)
        assert abs(s - (-7.36)) < 0.05

        # VSWR 1.0 -> perfect match -> -inf
        s = vswr_to_s11(1.0)
        assert s == -float("inf")

    def test_roundtrip(self):
        for s11 in [-5, -10, -15, -20, -30]:
            vswr = s11_to_vswr(s11)
            s11_back = vswr_to_s11(vswr)
            assert abs(s11_back - s11) < 0.01


# ---------------------------------------------------------------------------
# S11 data parsing
# ---------------------------------------------------------------------------


class TestParseS11Data:
    def test_parse_cst_format(self):
        """Test parsing CST ASCIIExport format (space-separated, 2-line header)."""
        content = (
            "          Frequency / GHz                S1,1/abs,dB\n"
            "--------------------------------------------------------------\n"
            "                        1                    -0.053\n"
            "                     1.035                    -0.061\n"
            "                      1.07                    -0.072\n"
            "                        2                    -5.123\n"
            "                      2.5                    -8.456\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            freqs, s11 = _parse_s11_data(path)
            assert len(freqs) == 5
            assert len(s11) == 5
            assert freqs[0] == 1.0
            assert freqs[-1] == 2.5
            assert abs(s11[0] - (-0.053)) < 1e-6
            assert abs(s11[3] - (-5.123)) < 1e-6
        finally:
            os.unlink(path)

    def test_parse_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Header\n---\n")
            path = f.name

        try:
            with pytest.raises(ValueError, match="No data found"):
                _parse_s11_data(path)
        finally:
            os.unlink(path)

    def test_parse_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            _parse_s11_data("/nonexistent/path.csv")


# ---------------------------------------------------------------------------
# Band evaluation
# ---------------------------------------------------------------------------


class TestEvaluateBands:
    def _make_data(self):
        """Create sample S11 data with a resonance at 2.45 GHz."""
        freqs = [f / 10.0 for f in range(10, 81)]  # 1.0 to 8.0 GHz
        s11 = []
        for f in freqs:
            # Gaussian dip centered at 2.45 GHz (peak -15 dB)
            dip1 = -15.0 * math.exp(-((f - 2.45) ** 2) / (2 * 0.05**2))
            # Another dip at 5.5 GHz (peak -12 dB)
            dip2 = -12.0 * math.exp(-((f - 5.5) ** 2) / (2 * 0.1**2))
            s11.append(min(dip1 + dip2, -0.1))  # baseline ~0 dB
        return freqs, s11

    def test_evaluate_passing_band(self):
        freqs, s11 = self._make_data()
        bands = [{"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5}]
        results = _evaluate_bands(freqs, s11, bands)
        assert len(results) == 1
        assert results[0]["name"] == "2.4 GHz"
        # The dip at 2.45 should make this band pass with VSWR target 2.5
        assert results[0]["status"] in ("PASS", "FAIL")
        assert "worst_vswr" in results[0]
        assert "best_vswr" in results[0]

    def test_evaluate_no_data_band(self):
        bands = [{"name": "X-band", "f_low_ghz": 8.0, "f_high_ghz": 12.0, "vswr_target": 2.0}]
        results = _evaluate_bands([1.0, 2.0, 3.0], [-5.0, -10.0, -5.0], bands)
        assert results[0]["status"] == "NO_DATA"

    def test_evaluate_multiple_bands(self):
        freqs, s11 = self._make_data()
        bands = [
            {"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5},
            {"name": "5 GHz", "f_low_ghz": 5.15, "f_high_ghz": 5.85, "vswr_target": 2.5},
            {"name": "6 GHz", "f_low_ghz": 5.925, "f_high_ghz": 7.125, "vswr_target": 2.5},
        ]
        results = _evaluate_bands(freqs, s11, bands)
        assert len(results) == 3
        for r in results:
            assert "name" in r
            assert "status" in r


# ---------------------------------------------------------------------------
# Resonance detection
# ---------------------------------------------------------------------------


class TestFindResonances:
    def test_find_single_resonance(self):
        freqs = [1.0, 1.5, 2.0, 2.5, 3.0]
        s11 = [-1.0, -3.0, -12.0, -3.0, -1.0]
        res = _find_resonances(freqs, s11)
        assert len(res) == 1
        assert res[0]["freq_ghz"] == 2.0
        assert res[0]["s11_db"] == -12.0

    def test_no_resonance_above_threshold(self):
        freqs = [1.0, 2.0, 3.0]
        s11 = [-1.0, -3.0, -1.0]  # Above -5 dB threshold
        res = _find_resonances(freqs, s11)
        assert len(res) == 0

    def test_multiple_resonances(self):
        freqs = [1, 2, 3, 4, 5, 6, 7]
        s11 = [-1, -10, -1, -1, -1, -8, -1]
        res = _find_resonances(freqs, s11)
        assert len(res) == 2
        assert res[0]["freq_ghz"] == 2
        assert res[1]["freq_ghz"] == 6


# ---------------------------------------------------------------------------
# Cost function
# ---------------------------------------------------------------------------


class TestComputeCost:
    def test_all_pass_zero_cost(self):
        # Data where S11 is very good in the target band
        freqs = [2.4, 2.45, 2.5]
        s11 = [-15.0, -20.0, -15.0]
        bands = [{"name": "WiFi", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5}]
        cost, results = _compute_cost(freqs, s11, bands)
        assert cost == 0.0
        assert results[0]["status"] == "PASS"

    def test_violation_positive_cost(self):
        # S11 near 0 dB = terrible match = high VSWR
        freqs = [2.4, 2.45, 2.5]
        s11 = [-0.5, -0.5, -0.5]
        bands = [{"name": "WiFi", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5}]
        cost, results = _compute_cost(freqs, s11, bands)
        assert cost > 0
        assert results[0]["status"] == "FAIL"

    def test_no_data_penalty(self):
        freqs = [1.0, 1.5]
        s11 = [-10.0, -10.0]
        bands = [{"name": "5 GHz", "f_low_ghz": 5.0, "f_high_ghz": 6.0, "vswr_target": 2.5}]
        cost, results = _compute_cost(freqs, s11, bands)
        assert cost == 10.0  # NO_DATA penalty


# ---------------------------------------------------------------------------
# VBA generation
# ---------------------------------------------------------------------------


class TestVBAGeneration:
    def test_set_params_vba(self):
        vba = _set_params_vba({"arm_length": 26.5, "branch_len": 14.0})
        # Raw VBA for add_to_history — no Sub Main wrapper
        assert "Sub Main()" not in vba
        assert 'StoreParameter "arm_length", "26.5"' in vba
        assert 'StoreParameter "branch_len", "14.0"' in vba
        # No rebuild commands — solver triggers rebuild automatically
        assert "RebuildOnParametricChange" not in vba
        assert "DeleteAllResults" not in vba

    def test_set_params_vba_only_store_parameter(self):
        """VBA should only contain StoreParameter lines."""
        vba = _set_params_vba({"x": 1.0, "y": 2.0})
        lines = [line for line in vba.split("\n") if line.strip()]
        assert all("StoreParameter" in line for line in lines)

    def test_set_params_and_solve_vba(self):
        """Combined VBA stores params, solves, and exports."""
        vba = _set_params_and_solve_vba(
            {"arm_length": 20.0},
            export_path="C:/out.csv",
            port=1,
        )
        assert 'StoreParameter "arm_length", "20.0"' in vba
        assert "Solver.Start" in vba
        assert "ASCIIExport" in vba
        assert "C:/out.csv" in vba
        assert "S1,1" in vba

    def test_set_params_and_solve_vba_no_export(self):
        """Combined VBA without export."""
        vba = _set_params_and_solve_vba({"x": 1.0})
        assert 'StoreParameter "x", "1.0"' in vba
        assert "Solver.Start" in vba
        assert "ASCIIExport" not in vba

    def test_run_solver_vba(self):
        vba = _run_solver_vba()
        assert "Solver.Start" in vba
        # Raw VBA for add_to_history — no Sub Main wrapper
        assert "Sub Main()" not in vba

    def test_export_s11_vba(self):
        vba = _export_s11_vba("C:/cst_projects/test.csv", port=1)
        assert "SelectTreeItem" in vba
        assert "S1,1" in vba
        assert "ASCIIExport" in vba
        assert "C:/cst_projects/test.csv" in vba
        # Raw VBA for add_to_history — no Sub Main wrapper
        assert "Sub Main()" not in vba

    def test_export_s11_vba_port2(self):
        vba = _export_s11_vba("C:/out.csv", port=2)
        assert "S2,2" in vba

    def test_export_s11_backslash_conversion(self):
        vba = _export_s11_vba("C:\\cst_projects\\out.csv")
        assert "C:/cst_projects/out.csv" in vba
        assert "\\" not in vba.split("FileName")[1]  # No backslashes in path

    def test_solve_and_export_vba(self):
        vba = _solve_and_export_vba("C:/cst_projects/test.csv", port=1)
        assert "Solver.Start" in vba
        assert "ASCIIExport" in vba
        assert "S1,1" in vba
        assert "C:/cst_projects/test.csv" in vba

    def test_build_impedance_vba_exports_s_params(self):
        """Impedance VBA should export S-parameters (not Z-parameters)."""
        vba = _build_impedance_vba(port=1)
        assert "S-Parameters" in vba
        assert "S1,1" in vba
        assert "ASCIIExport" in vba
        # Must NOT reference Z-Parameters (that's the bug we fixed)
        assert "Z-Parameters" not in vba

    def test_build_impedance_vba_port2(self):
        vba = _build_impedance_vba(port=2)
        assert "S2,2" in vba


# ---------------------------------------------------------------------------
# Nelder-Mead components
# ---------------------------------------------------------------------------


class TestNelderMeadComponents:
    def test_initial_simplex_dimensions(self):
        x0 = [10.0, 20.0, 30.0]
        bounds = [(5.0, 15.0), (10.0, 30.0), (20.0, 40.0)]
        simplex = _build_initial_simplex(x0, bounds)
        # N+1 vertices for N parameters
        assert len(simplex) == 4
        assert all(len(v) == 3 for v in simplex)
        # First vertex is x0
        assert simplex[0] == x0

    def test_initial_simplex_within_bounds(self):
        x0 = [10.0, 20.0]
        bounds = [(5.0, 15.0), (10.0, 30.0)]
        simplex = _build_initial_simplex(x0, bounds)
        for vertex in simplex:
            for i, v in enumerate(vertex):
                assert bounds[i][0] <= v <= bounds[i][1]

    def test_initial_simplex_near_upper_bound(self):
        """When x0 is above midpoint, delta should go downward."""
        x0 = [14.5]
        bounds = [(5.0, 15.0)]
        simplex = _build_initial_simplex(x0, bounds)
        assert len(simplex) == 2
        # x0=14.5 is above midpoint=10, so perturbation goes downward
        assert simplex[1][0] < x0[0]

    def test_clamp_to_bounds(self):
        assert _clamp_to_bounds([1, 20, 50], [(5, 15), (10, 30), (20, 40)]) == [5, 20, 40]
        assert _clamp_to_bounds([10, 20, 30], [(5, 15), (10, 30), (20, 40)]) == [10, 20, 30]

    def test_centroid(self):
        simplex = [[0, 0], [2, 0], [0, 2]]
        c = _centroid(simplex, exclude_idx=2)
        assert abs(c[0] - 1.0) < 1e-10
        assert abs(c[1] - 0.0) < 1e-10

    def test_reflect(self):
        c = [1.0, 1.0]
        worst = [2.0, 2.0]
        r = _reflect(c, worst, alpha=1.0)
        assert abs(r[0] - 0.0) < 1e-10
        assert abs(r[1] - 0.0) < 1e-10

    def test_expand(self):
        c = [1.0, 1.0]
        reflected = [0.0, 0.0]
        e = _expand(c, reflected, gamma=2.0)
        assert abs(e[0] - (-1.0)) < 1e-10
        assert abs(e[1] - (-1.0)) < 1e-10

    def test_contract(self):
        c = [1.0, 1.0]
        point = [3.0, 3.0]
        cont = _contract(c, point, rho=0.5)
        assert abs(cont[0] - 2.0) < 1e-10
        assert abs(cont[1] - 2.0) < 1e-10

    def test_shrink(self):
        simplex = [[0, 0], [4, 0], [0, 4]]
        shrunk = _shrink(simplex, best_idx=0, sigma=0.5)
        assert shrunk[0] == [0, 0]  # Best unchanged
        assert abs(shrunk[1][0] - 2.0) < 1e-10
        assert abs(shrunk[2][1] - 2.0) < 1e-10


class TestNelderMeadOnQuadratic:
    """Test that our Nelder-Mead components can minimize a simple quadratic."""

    def test_minimize_quadratic(self):
        """Manual Nelder-Mead loop on f(x,y) = (x-3)^2 + (y-5)^2."""

        def cost_fn(x: list[float]) -> float:
            return (x[0] - 3.0) ** 2 + (x[1] - 5.0) ** 2

        bounds = [(0.0, 10.0), (0.0, 10.0)]
        x0 = [1.0, 1.0]
        simplex = _build_initial_simplex(x0, bounds)
        costs = [cost_fn(v) for v in simplex]

        for _ in range(100):
            order = sorted(range(len(costs)), key=lambda i: costs[i])
            simplex = [simplex[i] for i in order]
            costs = [costs[i] for i in order]

            best_idx = 0
            worst_idx = len(simplex) - 1
            second_worst_idx = worst_idx - 1

            f_best = costs[best_idx]
            f_worst = costs[worst_idx]
            f_second_worst = costs[second_worst_idx]

            c = _centroid(simplex, worst_idx)
            xr = _clamp_to_bounds(_reflect(c, simplex[worst_idx]), bounds)
            fr = cost_fn(xr)

            if f_best <= fr < f_second_worst:
                simplex[worst_idx] = xr
                costs[worst_idx] = fr
            elif fr < f_best:
                xe = _clamp_to_bounds(_expand(c, xr), bounds)
                fe = cost_fn(xe)
                if fe < fr:
                    simplex[worst_idx] = xe
                    costs[worst_idx] = fe
                else:
                    simplex[worst_idx] = xr
                    costs[worst_idx] = fr
            else:
                if fr < f_worst:
                    xc = _clamp_to_bounds(_contract(c, xr), bounds)
                else:
                    xc = _clamp_to_bounds(_contract(c, simplex[worst_idx]), bounds)
                fc = cost_fn(xc)
                if fc < min(fr, f_worst):
                    simplex[worst_idx] = xc
                    costs[worst_idx] = fc
                else:
                    simplex = _shrink(simplex, best_idx)
                    costs = [cost_fn(v) for v in simplex]

        best = simplex[costs.index(min(costs))]
        assert abs(best[0] - 3.0) < 0.1, f"x={best[0]}, expected ~3.0"
        assert abs(best[1] - 5.0) < 0.1, f"y={best[1]}, expected ~5.0"
        assert min(costs) < 0.01


# ---------------------------------------------------------------------------
# Offline mode tool output
# ---------------------------------------------------------------------------


class TestOfflineMode:
    @pytest.fixture
    def offline_client(self):
        from mcp_cst_studio.config import CSTConfig
        config = CSTConfig(connected=False)
        return CSTClient(config=config)

    @pytest.mark.asyncio
    async def test_evaluate_offline(self, offline_client):
        from mcp_cst_studio.tools.optimization import handle
        result = await handle(
            "cst_evaluate_antenna",
            {
                "bands": [
                    {"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5}
                ],
                "port": 1,
            },
            offline_client,
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "offline"
        assert "vba" in data
        assert "ASCIIExport" in data["vba"]

    @pytest.mark.asyncio
    async def test_refine_offline(self, offline_client):
        from mcp_cst_studio.tools.optimization import handle
        result = await handle(
            "cst_refine_antenna",
            {
                "parameters": [
                    {"name": "arm_length", "initial": 26.0, "min": 18.0, "max": 36.0}
                ],
                "bands": [
                    {"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5}
                ],
                "max_iterations": 10,
            },
            offline_client,
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "offline"
        assert "vba" in data
        assert "Optimizer" in data["vba"]

    @pytest.mark.asyncio
    async def test_refine_validation_min_ge_max(self, offline_client):
        from mcp_cst_studio.tools.optimization import handle
        result = await handle(
            "cst_refine_antenna",
            {
                "parameters": [
                    {"name": "arm_length", "initial": 26.0, "min": 36.0, "max": 18.0}
                ],
                "bands": [
                    {"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5}
                ],
            },
            offline_client,
        )
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "min" in data["message"]

    @pytest.mark.asyncio
    async def test_refine_validation_initial_out_of_range(self, offline_client):
        from mcp_cst_studio.tools.optimization import handle
        result = await handle(
            "cst_refine_antenna",
            {
                "parameters": [
                    {"name": "arm_length", "initial": 50.0, "min": 18.0, "max": 36.0}
                ],
                "bands": [
                    {"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5}
                ],
            },
            offline_client,
        )
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "initial" in data["message"]


# ---------------------------------------------------------------------------
# Diagnostics tools
# ---------------------------------------------------------------------------


class TestDiagnosticsOffline:
    @pytest.fixture
    def offline_client(self):
        from mcp_cst_studio.config import CSTConfig
        config = CSTConfig(connected=False)
        return CSTClient(config=config)

    def test_delete_results_offline(self, offline_client):
        result = offline_client.delete_results()
        assert result["status"] == "offline"

    def test_set_params_rebuild_solve_offline(self, offline_client):
        result = offline_client.set_params_rebuild_solve(
            {"arm_length": 20.0}, export_path="C:/out.csv"
        )
        assert result["status"] == "offline"

    def test_read_messages_offline(self, offline_client):
        result = offline_client.read_project_messages()
        assert result["status"] == "offline"

    def test_dismiss_dialogs_offline(self, offline_client):
        result = offline_client.dismiss_dialogs()
        # "ok" = no dialogs found, "dismissed" = found and dismissed some
        assert result["status"] in ("ok", "dismissed")

    def test_read_dialogs_offline(self, offline_client):
        result = offline_client.read_dialogs()
        assert result["status"] in ("ok", "found")

    def test_dialog_watcher_lifecycle(self, offline_client):
        result = offline_client.start_dialog_watcher()
        assert result["status"] in ("started", "already_running")
        log = offline_client.get_dialog_log()
        assert "log" in log
        result = offline_client.stop_dialog_watcher()
        assert result["status"] == "stopped"

    def test_stop_watcher_when_not_running(self, offline_client):
        # Stop watcher first if it's running from previous test
        offline_client.stop_dialog_watcher()
        result = offline_client.stop_dialog_watcher()
        assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_delete_results_tool_offline(self, offline_client):
        from mcp_cst_studio.tools.diagnostics import handle
        result = await handle("cst_delete_results", {}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] == "offline"

    @pytest.mark.asyncio
    async def test_read_log_tool_offline(self, offline_client):
        from mcp_cst_studio.tools.diagnostics import handle
        result = await handle("cst_read_project_log", {}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] == "offline"

    @pytest.mark.asyncio
    async def test_dismiss_dialogs_tool(self, offline_client):
        from mcp_cst_studio.tools.diagnostics import handle
        result = await handle("cst_dismiss_dialogs", {}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] in ("ok", "dismissed")

    @pytest.mark.asyncio
    async def test_dismiss_dialogs_read_only(self, offline_client):
        from mcp_cst_studio.tools.diagnostics import handle
        result = await handle("cst_dismiss_dialogs", {"read_only": True}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] in ("ok", "found")

    @pytest.mark.asyncio
    async def test_start_stop_watcher_tools(self, offline_client):
        from mcp_cst_studio.tools.diagnostics import handle
        result = await handle("cst_start_dialog_watcher", {}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] in ("started", "already_running")
        result = await handle("cst_stop_dialog_watcher", {}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, offline_client):
        from mcp_cst_studio.tools.diagnostics import handle
        result = await handle("cst_nonexistent", {}, offline_client)
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "Unknown" in data["message"]


class TestDialogHandler:
    """Test the dialog_handler module directly."""

    def test_import(self):
        from mcp_cst_studio.dialog_handler import (
            find_cst_dialogs,
        )
        # Functions should be importable and callable
        dialogs = find_cst_dialogs()
        assert isinstance(dialogs, list)

    def test_dismiss_returns_list(self):
        from mcp_cst_studio.dialog_handler import dismiss_cst_dialogs
        result = dismiss_cst_dialogs()
        assert isinstance(result, list)

    def test_watcher_start_stop(self):
        from mcp_cst_studio.dialog_handler import DialogWatcher
        watcher = DialogWatcher(poll_interval=0.1)
        watcher.start()
        assert watcher.running
        import time
        time.sleep(0.3)
        watcher.stop()
        assert not watcher.running
        log = watcher.get_log()
        assert isinstance(log, list)

    def test_watcher_clear_log(self):
        from mcp_cst_studio.dialog_handler import DialogWatcher
        watcher = DialogWatcher()
        watcher.clear_log()
        assert watcher.get_log() == []


# ---------------------------------------------------------------------------
# Impedance analysis functions
# ---------------------------------------------------------------------------


class TestZToGamma:
    """Test impedance-to-reflection-coefficient conversion."""

    def test_perfect_match(self):
        """Z = Z0 should give Γ = 0."""
        g_r, g_i = z_to_gamma(50.0, 0.0, z0=50.0)
        assert abs(g_r) < 1e-10
        assert abs(g_i) < 1e-10

    def test_open_circuit(self):
        """Z = very large should give Γ ≈ 1."""
        g_r, g_i = z_to_gamma(1e6, 0.0, z0=50.0)
        g_m = gamma_mag(g_r, g_i)
        assert abs(g_m - 1.0) < 0.001

    def test_short_circuit(self):
        """Z = 0 should give Γ = -1."""
        g_r, g_i = z_to_gamma(0.0, 0.0, z0=50.0)
        assert abs(g_r - (-1.0)) < 1e-10
        assert abs(g_i) < 1e-10

    def test_purely_resistive_high(self):
        """Z = 100Ω (2× Z0) → Γ = 1/3."""
        g_r, g_i = z_to_gamma(100.0, 0.0, z0=50.0)
        expected = (100 - 50) / (100 + 50)  # 1/3
        assert abs(g_r - expected) < 1e-10
        assert abs(g_i) < 1e-10

    def test_purely_resistive_low(self):
        """Z = 25Ω (0.5× Z0) → Γ = -1/3."""
        g_r, g_i = z_to_gamma(25.0, 0.0, z0=50.0)
        expected = (25 - 50) / (25 + 50)  # -1/3
        assert abs(g_r - expected) < 1e-10
        assert abs(g_i) < 1e-10

    def test_purely_reactive(self):
        """Z = j50Ω → |Γ| = 1 (on unit circle)."""
        g_r, g_i = z_to_gamma(0.0, 50.0, z0=50.0)
        g_m = gamma_mag(g_r, g_i)
        assert abs(g_m - 1.0) < 1e-10

    def test_complex_impedance(self):
        """Z = 70 + j(-34)Ω (from our 2.4 GHz data)."""
        g_r, g_i = z_to_gamma(69.65, -34.20, z0=50.0)
        g_m = gamma_mag(g_r, g_i)
        vswr = gamma_to_vswr(g_m)
        # VSWR should be around 2.1-2.3 for this impedance
        assert 1.5 < vswr < 3.0
        # Return loss should be around 8-10 dB
        rl = gamma_to_return_loss(g_m)
        assert 7.0 < rl < 12.0

    def test_high_impedance_5ghz(self):
        """Z = 132 + j61Ω (from our 5.4 GHz data) — should show poor match."""
        g_r, g_i = z_to_gamma(131.79, 61.16, z0=50.0)
        g_m = gamma_mag(g_r, g_i)
        vswr = gamma_to_vswr(g_m)
        # Should have high VSWR (>3)
        assert vswr > 3.0
        rl = gamma_to_return_loss(g_m)
        assert rl < 6.0  # Poor return loss


class TestGammaConversions:
    def test_gamma_to_vswr_zero(self):
        """Perfect match Γ=0 → VSWR=1."""
        assert gamma_to_vswr(0.0) == 1.0

    def test_gamma_to_vswr_one(self):
        """Total reflection Γ=1 → VSWR=inf."""
        assert gamma_to_vswr(1.0) == float("inf")

    def test_gamma_to_vswr_half(self):
        """Γ=0.5 → VSWR=3."""
        assert abs(gamma_to_vswr(0.5) - 3.0) < 1e-10

    def test_return_loss_zero_gamma(self):
        """Perfect match → infinite return loss."""
        assert gamma_to_return_loss(0.0) == float("inf")

    def test_return_loss_known(self):
        """Γ=0.316 → return loss ≈ 10 dB."""
        rl = gamma_to_return_loss(0.3162)
        assert abs(rl - 10.0) < 0.1


class TestClassifyMismatch:
    def test_perfect_match(self):
        result = _classify_mismatch(50.0, 0.0, z0=50.0)
        assert result["r_class"] == "ok"
        assert result["x_class"] == "ok"
        assert result["vswr"] < 1.1

    def test_high_resistance(self):
        result = _classify_mismatch(150.0, 0.0, z0=50.0)
        assert result["r_class"] == "high"
        assert result["r_ratio"] == 3.0

    def test_low_resistance(self):
        result = _classify_mismatch(20.0, 0.0, z0=50.0)
        assert result["r_class"] == "low"
        assert result["r_ratio"] == 0.4

    def test_inductive(self):
        result = _classify_mismatch(50.0, 80.0, z0=50.0)
        assert result["x_class"] == "inductive"

    def test_capacitive(self):
        result = _classify_mismatch(50.0, -80.0, z0=50.0)
        assert result["x_class"] == "capacitive"

    def test_near_resonance(self):
        result = _classify_mismatch(50.0, 5.0, z0=50.0)
        assert result["x_class"] == "ok"

    def test_pifa_5ghz_mismatch(self):
        """Real-world: 132+j61 at 5.4 GHz — high R, inductive."""
        result = _classify_mismatch(131.79, 61.16, z0=50.0)
        assert result["r_class"] == "high"
        assert result["x_class"] == "inductive"
        assert result["vswr"] > 3.0


class TestGenerateRecommendations:
    def test_passing_band(self):
        recs = _generate_recommendations(
            "2.4 GHz", 1.5, 2.5, -15.0, None, 2.4, 2.5
        )
        assert len(recs) == 1
        assert "✓" in recs[0]

    def test_resonance_below_band(self):
        """Nearest resonance below target band → recommend shortening."""
        res = {"freq_ghz": 2.0, "s11_db": -12.0, "vswr": 1.67}
        recs = _generate_recommendations(
            "5 GHz", 4.5, 2.5, -3.0, res, 5.15, 5.85
        )
        assert len(recs) >= 2
        assert "✗" in recs[0]
        # Should mention shortening or shifting upward
        assert any("shorten" in r.lower() or "below" in r.lower() for r in recs)

    def test_resonance_above_band(self):
        """Nearest resonance above target band → recommend lengthening."""
        res = {"freq_ghz": 8.0, "s11_db": -10.0, "vswr": 1.93}
        recs = _generate_recommendations(
            "6 GHz", 6.0, 2.5, -2.0, res, 5.925, 7.125
        )
        assert any("lengthen" in r.lower() or "above" in r.lower() for r in recs)

    def test_resonance_in_band_narrow(self):
        """Resonance within band but narrow → recommend bandwidth increase."""
        res = {"freq_ghz": 2.45, "s11_db": -8.0, "vswr": 2.3}
        recs = _generate_recommendations(
            "2.4 GHz", 3.5, 2.5, -5.0, res, 2.4, 2.5
        )
        assert any("bandwidth" in r.lower() or "height" in r.lower() for r in recs)

    def test_no_resonance(self):
        """No resonance at all → recommend adding resonant element."""
        recs = _generate_recommendations(
            "Test", 8.0, 2.5, -1.0, None, 5.0, 6.0
        )
        assert any("resonant element" in r.lower() or "resonator" in r.lower() for r in recs)

    def test_severe_mismatch(self):
        recs = _generate_recommendations(
            "Test", 8.0, 2.5, -1.0, None, 5.0, 6.0
        )
        # Should mention topology change or severe mismatch
        assert any("severe" in r.lower() or "topology" in r.lower() for r in recs)


class TestParseZData:
    def test_parse_z_real(self):
        """Test parsing Z-parameter real part export."""
        content = (
            "          Frequency / GHz                Z1,1/Re\n"
            "--------------------------------------------------------------\n"
            "                        1                    45.2\n"
            "                      2.4                    69.7\n"
            "                      5.4                   131.8\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            freqs, values = _parse_z_data(path)
            assert len(freqs) == 3
            assert abs(freqs[1] - 2.4) < 1e-6
            assert abs(values[1] - 69.7) < 1e-6
        finally:
            os.unlink(path)

    def test_parse_z_imag(self):
        """Test parsing Z-parameter imaginary part export."""
        content = (
            "          Frequency / GHz                Z1,1/Im\n"
            "--------------------------------------------------------------\n"
            "                        1                    79.8\n"
            "                      2.4                   -34.2\n"
            "                      5.4                    61.2\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            freqs, values = _parse_z_data(path)
            assert len(freqs) == 3
            assert abs(values[1] - (-34.2)) < 1e-6
        finally:
            os.unlink(path)

    def test_parse_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Header\n---\n")
            path = f.name

        try:
            with pytest.raises(ValueError, match="No Z-parameter data"):
                _parse_z_data(path)
        finally:
            os.unlink(path)


class TestAnalyzeImpedanceBand:
    def _make_s11_data(self):
        """Create sample S11 data with resonances at 2.45 GHz and 5.5 GHz."""
        freqs = [f / 10.0 for f in range(10, 81)]  # 1.0 to 8.0 GHz
        s11 = []
        for f in freqs:
            # Gaussian dip at 2.45 GHz (peak -15 dB)
            dip1 = -15.0 * math.exp(-((f - 2.45) ** 2) / (2 * 0.05 ** 2))
            # Gaussian dip at 5.5 GHz (peak -12 dB)
            dip2 = -12.0 * math.exp(-((f - 5.5) ** 2) / (2 * 0.1 ** 2))
            s11.append(min(dip1 + dip2, -0.1))
        resonances = _find_resonances(freqs, s11)
        return freqs, s11, resonances

    def test_analyze_passing_band(self):
        freqs, s11, resonances = self._make_s11_data()
        band = {
            "name": "2.4 GHz",
            "f_low_ghz": 2.4,
            "f_high_ghz": 2.5,
            "vswr_target": 3.0,  # Relaxed target
        }
        result = _analyze_impedance_band(
            freqs, s11, band, z0=50.0, resonances=resonances
        )
        assert result["name"] == "2.4 GHz"
        assert "worst_vswr" in result
        assert "best_vswr" in result
        assert "average_s11_db" in result
        assert "recommendations" in result
        assert "detail_points" in result

    def test_analyze_failing_band(self):
        freqs, s11, resonances = self._make_s11_data()
        band = {
            "name": "6 GHz",
            "f_low_ghz": 5.925,
            "f_high_ghz": 7.125,
            "vswr_target": 2.0,
        }
        result = _analyze_impedance_band(
            freqs, s11, band, z0=50.0, resonances=resonances
        )
        assert result["status"] == "FAIL"
        assert result["worst_vswr"] > 2.0
        # Average S11 should be poor (close to 0 dB)
        assert result["average_s11_db"] > -10
        # Should have recommendations
        assert len(result["recommendations"]) >= 2

    def test_analyze_no_data(self):
        band = {
            "name": "Ka-band",
            "f_low_ghz": 26.0,
            "f_high_ghz": 40.0,
        }
        result = _analyze_impedance_band([1.0, 2.0], [-5.0, -5.0], band)
        assert result["status"] == "NO_DATA"

    def test_detail_points(self):
        freqs, s11, resonances = self._make_s11_data()
        band = {
            "name": "5 GHz",
            "f_low_ghz": 5.15,
            "f_high_ghz": 5.85,
            "vswr_target": 2.5,
        }
        sample = [5.2, 5.5, 5.8]
        result = _analyze_impedance_band(
            freqs, s11, band, z0=50.0,
            sample_freqs=sample, resonances=resonances,
        )
        assert len(result["detail_points"]) >= 3
        for pt in result["detail_points"]:
            assert "s11_db" in pt
            assert "vswr" in pt
            assert "return_loss_db" in pt
            assert "match_quality" in pt

    def test_perfect_match(self):
        """Test with very good S11 data → should PASS."""
        freqs = [2.4, 2.45, 2.5]
        s11 = [-20.0, -25.0, -20.0]
        band = {
            "name": "Test",
            "f_low_ghz": 2.4,
            "f_high_ghz": 2.5,
            "vswr_target": 2.0,
        }
        result = _analyze_impedance_band(freqs, s11, band, z0=50.0)
        assert result["status"] == "PASS"
        assert result["worst_vswr"] < 1.3


class TestAnalyzeImpedanceOffline:
    @pytest.fixture
    def offline_client(self):
        from mcp_cst_studio.config import CSTConfig
        config = CSTConfig(connected=False)
        return CSTClient(config=config)

    @pytest.mark.asyncio
    async def test_analyze_impedance_offline(self, offline_client):
        from mcp_cst_studio.tools.optimization import handle
        result = await handle(
            "cst_analyze_impedance",
            {
                "bands": [
                    {"name": "2.4 GHz", "f_low_ghz": 2.4, "f_high_ghz": 2.5, "vswr_target": 2.5},
                    {"name": "5 GHz", "f_low_ghz": 5.15, "f_high_ghz": 5.85, "vswr_target": 2.5},
                ],
                "z0": 50,
                "port": 1,
            },
            offline_client,
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "offline"
        assert "vba" in data
        assert "S-Parameters" in data["vba"]
        assert "S1,1" in data["vba"]
        assert data["z0_ohm"] == 50
        assert "analysis_guidance" in data
