"""Case-scoped, read/modify/save/read transactions shared by Pi and desktop."""
import hashlib
import json
import math
from pathlib import Path
import time

from mcp.types import TextContent, Tool
from mcp_cst_studio.operation_policy import prepare_edit
from mcp_cst_studio.session_workspace import digest, read_json, write_json, render_entry
from mcp_cst_studio.tools.cases import readback, publish_view
from mcp_cst_studio.vba_builder import VBABuilder

TOOLS = [Tool(name="cst_edit_case", description=(
    "Modify one actual case value, save a NEW native project version and publish actual readback. "
    "Never solve. First cst_readback to obtain project/project_sha256. Specify these as "
    "expected_project/expected_sha256 and a stable operation_id. A repeated operation_id replays "
    "the receipt without another edit. Supports existing parameter; resistor double property with "
    "exact native unit; frequency min/max; existing transient task tmax. No implicit task Update."),
    inputSchema={"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["parameter", "load", "frequency", "task"]},
        "target": {"type": "string"}, "property": {"type": "string"},
        "value": {"type": ["number", "string"]}, "unit": {"type": "string"},
        "expected_project": {"type": "string"}, "expected_sha256": {"type": "string"},
        "operation_id": {"type": "string", "minLength": 1, "maxLength": 128}},
        "required": ["kind", "target", "property", "value", "expected_project", "expected_sha256", "operation_id"],
        "additionalProperties": False})]


