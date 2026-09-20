"""Tests for CST diagnostics tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def offline_client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


def _parse(result) -> dict:
    assert len(result) == 1
    return json.loads(result[0].text)


@pytest.mark.asyncio
async def test_automation_guardrails_include_observed_cst_failures(
    offline_client: CSTClient,
):
    from mcp_cst_studio.tools.diagnostics import handle

    result = await handle("cst_automation_guardrails", {}, offline_client)

    data = _parse(result)
    assert data["status"] == "ok"
    rule_ids = {rule["id"] for rule in data["rules"]}
    assert "probe_label_not_supported" in rule_ids
    assert "gaussian_signal_requires_fmin_fmax" in rule_ids
    assert "schematic_tasks_not_in_3d_history" in rule_ids
    assert "cable_cosimulation_model_type_not_in_tlmnodesettings" in rule_ids
    assert "cable_field_coupling_is_internal_model_type_bus" in rule_ids
    assert "transient_cosim_requires_standard_block_model" in rule_ids
    assert "transient_cosim_circuit_simulator_is_primary_switch" in rule_ids
    assert "bidirectional_coupling_is_task_setting" in rule_ids
    assert "solver_circuit_cosim_commands_are_3d_side_only" in rule_ids
    assert "combine_results_requires_supported_mws_block" in rule_ids
    assert "circuit_probe_requires_connected_full_pin_name" in rule_ids
    assert "cosimulation_update_requires_prepared_3d_cable_model" in rule_ids


def _write_cosim_files(
    base: Path,
    *,
    tl_model_type: str,
    cached_model_type: str,
    tcf_model_type: str,
    log_text: str,
) -> None:
    tls = base / "Model" / "CBLS" / "tlm_settings" / "tlmodel.tls"
    tls.parent.mkdir(parents=True)
    tls.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<CabTLModellingSettings>'
            "<TLMODELLING_OPTIONS_TAG>"
            f'<ModelType value="{tl_model_type}"></ModelType>'
            "</TLMODELLING_OPTIONS_TAG>"
            "</CabTLModellingSettings>"
        ),
        encoding="utf-8",
    )

    cached = base / "Model" / "CBLS" / "cached_files" / "modelType.prt"
    cached.parent.mkdir(parents=True)
    cached.write_text(cached_model_type, encoding="utf-8")

    tcf = base / "Result" / "TLM" / "tlmodel.tcf"
    tcf.parent.mkdir(parents=True)
    tcf.write_text(f".modeltype       {tcf_model_type}\n", encoding="utf-8")

    log = base / "Result" / "DS" / "Model.log"
    log.parent.mkdir(parents=True)
    log.write_text(log_text, encoding="utf-8")


@pytest.mark.asyncio
async def test_cable_cosimulation_status_accepts_bidirectional_project(
    offline_client: CSTClient,
    tmp_path: Path,
):
    from mcp_cst_studio.tools.diagnostics import handle

    _write_cosim_files(
        tmp_path,
        tl_model_type="CoSimulation",
        cached_model_type="CoSimulation",
        tcf_model_type="EMI_TEM_BIDIR_MODEL",
        log_text="Task: Tran1\nBidirectional transient co-simulation is active.\n",
    )

    result = await handle(
        "cst_cable_cosimulation_status",
        {"project_path": str(tmp_path)},
        offline_client,
    )

    data = _parse(result)
    assert data["status"] == "ok"
    assert data["ready_for_bidirectional_update"] is True
    assert data["evidence"]["tlmodel_tls_model_type"] == "CoSimulation"
    assert data["evidence"]["tlmodel_tcf_model_type"] == "EMI_TEM_BIDIR_MODEL"
    mapping = data["observed_cst_2025_internal_model_type_mapping"]
    assert mapping["2"] == "CO_SIM / CoSimulation / Bi-directional"
    sequence = data["observed_cst_2025_ui_sequence"]
    assert "Bi-directional" in sequence["observed_coupling_type_options"]
    assert (
        data["expected_for_bidirectional"]["csschem_block_simulation_model"]
        == "Standard model"
    )
    assert (
        data["expected_for_bidirectional"]["tran_task_circuit_simulator"]
        == "CST transient co-simulation"
    )
    assert (
        data["expected_for_bidirectional"]["tran_task_cable_field_coupling_type"]
        == "Bi-directional"
    )
    assert 'Solver.CircuitCoSimCoupling "bidirectional"' in (
        data["tested_non_public_or_partial_commands"]["callable_3d_solver_side_only"]
    )


@pytest.mark.asyncio
async def test_cable_cosimulation_status_blocks_unidirectional_project(
    offline_client: CSTClient,
    tmp_path: Path,
):
    from mcp_cst_studio.tools.diagnostics import handle

    _write_cosim_files(
        tmp_path,
        tl_model_type="Radiation_Irradiation",
        cached_model_type="Radiation_Irradiation",
        tcf_model_type="EMI_TEM_UNIDIR_MODEL",
        log_text=(
            "ERROR: Could not find CS co-simulation results: results.ccr "
            "are not available.\n"
            "The simulator is not prepared for co-simulation task.\n"
        ),
    )

    result = await handle(
        "cst_cable_cosimulation_status",
        {"project_path": str(tmp_path)},
        offline_client,
    )

    data = _parse(result)
    assert data["status"] == "error"
    assert data["ready_for_bidirectional_update"] is False
    assert "will likely fail" in data["message"]
    assert data["evidence"]["cached_model_type_prt"] == "Radiation_Irradiation"
    assert 'Block.SetSimulationModel "3D Combined"' in (
        data["tested_non_public_or_partial_commands"]["not_public_vba"]
    )
