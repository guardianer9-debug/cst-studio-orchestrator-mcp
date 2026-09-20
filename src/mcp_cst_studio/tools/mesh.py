"""Mesh control tools for CST Studio Suite."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.types import MeshType
from mcp_cst_studio.validators import (
    validate_enum_value,
    validate_name,
    validate_positive,
    validate_range,
)
from mcp_cst_studio.vba_builder import VBABuilder

TOOLS: list[Tool] = [
    Tool(
        name="cst_set_mesh_type",
        description=(
            "Set the mesh type for the simulation. Hexahedral is used for time-domain, "
            "Tetrahedral for frequency-domain, Surface for integral-equation, and "
            "Hexahedral TLM for TLM solver."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_type": {
                    "type": "string",
                    "enum": ["Hexahedral", "Tetrahedral", "Surface", "Hexahedral TLM"],
                    "description": "Type of mesh to use",
                },
            },
            "required": ["mesh_type"],
        },
    ),
    Tool(
        name="cst_set_mesh_density",
        description=(
            "Set global mesh density parameters controlling automatic mesh generation. "
            "Higher cells_per_wavelength gives finer mesh and better accuracy at the "
            "cost of longer simulation time."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cells_per_wavelength": {
                    "type": "integer",
                    "description": "Number of mesh cells per wavelength (default 15)",
                    "default": 15,
                },
                "min_cells": {
                    "type": "integer",
                    "description": "Minimum number of mesh steps across any structure (default 5)",
                    "default": 5,
                },
                "ratio_limit": {
                    "type": "number",
                    "description": "Maximum ratio between adjacent mesh cells (default 20)",
                    "default": 20,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cst_add_mesh_refinement",
        description=(
            "Add local mesh refinement to a specific solid. This creates finer mesh "
            "around critical geometry features like feed points, gaps, or thin layers."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "description": "Component name containing the solid",
                },
                "solid": {
                    "type": "string",
                    "description": "Solid name to refine mesh around",
                },
                "refinement_factor": {
                    "type": "number",
                    "description": "Refinement factor — mesh cells are divided by this value (default 2.0)",
                    "default": 2.0,
                },
            },
            "required": ["component", "solid"],
        },
    ),
    Tool(
        name="cst_set_adaptive_mesh",
        description=(
            "Configure adaptive mesh refinement. When enabled, the solver runs multiple "
            "passes, refining the mesh in regions of high field gradient until the result "
            "converges within the specified threshold."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "Enable or disable adaptive meshing (default true)",
                    "default": True,
                },
                "max_passes": {
                    "type": "integer",
                    "description": "Maximum number of adaptive mesh refinement passes (default 3)",
                    "default": 3,
                },
                "threshold": {
                    "type": "number",
                    "description": "Convergence threshold in dB — stop when S-parameter change is below this (default 0.02)",
                    "default": 0.02,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cst_get_mesh_info",
        description=(
            "Get current mesh statistics and settings. In connected mode this queries "
            "the live mesh data; in offline mode it returns the VBA to retrieve mesh info."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="cst_get_mesh_quality",
        description=(
            "Extract mesh quality metrics including total cells, aspect ratios, and cells "
            "per wavelength. In connected mode this queries actual mesh statistics; in "
            "offline mode it describes what metrics would be returned."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="cst_set_pml_properties",
        description=(
            "Configure PML (Perfectly Matched Layer) absorbing boundary properties. "
            "Controls the number of absorbing layers and the target reflection level "
            "for fine-tuning radiation boundary accuracy."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "num_layers": {
                    "type": "integer",
                    "description": "Number of PML layers (4-12, default 4)",
                    "default": 4,
                },
                "reflection_level_db": {
                    "type": "number",
                    "description": "Target reflection level in dB (-80 to -20, default -40)",
                    "default": -40,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cst_add_fixpoint_mesh",
        description=(
            "Add a fixed mesh point at specific coordinates for precise field sampling. "
            "Ensures the mesh contains a node exactly at the specified location for "
            "accurate field probing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate in mm",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate in mm",
                },
                "z": {
                    "type": "number",
                    "description": "Z coordinate in mm",
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the fixed mesh point",
                },
            },
            "required": ["x", "y", "z"],
        },
    ),
    Tool(
        name="cst_set_mesh_properties",
        description=(
            "Set full global Mesh Properties (Hexahedral FIT / TLM), matching the GUI "
            "dialog: cells per wavelength near/far, cells per max model-box edge, "
            "minimum-cell ratio, and edge refinement. Use this instead of the simpler "
            "cst_set_mesh_density when you need near/far control."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_type": {
                    "type": "string",
                    "enum": ["Hexahedral", "Hexahedral TLM", "PBA"],
                    "description": "Mesh type (default Hexahedral / PBA)",
                    "default": "Hexahedral",
                },
                "steps_per_wave_near": {
                    "type": "integer",
                    "description": "Cells per wavelength near model (GUI default 10)",
                    "default": 10,
                },
                "steps_per_wave_far": {
                    "type": "integer",
                    "description": "Cells per wavelength far from model (default 15)",
                    "default": 15,
                },
                "same_as_near_wavelength": {
                    "type": "boolean",
                    "description": "Use same cells/wavelength far as near (default false)",
                    "default": False,
                },
                "steps_per_box_near": {
                    "type": "integer",
                    "description": "Cells per max model-box edge near model (default 15)",
                    "default": 15,
                },
                "steps_per_box_far": {
                    "type": "integer",
                    "description": "Cells per max model-box edge far (default 15)",
                    "default": 15,
                },
                "ratio_limit_geometry": {
                    "type": "number",
                    "description": (
                        "Minimum-cell control: fraction/ratio vs max cell "
                        "(GUI 'Fraction of maximum cell near to model', default 10)"
                    ),
                    "default": 10,
                },
                "edge_refinement": {
                    "type": "boolean",
                    "description": "Enable global edge refinement (default true)",
                    "default": True,
                },
                "edge_refinement_ratio": {
                    "type": "number",
                    "description": "Edge refinement ratio (default 2)",
                    "default": 2,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cst_set_local_mesh_properties",
        description=(
            "Set Local Mesh Properties for a solid (component:solid) or a mesh group, "
            "matching the GUI Local Mesh dialog: volume refinement (none / absolute / "
            "fraction of max cell / cells across object / ratio), edge refinement, and "
            "whether to consider global refinement. Creates the mesh group if needed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "description": "Component name (e.g. 'component1'). Required with solid.",
                },
                "solid": {
                    "type": "string",
                    "description": "Solid name (e.g. 'solid2'). Required with component.",
                },
                "mesh_group": {
                    "type": "string",
                    "description": (
                        "Optional existing mesh group name (e.g. 'meshgroup1'). "
                        "If set, applies settings to that group instead of a single solid."
                    ),
                },
                "volume_refinement": {
                    "type": "string",
                    "enum": [
                        "none",
                        "absolute",
                        "fraction",
                        "cells_across",
                        "ratio",
                    ],
                    "description": (
                        "Volume refinement type: none, absolute (max cell size), "
                        "fraction (of max cell near model), cells_across (n cells "
                        "across object), or ratio (cell size / N)"
                    ),
                    "default": "none",
                },
                "volume_value": {
                    "type": "number",
                    "description": (
                        "Value for volume refinement: mm for absolute, factor for "
                        "fraction/ratio, count for cells_across"
                    ),
                    "default": 2,
                },
                "edge_refinement": {
                    "type": "string",
                    "enum": ["none", "ratio", "steps"],
                    "description": "Local edge refinement type (default none)",
                    "default": "none",
                },
                "edge_value": {
                    "type": "number",
                    "description": "Edge refinement ratio or steps (default 2)",
                    "default": 2,
                },
                "consider_global_refinement": {
                    "type": "boolean",
                    "description": "Also apply global refinement settings (default true)",
                    "default": True,
                },
                "mesh_type": {
                    "type": "string",
                    "enum": ["Hex", "HexTLM", "PBA", "Tet"],
                    "description": "Mesh type for this local settings block (default Hex)",
                    "default": "Hex",
                },
            },
            "required": [],
        },
    ),
]

async def handle(
    name: str, arguments: dict, client: CSTClient
) -> list[TextContent]:
    """Handle a mesh tool call."""
    try:
        if name == "cst_set_mesh_type":
            return _set_mesh_type(arguments, client)
        elif name == "cst_set_mesh_density":
            return _set_mesh_density(arguments, client)
        elif name == "cst_add_mesh_refinement":
            return _add_mesh_refinement(arguments, client)
        elif name == "cst_set_adaptive_mesh":
            return _set_adaptive_mesh(arguments, client)
        elif name == "cst_get_mesh_info":
            return _get_mesh_info(arguments, client)
        elif name == "cst_get_mesh_quality":
            return _get_mesh_quality(arguments, client)
        elif name == "cst_set_pml_properties":
            return _set_pml_properties(arguments, client)
        elif name == "cst_add_fixpoint_mesh":
            return _add_fixpoint_mesh(arguments, client)
        elif name == "cst_set_mesh_properties":
            return _set_mesh_properties(arguments, client)
        elif name == "cst_set_local_mesh_properties":
            return _set_local_mesh_properties(arguments, client)

        return [TextContent(
            type="text",
            text=json.dumps({"tool": name, "status": "error", "message": f"Unknown mesh tool: {name}"}, indent=2),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"tool": name, "status": "error", "message": str(e)}, indent=2),
        )]


def _set_mesh_type(arguments: dict, client: CSTClient) -> list[TextContent]:
    mesh_type = arguments.get("mesh_type", "")
    validate_enum_value(mesh_type, MeshType, "mesh_type")

    vba = VBABuilder("Mesh")
    vba.set("MeshType", mesh_type)
    script = vba.build()

    result = client.execute_vba(script)
    result["mesh_type"] = mesh_type
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _set_mesh_density(arguments: dict, client: CSTClient) -> list[TextContent]:
    cells_per_wavelength = int(arguments.get("cells_per_wavelength", 15))
    min_cells = int(arguments.get("min_cells", 5))
    ratio_limit = float(arguments.get("ratio_limit", 20))

    validate_positive(cells_per_wavelength, "cells_per_wavelength")
    validate_positive(min_cells, "min_cells")
    validate_positive(ratio_limit, "ratio_limit")

    vba = VBABuilder("Mesh")
    vba.set_number("LinesPerWavelength", cells_per_wavelength)
    vba.set_number("MinimumStepNumber", min_cells)
    vba.set_number("RatioLimit", ratio_limit)
    script = vba.build()

    result = client.execute_vba(script)
    result["cells_per_wavelength"] = cells_per_wavelength
    result["min_cells"] = min_cells
    result["ratio_limit"] = ratio_limit
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _add_mesh_refinement(arguments: dict, client: CSTClient) -> list[TextContent]:
    component = arguments.get("component", "")
    solid = arguments.get("solid", "")
    refinement_factor = float(arguments.get("refinement_factor", 2.0))

    validate_name(component, "component")
    validate_name(solid, "solid")
    validate_positive(refinement_factor, "refinement_factor")

    vba = VBABuilder("MeshAdaption3D")
    vba.set("Name", f"{component}:{solid}")
    vba.set_number("RefinementFactor", refinement_factor)
    vba.call("SetLocalRefinement")
    script = vba.build()

    result = client.execute_vba(script)
    result["component"] = component
    result["solid"] = solid
    result["refinement_factor"] = refinement_factor
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _set_adaptive_mesh(arguments: dict, client: CSTClient) -> list[TextContent]:
    enabled = arguments.get("enabled", True)
    max_passes = int(arguments.get("max_passes", 3))
    threshold = float(arguments.get("threshold", 0.02))

    if max_passes < 1:
        max_passes = 1
    validate_range(max_passes, 1, 100, "max_passes")
    validate_positive(threshold, "threshold")

    vba = VBABuilder("MeshAdaption3D")
    vba.set_bool("Enabled", enabled)
    vba.set_number("MaxPasses", max_passes)
    vba.set_number("ConvergenceThreshold", threshold)
    script = vba.build()

    result = client.execute_vba(script)
    result["enabled"] = enabled
    result["max_passes"] = max_passes
    result["threshold"] = threshold
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _get_mesh_info(arguments: dict, client: CSTClient) -> list[TextContent]:
    # Build VBA that queries mesh statistics
    vba = VBABuilder("Mesh")
    vba.call("Update")
    script = vba.build()

    if client.connected:
        result = client.execute_vba(script)
    else:
        result = {
            "status": "offline",
            "vba": script,
            "description": (
                "In connected mode this would return mesh statistics including: "
                "total number of mesh cells, mesh type, cells per wavelength, "
                "minimum/maximum cell sizes, and mesh quality metrics. "
                "Execute the VBA in CST to update and inspect the mesh."
            ),
            "expected_fields": [
                "total_cells",
                "mesh_type",
                "cells_per_wavelength",
                "min_cell_size",
                "max_cell_size",
                "ratio_limit",
            ],
        }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _get_mesh_quality(arguments: dict, client: CSTClient) -> list[TextContent]:
    vba = VBABuilder("Mesh")
    vba.call("Update")
    script = vba.build()

    if client.connected:
        result = client.execute_vba(script)
    else:
        result = {
            "status": "offline",
            "vba": script,
            "description": (
                "In connected mode this would return mesh quality metrics including: "
                "total number of mesh cells, minimum and maximum aspect ratios, "
                "cells per wavelength at the highest frequency, and mesh quality "
                "histogram data. Execute the VBA in CST to update and inspect the mesh."
            ),
            "expected_fields": [
                "total_cells",
                "min_aspect_ratio",
                "max_aspect_ratio",
                "cells_per_wavelength",
                "mesh_quality_score",
            ],
        }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _set_pml_properties(arguments: dict, client: CSTClient) -> list[TextContent]:
    num_layers = int(arguments.get("num_layers", 4))
    reflection_level_db = float(arguments.get("reflection_level_db", -40))

    validate_range(num_layers, 4, 12, "num_layers")
    validate_range(reflection_level_db, -80, -20, "reflection_level_db")

    vba = VBABuilder("Boundary")
    vba.set_number("SetPMLMinimumLayers", num_layers)
    vba.set_number("SetPMLReflectionLevel", reflection_level_db)
    script = vba.build()

    result = client.execute_vba(script)
    result["num_layers"] = num_layers
    result["reflection_level_db"] = reflection_level_db
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _add_fixpoint_mesh(arguments: dict, client: CSTClient) -> list[TextContent]:
    x = float(arguments["x"])
    y = float(arguments["y"])
    z = float(arguments["z"])
    name = arguments.get("name")

    if name is not None:
        validate_name(name, "name")

    vba = VBABuilder("Mesh")
    if name is not None:
        vba.set("FixedPointName", name)
    vba.set_triple("AddFixedPoint", x, y, z)
    script = vba.build()

    result = client.execute_vba(script)
    result["x"] = x
    result["y"] = y
    result["z"] = z
    if name is not None:
        result["name"] = name
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


_MESH_TYPE_MAP = {
    "Hexahedral": ("PBA", "Hex"),
    "Hexahedral TLM": ("HexahedralTLM", "HexTLM"),
    "PBA": ("PBA", "Hex"),
}


def _set_mesh_properties(arguments: dict, client: CSTClient) -> list[TextContent]:
    """Full global Mesh Properties (near/far wavelength + box edge + min cell)."""
    mesh_type = arguments.get("mesh_type", "Hexahedral")
    if mesh_type not in _MESH_TYPE_MAP:
        raise ValueError(f"Invalid mesh_type '{mesh_type}'. Valid: {list(_MESH_TYPE_MAP)}")

    near_wave = int(arguments.get("steps_per_wave_near", 10))
    far_wave = int(arguments.get("steps_per_wave_far", 15))
    same_near = bool(arguments.get("same_as_near_wavelength", False))
    near_box = int(arguments.get("steps_per_box_near", 15))
    far_box = int(arguments.get("steps_per_box_far", 15))
    ratio_geom = float(arguments.get("ratio_limit_geometry", 10))
    edge_on = bool(arguments.get("edge_refinement", True))
    edge_ratio = float(arguments.get("edge_refinement_ratio", 2))

    validate_positive(near_wave, "steps_per_wave_near")
    validate_positive(far_wave, "steps_per_wave_far")
    validate_positive(near_box, "steps_per_box_near")
    validate_positive(far_box, "steps_per_box_far")
    validate_positive(ratio_geom, "ratio_limit_geometry")
    validate_positive(edge_ratio, "edge_refinement_ratio")

    mesh_cmd, settings_type = _MESH_TYPE_MAP[mesh_type]
    same_flag = "1" if same_near else "0"
    edge_flag = "1" if edge_on else "0"

    script = f"""
