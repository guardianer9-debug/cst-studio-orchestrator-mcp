"""Tool registration aggregator for CST Studio MCP server.

Each tool module exposes:
  - ``TOOLS``: list of ``mcp.types.Tool`` definitions
  - ``handle(name, arguments, client)``: async dispatcher
  - ``register_*_tools(server, client)``: convenience to add both

The ``ToolRegistry`` collects tools and handlers from every module,
then wires a single ``@server.list_tools`` / ``@server.call_tool``
pair so the MCP protocol sees all tools in one list.
"""

from __future__ import annotations

import logging
import json
import uuid
import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, cast

from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server import Server

    from mcp_cst_studio.cst_client import CSTClient

# Type alias for an async tool handler
ToolHandler = Callable[[str, dict], Awaitable[list[TextContent]]]


class ToolRegistry:
    """Accumulates Tool definitions and their handlers across modules."""

    def __init__(self) -> None:
        self._tools: list[Tool] = []
        self._handlers: dict[str, ToolHandler] = {}

    def clear(self) -> None:
        """Remove all registered tools and handlers."""
        self._tools.clear()
        self._handlers.clear()

    # -- public API used by each register_*_tools function --

    def add_tool(self, tool: Tool, handler: ToolHandler) -> None:
        """Register a single tool definition with its handler."""
        self._tools.append(tool)
        self._handlers[tool.name] = handler

    def add_module(
        self,
        tools: list[Tool],
        handle_fn: Callable[..., Awaitable[list[TextContent]]],
        client: CSTClient,
    ) -> None:
        """Register an entire tool module (TOOLS list + handle function)."""
        for tool in tools:
            self._tools.append(tool)
            # Bind *client* at registration time so each call gets the right ref
            async def guarded(name, args, _h=handle_fn, _c=client):
                from mcp_cst_studio.operation_policy import check_paused, check_external_change
                check_paused(_c, name, args)
                if name not in ("cst_close_project", "cst_reload_project", "cst_connection_status", "cst_get_simulation_status", "cst_stop_simulation"):
                    check_external_change(_c)
                if getattr(_c, "_task_job", None) and name not in (
                    "cst_get_simulation_status", "cst_stop_simulation", "cst_connection_status", "cst_read_project_log"
                ):
                    from mcp_cst_studio.task_runner import task_status, TERMINAL
                    state = task_status(_c)
                    if state["state"] not in TERMINAL:
                        return [TextContent(type="text", text=json.dumps({"status": "error",
                            "message": "Schematic task owns the project; only status/stop is available",
                            "job_id": state["job_id"]}))]
                from mcp_cst_studio.operation_policy import prepare_edit
                prepare_edit(_c, name, args)
                return await _h(name, args, _c)
            self._handlers[tool.name] = guarded

    # -- internal: wire into the MCP server --

    def install(self, server: Server) -> None:
        """Create the ``list_tools`` / ``call_tool`` MCP handlers."""
        tools = list(self._tools)
        handlers = dict(self._handlers)
        execution_lock = asyncio.Lock()

        @server.list_tools()
        async def _list_tools() -> list[Tool]:
            return tools

        @server.call_tool()
        async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
            handler = handlers.get(name)
            if handler is None:
                raise ValueError(f"Unknown tool: {name}")
            logger.debug("Dispatching tool: %s", name)
            from mcp_cst_studio.evidence import record
            call_id = uuid.uuid4().hex
            record({"event": "tool_start", "call_id": call_id, "tool": name, "arguments": arguments})
            try:
                # CST remote objects keep selection/plot state. Each tool must
                # finish before another request can change that state.
                async with execution_lock:
                    result = await handler(name, arguments)
            except BaseException as exc:
                record({"event": "tool_exception", "call_id": call_id,
                        "error": type(exc).__name__, "message": str(exc)})
                raise
            record({"event": "tool_result", "call_id": call_id,
                    "content": [item.model_dump() for item in result]})
            # Keep the existing TextContent contract and expose protocol-level errors.
            from mcp.types import CallToolResult
            failed = False
            for item in result:
                try:
                    payload = json.loads(item.text)
                    failed |= payload.get("status") in ("error", "unknown", "unsupported")
                except (ValueError, AttributeError):
                    pass
            return CallToolResult(content=result, isError=failed)

        # The desktop bridge uses the exact same dispatcher, evidence and lock.
        self.invoke = _call_tool


# Module-level registry shared across register_* calls
_registry = ToolRegistry()


def register_all_tools(server: Server, client: CSTClient) -> None:
    """Register all tool modules with the MCP server."""
    _registry.clear()  # prevent duplicate registration on repeated calls
    from mcp_cst_studio.tools.antenna_templates import register_antenna_template_tools
    from mcp_cst_studio.tools.arrays import register_array_tools
    from mcp_cst_studio.tools.boolean import register_boolean_tools
    from mcp_cst_studio.tools.boundaries import register_boundary_tools
    from mcp_cst_studio.tools.diagnostics import register_diagnostics_tools
    from mcp_cst_studio.tools.geometry import register_geometry_tools
    from mcp_cst_studio.tools.import_export import register_import_export_tools
    from mcp_cst_studio.tools.materials import register_material_tools
    from mcp_cst_studio.tools.mesh import register_mesh_tools
    from mcp_cst_studio.tools.optimization import register_optimization_tools
    from mcp_cst_studio.tools.parameters import register_parameter_tools
    from mcp_cst_studio.tools.pcb import register_pcb_tools
    from mcp_cst_studio.tools.ports import register_port_tools
    from mcp_cst_studio.tools.project import register_project_tools
    from mcp_cst_studio.tools.results import register_result_tools
    from mcp_cst_studio.tools.schematic import register_schematic_tools
    from mcp_cst_studio.tools.simulation import register_simulation_tools
    from mcp_cst_studio.tools.solvers import register_solver_tools
    from mcp_cst_studio.tools.transforms import register_transform_tools
    from mcp_cst_studio.tools.matching import register_matching_tools
    from mcp_cst_studio.tools.vba import register_vba_tools
    from mcp_cst_studio.tools.cases import register_case_tools

    register_project_tools(server, client)
    register_geometry_tools(server, client)
    register_boolean_tools(server, client)
    register_transform_tools(server, client)
    register_material_tools(server, client)
    register_port_tools(server, client)
    register_boundary_tools(server, client)
    register_mesh_tools(server, client)
    register_solver_tools(server, client)
    register_simulation_tools(server, client)
    register_result_tools(server, client)
    register_import_export_tools(server, client)
    register_parameter_tools(server, client)
    register_optimization_tools(server, client)
    register_diagnostics_tools(server, client)
    register_antenna_template_tools(server, client)
    register_array_tools(server, client)
    register_pcb_tools(server, client)
    register_matching_tools(server, client)
    register_schematic_tools(server, client)
    register_vba_tools(server, client)
    register_case_tools(server, client)

    # Wire accumulated tools into the MCP server protocol
    _registry.install(server)
