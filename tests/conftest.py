"""Shared test fixtures for CST Studio MCP server tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def offline_config() -> CSTConfig:
    """Config for offline mode testing."""
    return CSTConfig(
        cst_path=None,
        work_dir="/tmp/cst_test",
        version="2026",
        connected=False,
    )


@pytest.fixture
def offline_client(offline_config: CSTConfig) -> CSTClient:
    """CSTClient in offline mode (no CST installation)."""
    return CSTClient(config=offline_config)


@pytest.fixture
def mock_client() -> CSTClient:
    """CSTClient with mocked CST connection for testing connected mode.

    The mock project exposes ``modeler.execute_vba_code`` which returns
    ``"ok"`` by default — matching the real CST Python API for MWS projects.
    Patches ``CST_AVAILABLE`` so the ``connected`` property returns True.
    """
    config = CSTConfig(
        cst_path=r"C:\Program Files\CST Studio Suite 2026",
        work_dir="/tmp/cst_test",
        version="2026",
        connected=True,
    )
    client = CSTClient(config=config)
    project = MagicMock()
    # The merged execute_vba uses model3d.add_to_history (not modeler)
    project.model3d.add_to_history.return_value = None
    # Keep modeler mock for backward compat with any test that checks it
    project.modeler.execute_vba_code.return_value = "ok"
    client._project = project
    client._project_path = r"C:\test\project.cst"

    # Patch CST_AVAILABLE at the module level so client.connected returns True
    patcher_cst = patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True)
    # Patch DialogWatcher so it doesn't try real Win32 calls
    patcher_dw = patch("mcp_cst_studio.cst_client.DialogWatcher")
    patcher_cst.start()
    mock_dw_cls = patcher_dw.start()
    mock_dw_instance = MagicMock()
    mock_dw_instance.get_log.return_value = []
    mock_dw_cls.return_value = mock_dw_instance

    yield client

    # Clean up class-level dialog watcher state to prevent leaking
    CSTClient._dialog_watcher = None
    patcher_dw.stop()
    patcher_cst.stop()
