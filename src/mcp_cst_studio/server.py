"""MCP server entry point for CST Studio Suite."""

from __future__ import annotations

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.tools import register_all_tools

logger = logging.getLogger(__name__)


def create_server() -> tuple[Server, CSTClient]:
    """Create and configure the MCP server."""
    server = Server("mcp-cst-studio")
    client = CSTClient()

    register_all_tools(server, client)

    return server, client


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    server, client = create_server()
    connection = client.connect()
    logger.info("CST client status: %s", connection)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point."""
    import os

    level = os.environ.get("CST_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
