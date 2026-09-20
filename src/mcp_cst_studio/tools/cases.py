"""Reference copies and actual readback, using the existing CST client."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
import xml.etree.ElementTree as ET
import re
import struct

from mcp.types import TextContent, Tool

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.vba_builder import VBABuilder
from mcp_cst_studio.config import CSTConfig


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
    Tool(name="cst_publish_view", description=(
        "Save the current independent project, read it back and export a CAD preview for the PiDeck viewer. "
        "Publish an immutable snapshot and any curves previously read by cst_read_curve. Does not solve."),
        inputSchema={"type": "object", "properties": {
            "label": {"type": "string"}, "reproduction_kind": {"type": "string",
                "enum": ["reference_operation", "modified_variant", "rebuilt_from_scratch"]}},
            "required": ["label", "reproduction_kind"], "additionalProperties": False}),
    Tool(name="cst_run_task", description=(
        "Execute an existing schematic task asynchronously with durable status and time/RSS limits. "
        "Use cst_get_simulation_status and cst_stop_simulation. Stop first requests native 3D abort; "
        "if the task remains blocked after 15 seconds, only its owned CST process tree is terminated, "
        "preserving the saved copy and partial evidence. This is not a claim of native DS cancellation."),
        inputSchema={"type": "object", "properties": {
            "task": {"type": "string"}, "max_seconds": {"type": "integer", "minimum": 10, "maximum": CSTConfig.from_env().max_run_seconds},
            "max_rss_gb": {"type": "number", "minimum": 1, "maximum": CSTConfig.from_env().max_run_rss_gb}},
            "required": ["task"], "additionalProperties": False}),
    Tool(name="cst_read_farfield_cut", description=(
        "Read a real 3D farfield's directivity versus theta at a fixed phi. Select an exact "
        "3D leaf under Farfields from cst_project_tree, not a nested Farfield Cuts entry. "
        "Stores linear directivity and angles as an immutable local curve. No solver is started."),
        inputSchema={"type": "object", "properties": {
            "tree_path": {"type": "string"}, "phi": {"type": "number", "default": 0},
            "step_degrees": {"type": "number", "minimum": 1, "maximum": 30, "default": 5}},
            "required": ["tree_path"], "additionalProperties": False}),
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
    read("port_count", m.Solver.GetNumberOfPorts)
    read("ports", client.list_ports)
    read("plane_wave", lambda: {"normal": m.PlaneWave.GetNormal(), "electric_vector": m.PlaneWave.GetEVector(),
                                "polarization": m.PlaneWave.GetPolarizationType()})
    if "Error reading plane wave normal vector" in result["errors"].get("plane_wave", ""):
        result["plane_wave"] = {"status": "not_configured"}
        del result["errors"]["plane_wave"]

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
    def field_probes():
        probes = []
        active = m.Probe.GetFirst()
        while active:
            probes.append({"caption": m.Probe.GetCaption(), "field": m.Probe.GetField(),
                           "coordinate_system": m.Probe.GetCoordinateSystemType(),
                           "position": [m.Probe.GetPosition1(), m.Probe.GetPosition2(), m.Probe.GetPosition3()],
                           "orientation": m.Probe.GetOrientation()})
            if len(probes) >= 10000:
                raise RuntimeError("Probe iteration limit reached")
            active = m.Probe.GetNext()
        return probes
    read("field_probes", field_probes)
    def circuit_probes():
        probes = []
        sch.CircuitProbe.StartProbeNameIteration()
        for _ in range(10000):
            name = sch.CircuitProbe.GetNextProbeName()
            if not name:
                return probes
            sch.CircuitProbe.Name(name)
            probes.append({"name": name, "type": sch.CircuitProbe.GetType()})
        raise RuntimeError("Circuit probe iteration limit reached")
    read("circuit_probes", circuit_probes)
    signal_dir = Path(client.project_path).with_suffix("") / "Model" / "3D"
    read("user_signals", lambda: [{"name": p.stem, "source": "expanded_project_file",
                                   "sha256": sha256(p), "bytes": p.stat().st_size}
                                  for p in sorted(signal_dir.glob("*.usf"))])
    # Cable Studio exposes the saved harness as XML. Keep its provenance explicit:
    # this is the expanded project file, not a native CableStudio property getter.
    harness = Path(client.project_path).with_suffix("") / "Model" / "CBLS" / "Harness" / "harness.slh"
    if harness.is_file():
        read("cable", lambda: read_harness(harness))
    for key in ("parameters", "schematic", "ports"):
        if result.get(key, {}).get("status") == "error":
            result["errors"][key] = result[key]["message"]
    if result["errors"]:
        result["status"] = "partial"
    return result


def read_harness(path: Path) -> dict:
    if path.stat().st_size > 10_000_000:
        raise ValueError("Harness exceeds the current readback size limit")
    root = ET.parse(path).getroot()
    return {"source": "expanded_project_file", "sha256": sha256(path), "unit": root.get("UNITS"),
            "knots": [{"id": k.get("ID"), "position": [float(k.get(a)) for a in ("X", "Y", "Z")]}
                      for k in root.findall("./Knots/Knot")],
            "routes": [{"id": r.get("ID"), "knots": [k.get("ID") for k in r.findall("./Traces/Trace/TraceKnot")]}
                       for r in root.findall("./Routes/Route")],
            "cables": [dict(c.attrib) for c in root.findall("./Cabling/CableInstance")]}


def publish_view(client: CSTClient, label: str, reproduction_kind: str) -> dict:
    if not client.connected or not client.project_path:
        raise ValueError("Open an independent project first")
    saved = client.save_project()
    if saved.get("status") != "saved":
        return saved
    snapshot = readback(client)
    root = Path(client._config.work_dir).resolve() / "views"
    folder = root / uuid.uuid4().hex
    folder.mkdir(parents=True)
    snapshot.update(case_label=label, reproduction_kind=reproduction_kind, curves=[])
    try:
        model = client._project.model3d
        # CST 2025.2 exposes this private no-history entry point. It is used only
        # for the fixed exporter recipe, never as an unvalidated user-code tool.
        if snapshot["version"] != "Version 2025.2 - Dec 16 2024":
            raise RuntimeError("CAD no-history exporter requires validation on this CST build")
        before = json.dumps(model._GetHistory(), sort_keys=True)
        meshes = []
        for index, solid in enumerate(snapshot.get("solids", [])):
            component, name = solid["name"].rsplit(":", 1)
            cad = folder / f"shape-{index}.stl"
            code = (VBABuilder("STL").call("Reset").set("FileName", str(cad))
                    .set("Name", name).set("Component", component)
                    .set("ExportFileUnits", snapshot["units"]["Length"])
                    .set_bool("ExportFromActiveCoordinateSystem", False).call("Write").build())
            model._execute_vba_code("Sub Main()\n" + code + "\nEnd Sub", timeout=30)
            bounds = stl_bounds(cad)
            expected = solid["bounding_box"][1:]
            tolerance = max(1e-6, max(expected[i+1]-expected[i] for i in (0, 2, 4)) * .002)
            if any(abs(a-b) > tolerance for a, b in zip(bounds, expected)):
                raise RuntimeError(f"CAD bounds/units disagree with live shape: {solid['name']}")
            meshes.append({"file": cad.name, "object": solid["name"], "material": solid["material"],
                           "sha256": sha256(cad), "bounds": bounds})
        if json.dumps(model._GetHistory(), sort_keys=True) != before:
            raise RuntimeError("CAD export changed the model history")
        snapshot["cad"] = {"meshes": meshes, "source": "CST STL export",
                           "unit_check": "per_shape_bounds_pass", "history_unchanged": True}
    except Exception as exc:
        snapshot["errors"]["cad_export"] = str(exc)
        snapshot["status"] = "partial"
    source_curves = Path(client.project_path).parent / "curves"
    seen_curves = set()
    for path in sorted(source_curves.glob("*.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if Path(metadata["project"]).resolve() != Path(client.project_path).resolve():
            continue
        digest = sha256(path)
        if digest in seen_curves:
            continue
        seen_curves.add(digest)
        shutil.copy2(path, folder / path.name)
        snapshot["curves"].append({"file": path.name, "label": metadata["tree_path"], "sha256": digest})
    snapshot["curves"].sort(key=lambda item: ("S-Parameters" not in item["label"], item["label"]))
    target = folder / "snapshot.json"
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "published", "snapshot": str(target), "readback_status": snapshot["status"],
            "sha256": sha256(target), "curves": len(snapshot["curves"]), "errors": snapshot["errors"]}


def stl_bounds(path: Path) -> list[float]:
    """Check exported coordinates before displaying them in the model's units."""
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("Missing or empty STL")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) == 84 + count * 50:
        points = (struct.unpack_from("<3f", data, 84 + i*50 + 12 + vertex*12)
                  for i in range(count) for vertex in range(3))
    else:
        matches = re.findall(r"(?mi)^\s*vertex\s+([-+.0-9eE]+)\s+([-+.0-9eE]+)\s+([-+.0-9eE]+)",
                             data.decode("ascii", errors="strict"))
        points = (tuple(map(float, p)) for p in matches)
    import math
    mins, maxs, n = [math.inf]*3, [-math.inf]*3, 0
    for point in points:
        if not all(math.isfinite(v) for v in point):
            raise ValueError("Non-finite CAD coordinate")
        for axis in range(3):
            mins[axis], maxs[axis] = min(mins[axis], point[axis]), max(maxs[axis], point[axis])
        n += 1
    if not n:
        raise ValueError("STL contains no vertices")
    return [v for axis in range(3) for v in (mins[axis], maxs[axis])]


