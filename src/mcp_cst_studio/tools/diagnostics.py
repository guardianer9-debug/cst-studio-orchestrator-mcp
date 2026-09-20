"""Diagnostic tools for CST Studio Suite.

Provides tools for managing simulation results, reading project
messages/logs, and handling CST dialog windows — essential for
preventing blocking popups during automation.

- ``cst_delete_results``: Delete simulation results (prevents stale-result dialogs)
- ``cst_read_project_log``: Read solver log and project messages
- ``cst_dismiss_dialogs``: Find and dismiss CST dialog windows (read their content)
- ``cst_start_dialog_watcher``: Auto-dismiss dialogs in background during long ops
- ``cst_stop_dialog_watcher``: Stop the background dialog watcher and get its log
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from mcp.types import TextContent, Tool

from mcp_cst_studio.cst_client import CSTClient

if TYPE_CHECKING:
    from mcp.server import Server

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="cst_automation_guardrails",
        description=(
            "Return known CST automation guardrails learned from real CST "
            "runs and local CST 2025 documentation. Use before generating "
            "VBA/Python automation for probes, transient signals, Cable Studio "
            "co-simulation, or Design Studio schematic tasks."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="cst_cable_cosimulation_status",
        description=(
            "Inspect an expanded CST project directory before running a Design "
            "Studio transient co-simulation task. Checks Cable Studio 2D TL "
            "model files and recent DS/TLM logs for CoSimulation versus "
            "Radiation/Irradiation or EMI_TEM_UNIDIR_MODEL. Use before "
            "SimulationTask.Update to avoid repeating long failing updates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": (
                        "Optional .cst file path or expanded project directory. "
                        "Defaults to the active project path in connected mode."
                    ),
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cst_delete_results",
        description=(
            "Delete simulation results from the current CST project. "
            "This prevents the 'Results May Get Incompatible With Model' "
            "dialog that blocks automation when modifying a model with "
            "existing results. Call before making parameter or geometry "
            "changes on a project that has been solved."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="cst_read_project_log",
        description=(
            "Read solver log files and project status information from "
            "the current CST project. Returns solver running state and "
            "the contents of the most recent log file. Useful for "
            "diagnosing solver errors, checking simulation progress, "
            "and understanding what happened during a failed run."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="cst_dismiss_dialogs",
        description=(
            "Find and dismiss any visible CST dialog windows (error popups, "
            "'Results Incompatible' dialogs, solver warnings). Returns the "
            "title and text content of each dialog before dismissing it. "
            "Use this to unblock CST when a modal dialog is preventing "
            "further automation. Uses Win32 API on Windows."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "read_only": {
                    "type": "boolean",
                    "description": (
                        "If true, only read dialog content without dismissing. "
                        "Default: false (read and dismiss)."
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cst_start_dialog_watcher",
        description=(
            "Start a background thread that automatically detects and "
            "dismisses CST dialog windows as they appear. Essential for "
            "long-running operations like optimization loops where dialogs "
            "would otherwise block execution. The watcher logs every dialog "
            "it dismisses — retrieve the log with cst_stop_dialog_watcher."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="cst_stop_dialog_watcher",
        description=(
            "Stop the background dialog watcher and return its log of all "
            "dialogs that were auto-dismissed. Use after completing an "
            "operation that required the watcher."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]

_TOOL_NAMES = {t.name for t in TOOLS}

_AUTOMATION_GUARDRAILS: list[dict[str, str]] = [
    {
        "id": "probe_label_not_supported",
        "area": "3D probes",
        "problem": (
            "The 3D Probe VBA object in CST 2025 does not expose a Label method. "
            "Using Probe.Label raises ActiveX Automation error 10091."
        ),
        "safe_pattern": (
            "Use Probe.ID, Probe.AutoLabel, Probe.Field, Probe.Orientation, "
            "Probe.Xpos/Ypos/Zpos, then Probe.Create."
        ),
    },
    {
        "id": "gaussian_signal_requires_fmin_fmax",
        "area": "transient excitation",
        "problem": (
            "TimeSignal SignalType 'Gaussian' and SimulationTask.SetPortSignal "
            "'Gaussian' require Fmin/Fmax/amplitude settings. Missing Fmin/Fmax "
            "causes the CST 'Invalid Fmin-Fmax settings' error."
        ),
        "safe_pattern": (
            "For quick broadband automation use a User signal, or pass the full "
            "Gaussian values array: Fmin, Fmax, Ampl, and optional "
            "UseFminFmaxFromTask."
        ),
    },
    {
        "id": "schematic_tasks_not_in_3d_history",
        "area": "Design Studio schematic",
        "problem": (
            "Circuit/Schematic task creation is not recorded in the 3D History "
            "List. Looking only at Model/3D/ModelHistory misses Tran1, probes, "
            "and Design Studio result settings."
        ),
        "safe_pattern": (
            "Use project.schematic.SimulationTask or Design Studio VBA. Inspect "
            "Model/simulationproperties.docstore, Model/DS/schematic.xml, and "
            "Result/DS/model.res for saved schematic/task state."
        ),
    },
    {
        "id": "cable_cosimulation_model_type_not_in_tlmnodesettings",
        "area": "Cable Studio",
        "problem": (
            "TLMNodeSettings exposes settings such as DielectricLosses and "
            "UpdateSelect, but CST 2025 documentation does not expose a public "
            "VBA field for the TL model type displayed as CoSimulation."
        ),
        "safe_pattern": (
            "Use documented TLMNodeSettings for public options, then verify the "
            "expanded project's Model/CBLS/tlm_settings/tlmodel.tls ModelType "
            "and cached_files/modelType.prt when automating co-simulation."
        ),
    },
    {
        "id": "cable_field_coupling_is_internal_model_type_bus",
        "area": "Field-circuit co-simulation",
        "problem": (
            "The Transient task Cable Field Coupling coupling-type dropdown "
            "is not exposed as a confirmed documented SimulationTask.SetProperty "
            "key in CST 2025. Observed probes show Block.SetSimulationModel "
            "'3D Combined' returns 'Unknown model', Block.SetIntegerProperty "
            "'*SLModelType' is read-only, Solver.SetCableFieldCoupling is not "
            "a public VBA method, and CableStudio.DoSetModelType/SetModelType/"
            "ChangeModelType are not callable VBA wrappers."
        ),
        "safe_pattern": (
            "Use CST UI automation or a preconfigured project for the task "
            "coupling type until a stable public wrapper is found. The observed "
            "successful CST 2025 path is Tran1 -> Cable Field Coupling -> "
            "Coupling Type = Bi-directional, followed by Update. Verify "
            "tlmodel.tls, modelType.prt, and tlmodel.tcf after Update."
        ),
    },
    {
        "id": "transient_cosim_requires_standard_block_model",
        "area": "Field-circuit co-simulation",
        "problem": (
            "CST 2025 UI test showed that setting CSSCHEM1 Block Parameter "
            "List -> Solver -> Simulation model to '3D Combined' makes Tran1 "
            "Update fail with: Transient co-simulation simulation is only "
            "supported for 'Standard' block model type."
        ),
        "safe_pattern": (
            "For a Design Studio transient field-circuit co-simulation task, "
            "keep the CSSCHEM/Cable Studio schematic block Simulation model "
            "as 'Standard model'. Configure bidirectional coupling on the "
            "task's Cable Field Coupling tab instead."
        ),
    },
    {
        "id": "transient_cosim_circuit_simulator_is_primary_switch",
        "area": "Field-circuit co-simulation",
        "problem": (
            "The Transient tab's Circuit simulator setting is the primary "
            "switch for transient EM/circuit co-simulation. If it is left at "
            "plain 'CST', the task is a circuit-engine transient simulation, "
            "not the direct CST transient EM/circuit co-simulation workflow."
        ),
        "safe_pattern": (
            "For direct transient field-circuit co-simulation, set Tran1 -> "
            "Transient -> Circuit simulator to 'CST transient co-simulation'. "
            "The Cable Field Coupling tab becomes relevant after CST CS "
            "co-simulation is activated there."
        ),
    },
    {
        "id": "bidirectional_coupling_is_task_setting",
        "area": "Field-circuit co-simulation",
        "problem": (
            "With CSSCHEM1 set to Standard model, Tran1 Update still fails "
            "with 'The simulator is not prepared for co-simulation task' when "
            "Tran1 -> Cable Field Coupling -> Coupling Type remains 'None'. "
            "Some CST-created workflows may default this coupling type to "
            "Bi-directional; generated tasks should still verify it explicitly."
        ),
        "safe_pattern": (
            "Select the transient task, open Task Parameter List -> Cable Field "
            "Coupling, and set Coupling Type to 'Bi-directional'. CST 2025 UI "
            "also exposes 'Uni-directional Radiation' and 'Uni-directional "
            "Irradiation' for one-way coupling cases."
        ),
    },
    {
        "id": "solver_circuit_cosim_commands_are_3d_side_only",
        "area": "3D solver co-simulation",
        "problem": (
            "Solver.DSCoSimulation, Solver.CircuitCoSimulationTaskName, and "
            "Solver.CircuitCoSimCoupling are callable 3D VBA commands, but "
            "adding them to 3D history does not by itself switch the Cable "
            "Studio TL model from Radiation_Irradiation to CoSimulation."
        ),
        "safe_pattern": (
            "Use those Solver commands only for the 3D solver-side circuit "
            "co-simulation settings. Still require the Cable Studio model "
            "type to be CoSimulation before assuming bidirectional "
            "field-circuit readiness."
        ),
    },
    {
        "id": "node_set_grounded_is_auto_connect_3d",
        "area": "Cable Studio",
        "problem": (
            "Cable node coupling to 3D is controlled by the NodeSetGrounded "
            "command, which can be easy to confuse with an electrical ground."
        ),
        "safe_pattern": (
            "For field-to-cable coupling, call CableStudio.Execute "
            "'NodeSetGrounded' for the harness nodes that should auto-connect "
            "to 3D."
        ),
    },
    {
        "id": "combine_results_requires_supported_mws_block",
        "area": "Design Studio schematic",
        "problem": (
            "SimulationTask docombineresults cannot be enabled against every "
            "schematic block. CST 2025 ValidateSetup reports 'Selected block "
            "type does not support combine results' when CSSCHEM1/Cable Studio "
            "is used as blocknameforcombineresults."
        ),
        "safe_pattern": (
            "For Cable Studio field-circuit work, first enable the transient "
            "task's circuit simulator as cosimulation and leave docombineresults "
            "off unless a supported MWS block has been selected."
        ),
    },
    {
        "id": "circuit_probe_requires_connected_full_pin_name",
        "area": "Design Studio schematic",
        "problem": (
            "CircuitProbe.SetBlockPin may reject the short layout label of a "
            "CSSCHEM pin, and CircuitProbe.Create fails when the target block "
            "pin is still unconnected."
        ),
        "safe_pattern": (
            "Query Block.GetPinName(index) and pass the full pin name such as "
            "'1(N1_SW_1)'. Create the baseline net first, then insert the "
            "CircuitProbe into that connected pin."
        ),
    },
    {
        "id": "cosimulation_update_requires_prepared_3d_cable_model",
        "area": "Field-circuit co-simulation",
        "problem": (
            "Creating a Design Studio transient task with circuit simulator "
            "cosimulation is not enough to run Update. CST can fail with "
            "'Could not find CS co-simulation results ... results.ccr are not "
            "available', 'Transient co-simulation simulation is only supported "
            "for Standard block model type', and 'The simulator is not prepared "
            "for co-simulation task' when the 3D/Cable/task coupling state is "
            "incomplete."
        ),
        "safe_pattern": (
            "Before relying on SimulationTask.Update, verify CSSCHEM uses "
            "Standard model, Tran1 Circuit simulator uses CST transient "
            "co-simulation, Tran1 Cable Field Coupling uses Bi-directional "
            "when bidirectional cable-field feedback is desired, and the "
            "expanded project's Model/CBLS/tlm_settings/tlmodel.tls ModelType, "
            "cached_files/modelType.prt, and Result/TLM/tlmodel.tcf have been "
            "regenerated as bidirectional/CoSimulation outputs."
        ),
    },
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _text(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _project_base(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if p.suffix.lower() == ".cst":
        return p.with_suffix("")
    return p


def _read_text(path: Path, limit: int | None = None) -> str | None:
    if not path.is_file():
        return None
    data = path.read_bytes()
    if limit is not None:
        data = data[-limit:]
    return data.decode("utf-8", errors="replace")


def _xml_model_type(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError:
        return None
    node = root.find(".//ModelType")
    if node is None:
        return None
    return node.attrib.get("value")


def _tcf_model_type(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(?im)^\s*\.modeltype\s+(\S+)", text)
    return match.group(1) if match else None


def _interesting_log_lines(text: str | None) -> list[str]:
    if not text:
        return []
    patterns = (
        "Task:",
        "co-simulation",
        "cosimulation",
        "bidirectional",
        "uni-directional",
        "unidirectional",
        "results.ccr",
        "simulator is not prepared",
        "ERROR:",
    )
    lines: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(pattern.lower() in lower for pattern in patterns):
            lines.append(line.strip())
    return lines[-40:]


def _cosimulation_status(project_path: str | None) -> dict:
    base = _project_base(project_path)
    if base is None:
        return {
            "status": "error",
            "message": "project_path is required when no active CST project path is available.",
        }
    if not base.exists():
        return {
            "status": "error",
            "project_base": str(base),
            "message": "Expanded CST project directory was not found.",
        }

    paths = {
        "tl_settings": base / "Model" / "CBLS" / "tlm_settings" / "tlmodel.tls",
        "cached_model_type": base / "Model" / "CBLS" / "cached_files" / "modelType.prt",
        "tcf": base / "Result" / "TLM" / "tlmodel.tcf",
        "ds_log": base / "Result" / "DS" / "Model.log",
        "model_ads": base / "Model" / "3D" / "Model.ads",
    }

    tl_model_type = _xml_model_type(paths["tl_settings"])
    cached_model_type = _read_text(paths["cached_model_type"])
    if cached_model_type is not None:
        cached_model_type = cached_model_type.strip()
    tcf_text = _read_text(paths["tcf"], limit=200_000)
    tcf_model_type = _tcf_model_type(tcf_text)
    ds_log = _read_text(paths["ds_log"], limit=200_000)
    model_ads = _read_text(paths["model_ads"], limit=20_000)

    evidence = {
        "tlmodel_tls_model_type": tl_model_type,
        "cached_model_type_prt": cached_model_type,
        "tlmodel_tcf_model_type": tcf_model_type,
        "model_ads_cosimulation_flag": None,
        "recent_relevant_log_lines": _interesting_log_lines(ds_log),
        "files": {name: str(path) for name, path in paths.items() if path.exists()},
        "missing_files": [name for name, path in paths.items() if not path.exists()],
    }
    if model_ads:
        match = re.search(r"(?im)^\[COSIMULATION\]\s+(\S+)", model_ads)
        evidence["model_ads_cosimulation_flag"] = match.group(1) if match else None

    settings_ready = (
        tl_model_type == "CoSimulation"
        and cached_model_type == "CoSimulation"
    )
    exported_ready = tcf_model_type in (None, "EMI_TEM_BIDIR_MODEL")
    ready = settings_ready and exported_ready

    if ready:
        status = "ok"
        message = (
            "Cable Studio files look prepared for bidirectional field-circuit "
            "co-simulation. SimulationTask.Update is not guaranteed to solve, "
            "but the observed CoSimulation/EMI_TEM_BIDIR_MODEL prerequisite is met."
        )
    elif (
        tl_model_type == "Radiation_Irradiation"
        or cached_model_type == "Radiation_Irradiation"
        or tcf_model_type == "EMI_TEM_UNIDIR_MODEL"
    ):
        status = "error"
        message = (
            "SimulationTask.Update will likely fail for bidirectional "
            "field-circuit co-simulation: the Cable Studio model is still "
            "Radiation/Irradiation or exported as EMI_TEM_UNIDIR_MODEL."
        )
    else:
        status = "warning"
        message = (
            "Could not prove the project is ready for bidirectional "
            "field-circuit co-simulation. Regenerate the Cable Studio 2D TL "
            "model as CoSimulation before running SimulationTask.Update."
        )

    return {
        "status": status,
        "project_base": str(base),
        "ready_for_bidirectional_update": ready,
        "message": message,
        "evidence": evidence,
        "observed_cst_2025_internal_model_type_mapping": {
            "-1": "FAST",
            "0": "STANDARD",
            "1": "RAD_IRRAD / Radiation_Irradiation / Uni-directional",
            "2": "CO_SIM / CoSimulation / Bi-directional",
            "3": "PEEC_ROM",
            "4": "PEEC_CABLEFIELDCOUPLING",
            "source": (
                "D:/CST2025/Plugins/lib/slcore.jar "
                "com/simlab/cabmod/modelling/nodes/CabModelType_e and "
                "D:/CST2025/Plugins/lib/slstudio.jar "
                "com/cst/cs/CSModelTypeChanger.paramToCabModelType"
            ),
        },
        "tested_non_public_or_partial_commands": {
            "not_public_vba": [
                'Block.SetSimulationModel "3D Combined"',
                'Block.SetIntegerProperty "*SLModelType", "2"',
                'Solver.SetCableFieldCoupling "bidirectional"',
                "CableStudio.DoSetModelType 2",
                "CableStudio.SetModelType 2",
                "CableStudio.ChangeModelType 2",
            ],
            "callable_3d_solver_side_only": [
                'Solver.DSCoSimulation "True"',
                'Solver.CircuitCoSimulationTaskName "Tran1"',
                'Solver.CircuitCoSimCoupling "bidirectional"',
            ],
        },
        "observed_cst_2025_ui_sequence": {
            "validated_bidirectional_transient_cosimulation_setup": [
                (
                    "CSSCHEM1 Block Parameter List -> Solver -> Simulation "
                    "model = Standard model"
                ),
                (
                    "Tran1 Task Parameter List -> Transient -> Circuit "
                    "simulator = CST transient co-simulation"
                ),
                (
                    "Tran1 Task Parameter List -> Cable Field Coupling -> "
                    "Coupling Type = Bi-directional"
                ),
                "Select Tran1 in the Navigation Tree and click Update.",
            ],
            "do_not_use_for_transient_cosimulation": [
                (
                    "CSSCHEM1 Simulation model = 3D Combined. CST 2025 Update "
                    "reported that transient co-simulation is only supported "
                    "for Standard block model type."
                ),
            ],
            "observed_coupling_type_options": [
                "None",
                "Bi-directional",
                "Uni-directional Radiation",
                "Uni-directional Irradiation",
            ],
            "observed_success_markers": [
                "Block CSSCHEM1: Bidirectional transient co-simulation is active.",
                "modelType.prt = CoSimulation",
                'tlmodel.tls contains <ModelType value="CoSimulation">',
                "tlmodel.tcf contains .modeltype EMI_TEM_BIDIR_MODEL",
            ],
            "observed_failure_markers": [
                (
                    "Transient co-simulation simulation is only supported for "
                    "'Standard' block model type."
                ),
                (
                    "The simulator is not prepared for co-simulation task. "
                    "Please check the task settings."
                ),
            ],
        },
        "expected_for_bidirectional": {
            "csschem_block_simulation_model": "Standard model",
            "tran_task_circuit_simulator": "CST transient co-simulation",
            "tran_task_cable_field_coupling_type": "Bi-directional",
            "tlmodel_tls_model_type": "CoSimulation",
            "cached_model_type_prt": "CoSimulation",
            "tlmodel_tcf_model_type": "EMI_TEM_BIDIR_MODEL",
        },
    }


async def handle(
    name: str, arguments: dict, client: CSTClient
) -> list[TextContent]:
    """Handle a diagnostics tool call."""
    try:
        if name == "cst_delete_results":
            return _text(client.delete_results())

        if name == "cst_automation_guardrails":
            return _text(
                {
                    "status": "ok",
                    "rules": _AUTOMATION_GUARDRAILS,
                }
            )

        if name == "cst_cable_cosimulation_status":
            project_path = arguments.get("project_path") or client.project_path
            return _text(_cosimulation_status(project_path))

        if name == "cst_read_project_log":
            return _text(client.read_project_messages())

        if name == "cst_dismiss_dialogs":
            read_only = arguments.get("read_only", False)
            if read_only:
                return _text(client.read_dialogs())
            return _text(client.dismiss_dialogs())

        if name == "cst_start_dialog_watcher":
            return _text(client.start_dialog_watcher())

        if name == "cst_stop_dialog_watcher":
            return _text(client.stop_dialog_watcher())

        return _text({"status": "error", "message": f"Unknown diagnostics tool: {name}"})
    except Exception as e:
        return _text({"status": "error", "message": str(e)})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_diagnostics_tools(server: Server, client: CSTClient) -> None:
    """Register diagnostics tools with the MCP server."""
    from mcp_cst_studio.tools import _registry
    _registry.add_module(TOOLS, handle, client)
