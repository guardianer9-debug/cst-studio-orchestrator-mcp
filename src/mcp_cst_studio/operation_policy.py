"""Explicit no-solve policy and native-file change protection for session workflows."""
import re
from pathlib import Path

from mcp_cst_studio.session_workspace import digest
import time


def check_paused(client, tool: str, args: dict) -> None:
    if not client._config.simulation_paused:
        return
    if args.get("update"):
        raise ValueError("Task update/run is paused; configuration may be saved without update")
    if tool in {"cst_run_task", "cst_run_simulation", "cst_run_simulation_async",
                "cst_resume_simulation", "cst_optimize_antenna"} or "optimiz" in tool:
        raise ValueError("Automatic simulation is paused for this session; no new solver/task/mesh run is permitted")
    if tool in {"cst_execute_vba", "cst_execute_vba_silent", "cst_schematic_call"}:
        # Raw code is not a sandbox. In paused mode reject all potential execution
        # verbs, including With-block forms, instead of trusting a chat instruction.
        text = str(args)
        method = str(args.get("method_name", ""))
        if re.match(r"^(Start|Run|Resume|Update|Calculate|Execute)", method, re.I) and "Iteration" not in method:
            raise ValueError("Execution method is disabled while automatic simulation is paused")
        if re.search(r"\b(start|run|resume|update|calculate|execute|shell|application|eval|callbyname)\b", text, re.I):
            raise ValueError("Raw execution verbs are disabled while automatic simulation is paused")


def remember_file(client) -> None:
    path = Path(client.project_path) if client.project_path else None
    client._opened_file_hash = digest(path) if path and path.is_file() else None


def check_external_change(client) -> None:
    if not client._config.session_dir or not client.project_path:
        return
    previous = getattr(client, "_opened_file_hash", None)
    path = Path(client.project_path)
    if previous and (not path.exists() or digest(path) != previous):
        raise ValueError("Native project changed outside this backend. Writes blocked: close/reopen and read actual state before retrying; do not overwrite manual changes")


def is_model_edit(tool: str, args: dict) -> bool:
    if tool == "cst_schematic_call":
        return not str(args.get("method_name", "")).startswith(("Get", "Does", "Is", "Start", "Reset", "Name"))
    return tool.startswith(("cst_set_", "cst_create_", "cst_delete_", "cst_add_", "cst_transform_")) and tool != "cst_create_project" or tool in ("cst_execute_vba", "cst_execute_vba_silent")


def prepare_edit(client, tool: str, args: dict) -> None:
    """Read actual state, then branch an existing model once per editing interval."""
    if not client._config.session_dir or not client.connected or not client.has_project or not is_model_edit(tool, args):
        return
    from mcp_cst_studio.tools.cases import readback
    from mcp_cst_studio.session_workspace import write_json, read_json, render_entry
    root = Path(client._config.session_dir)
    before = readback(client)
    write_json(root / "过程记录" / f"before-edit-{time.time_ns()}.json", before)
    if before["status"] != "ok" or before.get("errors"):
        raise ValueError("Actual pre-edit readback is incomplete; resolve errors before changing this model")
    if getattr(client, "_edit_branch", None) == client.project_path:
        client._unsaved_backend_edits = True
        return
    source = Path(client.project_path)
    folder = root / "工程" / "修改版本" / f"v{time.time_ns()}"
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / source.name
    old_hash = digest(source)
    saved = client.save_project(str(target))
    if saved.get("status") != "saved":
        write_json(folder / "failed-save.json", saved)
        raise RuntimeError("Could not save independent native version before editing")
    if digest(source) != old_hash:
        raise RuntimeError("Native Save As changed the source; retained evidence requires review")
    client._edit_branch = str(target)
    client._unsaved_backend_edits = True
    info = read_json(root / "会话信息.json")
    info["projects"].append({"path": str(target), "label": "修改版本 / " + source.name,
        "source_path": str(source), "source_sha256": old_hash, "status": "修改进行中；尚未验收",
        "result_origin": "unknown", "result_binding": "unknown", "result_note": "不沿用源版本结果的当前有效性"})
    info["recommended_project"] = str(target)
    write_json(root / "会话信息.json", info)
    render_entry(root)