def read_farfield_cut(client: CSTClient, tree_path: str, phi: float = 0, step_degrees: float = 5) -> dict:
    import math
    if not client.connected or not client.has_project:
        raise ValueError("Open a project with completed farfield results")
    if not 1 <= step_degrees <= 30 or not math.isfinite(phi):
        raise ValueError("Invalid angular sampling")
    model = client._project.model3d
    if model.is_solver_running(timeout=10):
        raise ValueError("Wait for the solver to finish")
    if tree_path.count("\\") != 1 or not tree_path.startswith("Farfields\\"):
        raise ValueError("Select the 3D farfield leaf, not a generated 1D cut")
    if tree_path not in model.get_tree_items(timeout=10):
        raise ValueError("Farfield tree item does not exist")
    if model.GetApplicationVersion() != "Version 2025.2 - Dec 16 2024":
        raise ValueError("Farfield plot setup has not been validated on this CST build")
    if not model.SelectTreeItem(tree_path):
        raise ValueError("CST rejected the farfield selection")
    angles = [i * step_degrees for i in range(int(180 / step_degrees) + 1)]
    builder = (VBABuilder("FarfieldPlot").call("Reset").set("SetPlotMode", "directivity")
               .set_bool("SetScaleLinear", True).call("Plot"))
    for theta in angles:
        builder.call_with_args("AddListEvaluationPoint", str(theta), str(phi), "0", "spherical", "", "0")
    builder.call_with_args("CalculateList", "")
    model._execute_vba_code("Sub Main()\n" + builder.build() + "\nEnd Sub", timeout=30)
    values = list(model.FarfieldPlot.GetList("spherical abs"))
    if len(values) != len(angles):
        raise ValueError("Farfield result count does not match requested angles")
    if not all(math.isfinite(v) and v >= 0 for v in values):
        raise ValueError("Farfield returned non-finite or negative linear directivity")
    curve = {"status": "ok", "project": client.project_path, "domain": "3d",
             "tree_path": f"{tree_path} / phi={phi}", "run_id": "selected CST farfield",
             "retrieved_at": time.time(), "representation": "real", "quantity": "directivity",
             "xlabel": "theta / degree", "ylabel": "Directivity (linear)",
             "data": {"x": angles, "real": values, "imag": [0.0] * len(values)}}
    directory = Path(client.checked_project_path(client.project_path)).parent / "curves"
    directory.mkdir(exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(curve, indent=2), encoding="utf-8")
    return {"status": "ok", "artifact": str(path), "sha256": sha256(path),
            "count": len(values), "maximum_directivity_dbi": 10 * math.log10(max(values)),
            "phi": phi, "tree_path": tree_path}


async def handle(name: str, arguments: dict, client: CSTClient) -> list[TextContent]:
    try:
        if name == "cst_prepare_reference":
            result = prepare_reference(client, **arguments)
        elif name == "cst_readback":
            result = readback(client)
        elif name == "cst_read_curve":
            result = client.get_result(**arguments)
            if result.get("status") == "ok":
                path = Path(client.checked_project_path(client.project_path)).parent / "curves"
                path.mkdir(exist_ok=True)
                artifact = path / f"{uuid.uuid4().hex}.json"
                artifact.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                data = result.pop("data")
                result.update(artifact=str(artifact), sha256=sha256(artifact),
                              count=len(data["x"]), preview={k: v[:5] for k, v in data.items()})
        elif name == "cst_publish_view":
            result = publish_view(client, **arguments)
        elif name == "cst_run_task":
            from mcp_cst_studio.task_runner import start_task
            result = start_task(client, **arguments)
        elif name == "cst_read_farfield_cut":
            result = read_farfield_cut(client, **arguments)
        else:
            raise ValueError(f"Unknown case tool: {name}")
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


def register_case_tools(server, client):
    from mcp_cst_studio.tools import _registry
    _registry.add_module(TOOLS, handle, client)