With Mesh
     .MeshType "{mesh_cmd}"
     .SetCreator "High Frequency"
End With
With MeshSettings
     .SetMeshType "{settings_type}"
     .Set "Version", 1%
     'MAX CELL - WAVELENGTH REFINEMENT
     .Set "StepsPerWaveNear", "{near_wave}"
     .Set "StepsPerWaveFar", "{far_wave}"
     .Set "WavelengthRefinementSameAsNear", "{same_flag}"
     'MAX CELL - GEOMETRY REFINEMENT
     .Set "StepsPerBoxNear", "{near_box}"
     .Set "StepsPerBoxFar", "{far_box}"
     .Set "MaxStepNear", "0"
     .Set "MaxStepFar", "0"
     .Set "ModelBoxDescrNear", "maxedge"
     .Set "ModelBoxDescrFar", "maxedge"
     .Set "UseMaxStepAbsolute", "0"
     .Set "GeometryRefinementSameAsNear", "1"
     'MIN CELL
     .Set "UseRatioLimitGeometry", "1"
     .Set "RatioLimitGeometry", "{_fmt(ratio_geom)}"
     .Set "MinStepGeometryX", "0"
     .Set "MinStepGeometryY", "0"
     .Set "MinStepGeometryZ", "0"
     .Set "UseSameMinStepGeometryXYZ", "1"