def edit_case(client, args):
    if not client._config.session_dir or not client.connected or not client.has_project:
        raise ValueError("Open a session-local working project first")
    operation = args["operation_id"]
    if not isinstance(operation, str) or not 1 <= len(operation) <= 128:
        raise ValueError("Invalid operation_id")
    receipt = Path(client._config.session_dir) / "过程记录" / "operations" / (hashlib.sha256(operation.encode()).hexdigest() + ".json")
    if receipt.exists():
        prior = read_json(receipt)
        if prior["request"] != args:
            raise ValueError("operation_id was already used for a different request")
        return {**prior["result"], "replayed": True, "receipt": str(receipt)}
    if Path(args["expected_project"]).resolve() != Path(client.project_path).resolve() or args["expected_sha256"] != digest(Path(client.project_path)):
        raise ValueError("Project/revision changed; read actual state before editing")
    if getattr(client, "_unsaved_backend_edits", False):
        raise ValueError("Resolve unsaved backend edits before starting a new transaction")
    if client.solver_status().get("running") is not False:
        raise ValueError("Cannot edit while solver state is running or unknown")
    before = readback(client)
    if before.get("errors") or before.get("status") != "ok":
        raise ValueError("Pre-edit readback is incomplete")
    kind, target, prop, value = (args[k] for k in ("kind", "target", "property", "value"))
    unit = args.get("unit", "")
    old = None
    number = None
    if kind == "parameter":
        parameters = before["parameters"]["parameters"]
        item = next((p for p in parameters if p["name"] == target), None)
        if not item or prop != "expression":
            raise ValueError("Select an existing design parameter")
        old = item["expression"]
    else:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError("A finite nonnegative value is required")
        if kind == "load":
            block = next((b for b in before["schematic"]["blocks"] if b["name"] == target), None)
            allowed = {"Resistance", "Parasitic Capacitance", "Parasitic Inductance", "Shunt Resistance", "Shunt Capacitance"}
            if not block or block["type_short"] != "RES" or prop not in allowed:
                raise ValueError("Only the observed resistor properties are supported")
            item = next(p for p in before["block_properties"] if p["name"] == target)["properties"].get(prop)
            if not item or item["type"] != "double" or unit != item["unit"]:
                raise ValueError("Property/unit differs from actual CST readback; unit conversion is not implicit")
            old = item["value"]
        elif kind == "frequency":
            if target != "Solver" or prop not in ("min", "max") or unit != before["units"]["Frequency"]:
                raise ValueError("Select min/max in the project's native frequency unit")
            bounds = {**before["frequency"], prop: number}
            if bounds["max"] <= bounds["min"]:
                raise ValueError("Frequency max must exceed min")
            old = before["frequency"][prop]
        elif kind == "task":
            item = next((t for t in before["tasks"] if t["name"] == target), None)
            if not item or item["type"].lower() != "transient" or prop != "tmax" or unit != before["units"]["Time"] or number <= 0:
                raise ValueError("Only existing transient tmax in the native time unit is supported")
            old = item["properties"]["tmax"]
        else:
            raise ValueError("Unsupported case edit")
    unchanged = str(old) == str(value) if kind == "parameter" else math.isclose(float(old), number, rel_tol=1e-12, abs_tol=1e-12)
    record = {"request": args, "started_at": time.time(), "before": before}
    if unchanged:
        result = {"status": "unchanged", "project": client.project_path, "readback": before}
    else:
        # The existing native Save As implementation preserves the old version.
        prepare_edit(client, "cst_set_parameter", {})
        try:
            if kind == "parameter":
                response = client.set_parameter(target, value)
                if response.get("status") != "executed":
                    raise RuntimeError(str(response))
            elif kind == "load":
                response = client.schematic_call(object_name="Block", method_name="SetDoubleProperty", args=[prop, number], target_name=target)
                if response.get("status") != "executed":
                    raise RuntimeError(str(response))
            elif kind == "task":
                response = client.schematic_call(object_name="SimulationTask", method_name="SetProperty", args=["tmax", str(number)], target_name=target)
                if response.get("status") != "executed":
                    raise RuntimeError(str(response))
            else:
                bounds = {**before["frequency"], prop: number}
                response = client.execute_vba(VBABuilder("Solver").set_double("FrequencyRange", bounds["min"], bounds["max"]).build())
                if response.get("status") != "executed":
                    raise RuntimeError(str(response))
            after = readback(client)
            if after.get("errors"):
                raise RuntimeError("Post-edit readback incomplete")
            if kind == "parameter":
                observed = next(p for p in after["parameters"]["parameters"] if p["name"] == target)["expression"]
                matches = str(observed) == str(value)
            else:
                if kind == "load":
                    observed = next(b for b in after["block_properties"] if b["name"] == target)["properties"][prop]["value"]
                    if after["schematic"]["nets"] != before["schematic"]["nets"]:
                        raise RuntimeError("Load property edit changed connectivity")
                elif kind == "task":
                    observed = next(t for t in after["tasks"] if t["name"] == target)["properties"][prop]
                else:
                    observed = after["frequency"][prop]
                matches = math.isclose(float(observed), number, rel_tol=1e-9, abs_tol=1e-12)
            if not matches:
                raise RuntimeError(f"Readback mismatch: {observed}")
            saved = client.save_project()
            if saved.get("status") != "saved":
                raise RuntimeError(str(saved))
            client._edit_branch = None
            view = publish_view(client, f"{target}.{prop}={value} {unit}", "modified_variant", save=False)
            result = {"status": "saved" if not view.get("errors") else "partial", "project": client.project_path,
                      "observed": observed, "unit": unit, "view": view}
        except Exception as exc:
            result = {"status": "error", "project": client.project_path, "message": str(exc), "partial_execution_possible": True}
            client._edit_branch = None
            info_path = Path(client._config.session_dir) / "会话信息.json"
            if info_path.exists():
                info = read_json(info_path)
                for item in info["projects"]:
                    if item["path"] == client.project_path:
                        item.update(status="修改失败，保留现场", label=f"失败尝试 / {target}.{prop}", operation_receipt=str(receipt))
                info["recommended_project"] = args["expected_project"]
                write_json(info_path, info)
                render_entry(info_path.parent)
    record.update(ended_at=time.time(), result=result)
    write_json(receipt, record)
    return {**result, "operation_id": operation, "receipt": str(receipt)}


async def handle(name, arguments, client):
    try:
        result = edit_case(client, arguments)
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
