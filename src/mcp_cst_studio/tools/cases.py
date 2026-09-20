"""Reference copies and actual readback, using the existing CST client."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import time

from mcp.types import TextContent, Tool

from mcp_cst_studio.cst_client import CSTClient


TOOLS = [
    Tool(name="cst_prepare_reference", description=(
        "Copy a saved reference into a new attempt under CST_WORK_DIR and open only the copy. "
        "Does not run a solver. Embedded dependencies are extracted by CST; external dependencies "
        "must be checked in readback before solving. Existing attempts are never overwritten."),
        inputSchema={"type": "object", "properties": {
            "source": {"type": "string"}, "attempt": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"}},
            "required": ["source", "attempt"], "additionalProperties": False}),
    Tool(name="cst_readback", description=(
        "Read actual parameters, units, solids, plane wave, schematic blocks/nets and transient tasks. "
        "Errors are returned explicitly. Does not rebuild, mesh or solve."),
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False}),
    Tool(name="cst_read_curve", description=(
        "Read a real CST 3D or schematic curve into an immutable JSON artifact. "
        "Return metadata and a preview; the full data remains local. A cached curve alone does not prove a fresh run."),
        inputSchema={"type": "object", "properties": {
            "tree_path": {"type": "string"}, "domain": {"type": "string", "enum": ["3d", "schematic"]}},
            "required": ["tree_path", "domain"], "additionalProperties": False}),
]


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        digest = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def prepare_reference(client: CSTClient, source: str, attempt: str) -> dict:
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]+", attempt):
        raise ValueError("Attempt must contain only letters, digits, underscores and hyphens")
    if not client._config.work_dir:
        raise ValueError("CST_WORK_DIR must be configured")
    source_path = Path(source).resolve(strict=True)
    if source_path.suffix.lower() != ".cst":
        raise ValueError("Reference must be a .cst file")
    root = Path(client._config.work_dir).resolve()
    destination = root / attempt
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / "model.cst"
    receipt = {"attempt": attempt, "kind": "reference_operation", "source": str(source_path),
               "source_sha256": sha256(source_path), "created_at": time.time(),
               "project": str(target), "model_usage": None, "human_acceptance": "pending"}
    shutil.copy2(source_path, target)
    receipt["copy_sha256_before_open"] = sha256(target)
    receipt["open"] = client.open_project(str(target))
    receipt["source_unchanged"] = sha256(source_path) == receipt["source_sha256"]
    receipt_path = destination / "reference.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": receipt["open"]["status"], "receipt": str(receipt_path), **receipt}


def readback(client: CSTClient) -> dict:
    if not client.connected or not client.has_project:
        return {"status": "offline", "message": "A live, explicitly opened project is required"}
    m = client._project.model3d
    result: dict = {"status": "ok", "project": client.project_path, "read_at": time.time(), "errors": {}}

    def read(key, operation):
        try:
            result[key] = client._jsonable(operation())
        except Exception as exc:
            result["errors"][key] = str(exc)

    read("version", m.GetApplicationVersion)
    read("parameters", client.read_parameters)
    read("units", lambda: {key: m.Units.GetUnit(key) for key in ("Length", "Frequency", "Time")})
    read("frequency", lambda: {"min": m.Solver.GetFmin(), "max": m.Solver.GetFmax()})
    read("solver", lambda: m.get_active_solver_name(timeout=10))
    read("mesh_cells", m.Mesh.GetNumberOfMeshCells)
    read("plane_wave", lambda: {"normal": m.PlaneWave.GetNormal(), "electric_vector": m.PlaneWave.GetEVector(),
                                "polarization": m.PlaneWave.GetPolarizationType()})

    def solids():
        shapes = []
        for index in range(m.Solid.GetNumberOfShapes()):
            name = m.Solid.GetNameOfShapeFromIndex(index)
            shapes.append({"name": name, "material": m.Solid.GetMaterialNameForShape(name),
                           "bounding_box": m.Solid.GetLooseBoundingBoxOfShape(name)})
        return shapes
    read("solids", solids)
    read("schematic", client.schematic_list)
    sch = client._project.schematic

    def properties():
        values = []
        for block in result.get("schematic", {}).get("blocks", []):
            obj = sch.Block
            obj.Reset(); obj.Name(block["name"])
            item = {"name": block["name"], "x": obj.GetPositionX(), "y": obj.GetPositionY(), "properties": {}}
            obj.StartPropertyIteration()
            for _ in range(10000):
                entry = obj.GetNextProperty()
                if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                    raise RuntimeError(f"Unexpected property iterator response: {entry!r}")
                name, kind, value = entry
                if not name:
                    break
                item["properties"][name] = {"value": value, "type": kind, "unit": obj.GetUnitForProperty(name)}
            else:
                raise RuntimeError("Block property iteration did not terminate")
            values.append(item)
        return values
    read("block_properties", properties)

    def tasks():
        task = sch.SimulationTask
        task.StartTaskNameIteration()
        values = []
        for _ in range(1000):
            name = task.GetNextTaskName()
            if not name:
                return values
            task.Reset(); task.Name(name)
            item = {"name": name, "type": task.GetTypeForTask(name)}
            if str(item["type"]).lower() == "transient":
                item["properties"] = {key: task.GetProperty(key) for key in (
                    "tmax", "circuit simulator", "sampling method", "nfdsamples", "docombineresults")}
            values.append(item)
        raise RuntimeError("Task iteration did not terminate")
    read("tasks", tasks)
    for key in ("parameters", "schematic"):
        if result.get(key, {}).get("status") == "error":
            result["errors"][key] = result[key]["message"]
    if result["errors"]:
        result["status"] = "partial"
    return result


async def handle(name: str, arguments: dict, client: CSTClient) -> list[TextContent]:
    try:
        if name == "cst_prepare_reference":
            result = prepare_reference(client, **arguments)
        elif name == "cst_readback":
            result = readback(client)
        elif name == "cst_read_curve":
            result = client.get_result(**arguments)
            if result.get("status") == "ok":
                import uuid
                path = Path(client.checked_project_path(client.project_path)).parent / "curves"
                path.mkdir(exist_ok=True)
                artifact = path / f"{uuid.uuid4().hex}.json"
                artifact.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                data = result.pop("data")
                result.update(artifact=str(artifact), sha256=sha256(artifact),
                              count=len(data["x"]), preview={k: v[:5] for k, v in data.items()})
        else:
            raise ValueError(f"Unknown case tool: {name}")
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


def register_case_tools(server, client):
    from mcp_cst_studio.tools import _registry
    _registry.add_module(TOOLS, handle, client)