End With
With MeshSettings
     .SetMeshType "{settings_type}"
     .Set "EdgeRefinementOn", "{edge_flag}"
     .Set "EdgeRefinementPolicy", "1"
     .Set "EdgeRefinementRatio", "{_fmt(edge_ratio)}"
     .Set "EdgeRefinementStep", "0"
     .Set "EdgeRefinementBufferLines", "3"
End With
""".strip()

    result = client.execute_vba(script, history_label="set mesh properties (global near/far)")
    result.update(
        {
            "mesh_type": mesh_type,
            "steps_per_wave_near": near_wave,
            "steps_per_wave_far": far_wave,
            "steps_per_box_near": near_box,
            "ratio_limit_geometry": ratio_geom,
        }
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _fmt(v: float) -> str:
    if float(v) == int(v):
        return str(int(v))
    return f"{v:g}"


# Map user volume_refinement -> CST VolumeRefinementType + value key
_VOL_TYPE = {
    "none": ("NONE", "VolumeRefinementStep"),
    "absolute": ("ABSOLUTE", "VolumeRefinementStep"),
    "fraction": ("FRACTION_OF_MAX", "VolumeRefinementStep"),
    "cells_across": ("STEPS_PER_DIM", "VolumeRefinementNumSteps"),
    "ratio": ("RATIO", "VolumeRefinementRatio"),
}


def _set_local_mesh_properties(arguments: dict, client: CSTClient) -> list[TextContent]:
    """Local Mesh Properties via mesh group (official CST pattern).

    Order matters (from CST ConfigurationWizard / demo macros):
      1) Mesh.MeshType + MeshSettings.SetMeshType "Hex"
      2) Group.Add mesh group
      3) optional Group.AddItem solid
      4) MeshSettings.ItemMeshSettings("group$...") settings
    """
    component = arguments.get("component") or ""
    solid = arguments.get("solid") or ""
    mesh_group = arguments.get("mesh_group") or ""
    vol = arguments.get("volume_refinement", "none")
    vol_val = float(arguments.get("volume_value", 2))
    edge = arguments.get("edge_refinement", "none")
    edge_val = float(arguments.get("edge_value", 2))
    consider_global = bool(arguments.get("consider_global_refinement", True))
    mesh_type = arguments.get("mesh_type", "Hex")

    if vol not in _VOL_TYPE:
        raise ValueError(f"Invalid volume_refinement '{vol}'. Valid: {list(_VOL_TYPE)}")
    if edge not in ("none", "ratio", "steps"):
        raise ValueError(f"Invalid edge_refinement '{edge}'. Valid: none, ratio, steps")
    if mesh_type not in ("Hex", "HexTLM", "PBA", "Tet"):
        raise ValueError(f"Invalid mesh_type '{mesh_type}'. Valid: Hex, HexTLM, PBA, Tet")
    validate_positive(vol_val, "volume_value")
    validate_positive(edge_val, "edge_value")

    if not mesh_group:
        if component and solid:
            mesh_group = f"mg_{component}_{solid}".replace(":", "_")
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "message": "Provide mesh_group, or both component and solid",
                        },
                        indent=2,
                    ),
                )
            ]
    else:
        validate_name(mesh_group, "mesh_group")

    if component and solid:
        validate_name(component, "component")
        validate_name(solid, "solid")
        solid_key = f"solid${component}:{solid}"
    else:
        solid_key = None

    # Map user types to CST keys used in official examples
    if vol == "absolute":
        # GUI Absolute value: max cell size mm (same xyz)
        vol_sets = [
            f'.Set "VolumeRefinementType", "ABSOLUTE"',
            f'.Set "Step", "{_fmt(vol_val)}", "{_fmt(vol_val)}", "{_fmt(vol_val)}"',
        ]
    elif vol == "fraction":
        vol_sets = [
            f'.Set "VolumeRefinementType", "FRACTION"',
            f'.Set "VolumeRefinementStep", "{_fmt(vol_val)}", "{_fmt(vol_val)}", "{_fmt(vol_val)}"',
            f'.Set "VolumeRefinementValueUseSameXYZ", 1',
        ]
    elif vol == "cells_across":
        vol_sets = [
            f'.Set "VolumeRefinementType", "STEPS_PER_DIM"',
            f'.Set "VolumeRefinementExtentType", "STEPS_PER_DIM"',
            f'.Set "VolumeRefinementExtentNumSteps", {_fmt(vol_val)}, {_fmt(vol_val)}, {_fmt(vol_val)}',
            f'.Set "VolumeRefinementExtentValueUseSameXYZ", 1',
        ]
    elif vol == "ratio":
        vol_sets = [
            f'.Set "VolumeRefinementType", "RATIO"',
            f'.Set "VolumeRefinementRatio", "1", "{_fmt(vol_val)}", "{_fmt(vol_val)}"',
            f'.Set "VolumeRefinementValueUseSameXYZ", 0',
        ]
    else:  # none
        vol_sets = [f'.Set "VolumeRefinementType", "NONE"']

    if edge == "ratio":
        edge_sets = [
            f'.Set "UseEdgeRefinement", 1',
            f'.Set "EdgeRefinementType", "RATIO"',
            f'.Set "EdgeRefinementRatio", "{_fmt(edge_val)}"',
        ]
    elif edge == "steps":
        edge_sets = [
            f'.Set "UseEdgeRefinement", 1',
            f'.Set "EdgeRefinementType", "STEPS"',
            f'.Set "EdgeRefinementStep", "{_fmt(edge_val)}"',
        ]
    else:
        edge_sets = [f'.Set "EdgeRefinementType", "NONE"']

    cons = "1" if consider_global else "0"
    mesh_cmd = "PBA" if mesh_type in ("Hex", "PBA") else (
        "HexahedralTLM" if mesh_type == "HexTLM" else mesh_type
    )

    lines = [
        f"With Mesh",
        f'     .MeshType "{mesh_cmd}"',
        f"End With",
        f"With MeshSettings",
        f'     .SetMeshType "{mesh_type}"',
        f"End With",
        f'Group.Add "{_escape(mesh_group)}", "mesh"',
    ]
    if solid_key:
        lines.append(f'Group.AddItem "{_escape(solid_key)}", "{_escape(mesh_group)}"')

    lines += [
        "With MeshSettings",
        f'     With .ItemMeshSettings ("group${_escape(mesh_group)}")',
        f'          .SetMeshType "{mesh_type}"',
        f'          .Set "ConsiderGlobalRefinement", {cons}',
        f'          .Set "ConsiderGlobalEdgeRefinement", {cons}',
        f'          .Set "ConsiderGlobalFaceRefinement", {cons}',
        f'          .Set "ConsiderGlobalMaterialRefinement", {cons}',
    ]
    for s in vol_sets + edge_sets:
        lines.append(f"          {s}")
    lines += [
        "     End With",
        "End With",
    ]

    script = "\n".join(lines)
    label = f"set local mesh properties for group {mesh_group}"
    result = client.execute_vba(script, history_label=label)
    result.update(
        {
            "mesh_group": mesh_group,
            "solid_key": solid_key,
            "volume_refinement": vol,
            "volume_value": vol_val,
            "edge_refinement": edge,
            "mesh_type": mesh_type,
            "vba": script,
        }
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _escape(s: str) -> str:
    return s.replace('"', '""')


def register_mesh_tools(server: Server, client: CSTClient) -> None:
    """Register mesh tools with the MCP server."""
    from mcp_cst_studio.tools import _registry
    _registry.add_module(TOOLS, handle, client)
