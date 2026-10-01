"""Raw VBA access tools for CST Studio Suite.

Provides 3 MCP tools for executing arbitrary VBA code (with safety validation),
looking up VBA object reference documentation, and listing available CST VBA objects.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp.types import TextContent, Tool

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.validators import validate_vba_input
from mcp_cst_studio.official_help import lookup, list_objects

if TYPE_CHECKING:
    from mcp.server import Server

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    # 1. Execute raw VBA
    Tool(
        name="cst_execute_vba",
        description=(
            "Execute raw VBA code in the CST 3D model only. For schematic Block/Net/Task use "
            "cst_schematic_call; 3D failures are never replayed in the schematic. "
            "For a 3D discrete port use cst_delete_port. The code is validated for "
            "safety (shell access, file I/O, and external process execution are "
            "blocked). In connected mode the code runs directly; in offline mode "
            "the validated script is returned for manual execution."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "VBA code to execute in CST Studio. Must not contain "
                        "shell commands, file I/O, or external process calls."
                    ),
                },
            },
            "required": ["code"],
        },
    ),

    # 2. VBA help / reference
    Tool(
        name="cst_vba_help",
        description=(
            "Read installed official CST HTML help, with source path/hash and configured version. "
            "Query exact object_name and optional method_name; use domain to distinguish 3d/schematic/cable. "
            "section=example returns official examples only. Long excerpts paginate via next_offset. "
            "Missing sources/methods never fall back to bundled summaries. This is reference, not execution verification."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": (
                        "Name of the CST VBA object to look up, e.g. 'Brick', "
                        "'Solid', 'Material', 'DiscretePort', 'Block', 'SimulationTask'."
                    ),
                },
                "method_name": {"type": "string", "description": "Exact method name, e.g. ChangeMaterial."},
                "domain": {"type": "string", "enum": ["3d", "schematic", "cable"]},
                "section": {"type": "string", "enum": ["object", "example"], "default": "object"},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "max_chars": {"type": "integer", "minimum": 256, "maximum": 24000, "default": 10000},
            },
            "required": ["object_name"],
        },
    ),

    # 3. List VBA objects
    Tool(
        name="cst_list_vba_objects",
        description=(
            "List available CST Studio VBA objects, optionally filtered by category. "
            "Returns the curated official-help path index and local availability. Not a complete CST API catalog."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "geometry",
                        "solver",
                        "material",
                        "mesh",
                        "boundary",
                        "excitation",
                        "monitor",
                        "postprocessing",
                        "optimization",
                        "settings",
                        "interaction",
                        "schematic",
                        "cable",
                    ],
                    "description": (
                        "Optional category filter. If omitted, all categories are returned."
                    ),
                },
            },
            "required": [],
        },
    ),
]


def _handle_execute_vba(args: dict, client: CSTClient) -> dict:
    """Validate and execute raw VBA code."""
    code = args.get("code", "")
    if not code.strip():
        return {"status": "error", "message": "VBA code cannot be empty"}

    # Safety validation — raises ValidationError on dangerous patterns
    validate_vba_input(code)

    result = client.execute_vba(code)
    return result


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def _text(data: dict) -> list[TextContent]:
    """Wrap a dict as a single JSON TextContent response."""
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


async def handle(name: str, arguments: dict, client: CSTClient) -> list[TextContent]:
    """Handle a VBA tool call.

    Routes to the appropriate handler and returns results wrapped in TextContent.
    """
    try:
        if name == "cst_execute_vba":
            result = _handle_execute_vba(arguments, client)
            return _text(result)

        elif name == "cst_vba_help":
            result = lookup(client._config, arguments)
            return _text(result)

        elif name == "cst_list_vba_objects":
            result = list_objects(client._config, arguments.get("category"))
            return _text(result)

        return _text({"status": "error", "message": f"Unknown VBA tool: {name}"})

    except Exception as e:
        return _text({"status": "error", "message": str(e)})


# ---------------------------------------------------------------------------
# Registration helper (called from tools/__init__.py)
# ---------------------------------------------------------------------------


def register_vba_tools(server: Server, client: CSTClient) -> None:
    """Register VBA tools with the MCP server."""
    from mcp_cst_studio.tools import _registry
    _registry.add_module(TOOLS, handle, client)
