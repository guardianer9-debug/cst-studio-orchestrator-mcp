"""Tests for CSTClient -- offline mode, execute_vba, execute_vba_silent, DialogWatcher integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def offline_client() -> CSTClient:
    """CSTClient configured for offline mode (no CST installation)."""
    return CSTClient(config=CSTConfig(connected=False))


@pytest.fixture
def mock_client() -> CSTClient:
    """CSTClient with mocked CST project for testing connected-mode paths."""
    config = CSTConfig(
        cst_path=r"C:\Program Files\CST Studio Suite 2026",
        work_dir="/tmp/cst_test",
        version="2026",
        connected=True,
    )
    client = CSTClient(config=config)
    client._project = MagicMock()
    client._project_path = r"C:\test\project.cst"
    # Patch CST_AVAILABLE at module level so client.connected returns True
    with patch("mcp_cst_studio.cst_client.CST_AVAILABLE", True), \
         patch("mcp_cst_studio.cst_client.DialogWatcher") as mock_dw_cls:
        mock_dw_instance = MagicMock()
        mock_dw_instance.get_log.return_value = []
        mock_dw_cls.return_value = mock_dw_instance
        yield client
    # Clean up class-level dialog watcher state
    CSTClient._dialog_watcher = None


# ---------------------------------------------------------------------------
# execute_vba — offline mode
# ---------------------------------------------------------------------------

class TestExecuteVBAOffline:
    def test_returns_offline_status(self, offline_client: CSTClient):
        result = offline_client.execute_vba("With Brick\nEnd With")
        assert result["status"] == "offline"

    def test_returns_vba_code_unchanged(self, offline_client: CSTClient):
        code = "With Brick\n  .Name \"Box1\"\nEnd With"
        result = offline_client.execute_vba(code)
        assert result["vba"] == code

    def test_offline_result_contains_message(self, offline_client: CSTClient):
        result = offline_client.execute_vba("MsgBox \"hello\"")
        assert "message" in result

    def test_empty_vba_still_returns_offline(self, offline_client: CSTClient):
        result = offline_client.execute_vba("")
        assert result["status"] == "offline"
        assert result["vba"] == ""


# ---------------------------------------------------------------------------
# execute_vba_silent — offline mode
# ---------------------------------------------------------------------------

class TestExecuteVbaSilentOffline:
    def test_returns_offline_status(self, offline_client: CSTClient):
        vba = 'Sub Main()\nDim x As Double\nEnd Sub'
        result = offline_client.execute_vba_silent(vba)
        assert result["status"] == "offline"
        assert "vba" in result

    def test_returns_silent_message(self, offline_client: CSTClient):
        result = offline_client.execute_vba_silent("Sub Main()\nEnd Sub")
        assert "silent" in result.get("message", "").lower()


# ---------------------------------------------------------------------------
# status() — offline mode
# ---------------------------------------------------------------------------

class TestStatusOffline:
    def test_mode_is_offline(self, offline_client: CSTClient):
        status = offline_client.status()
        assert status["mode"] == "offline"

    def test_project_open_is_false(self, offline_client: CSTClient):
        status = offline_client.status()
        assert status["project_open"] is False

    def test_project_path_is_none(self, offline_client: CSTClient):
        status = offline_client.status()
        assert status["project_path"] is None

    def test_cst_version_reported(self, offline_client: CSTClient):
        status = offline_client.status()
        assert "cst_version" in status

    def test_work_dir_reported(self, offline_client: CSTClient):
        status = offline_client.status()
        assert "work_dir" in status

    def test_cst_available_key_present(self, offline_client: CSTClient):
        status = offline_client.status()
        assert "cst_available" in status

    def test_connected_property_is_false(self, offline_client: CSTClient):
        assert offline_client.connected is False

    def test_mode_property_is_offline(self, offline_client: CSTClient):
        assert offline_client.mode == "offline"


# ---------------------------------------------------------------------------
# new_project — offline mode stores path
# ---------------------------------------------------------------------------

class TestNewProjectOffline:
    def test_returns_offline_status(self, offline_client: CSTClient):
        result = offline_client.new_project("/tmp/test.cst")
        assert result["status"] == "offline"

    def test_path_echoed_in_result(self, offline_client: CSTClient):
        result = offline_client.new_project("/tmp/my_project.cst")
        assert result["path"] == "/tmp/my_project.cst"

    def test_project_type_echoed(self, offline_client: CSTClient):
        result = offline_client.new_project("/tmp/test.cst", project_type="MWS")
        assert result["type"] == "MWS"

    def test_offline_contains_message(self, offline_client: CSTClient):
        result = offline_client.new_project("/tmp/test.cst")
        assert "message" in result


# ---------------------------------------------------------------------------
# open_project — offline mode stores path
# ---------------------------------------------------------------------------

class TestOpenProjectOffline:
    def test_returns_offline_status(self, offline_client: CSTClient):
        result = offline_client.open_project("/tmp/existing.cst")
        assert result["status"] == "offline"

    def test_path_echoed_in_result(self, offline_client: CSTClient):
        result = offline_client.open_project("/tmp/existing.cst")
        assert result["path"] == "/tmp/existing.cst"

    def test_project_path_stored_on_client(self, offline_client: CSTClient):
        offline_client.open_project("/tmp/ref_project.cst")
        assert offline_client.project_path == "/tmp/ref_project.cst"

    def test_offline_contains_message(self, offline_client: CSTClient):
        result = offline_client.open_project("/tmp/existing.cst")
        assert "message" in result

    def test_has_project_remains_false(self, offline_client: CSTClient):
        """Offline open sets _project_path but _project stays None."""
        offline_client.open_project("/tmp/existing.cst")
        assert offline_client.has_project is False


# ---------------------------------------------------------------------------
# save_project — offline mode
# ---------------------------------------------------------------------------

class TestSaveProjectOffline:
    def test_returns_offline_status(self, offline_client: CSTClient):
        result = offline_client.save_project()
        assert result["status"] == "offline"

    def test_offline_contains_message(self, offline_client: CSTClient):
        result = offline_client.save_project()
        assert "message" in result

    def test_save_with_explicit_path_still_offline(self, offline_client: CSTClient):
        result = offline_client.save_project("/tmp/save_here.cst")
        assert result["status"] == "offline"


# ---------------------------------------------------------------------------
# close_project — offline mode
# ---------------------------------------------------------------------------

class TestCloseProjectOffline:
    def test_returns_closed_status(self, offline_client: CSTClient):
        result = offline_client.close_project()
        assert result["status"] == "closed"

    def test_clears_project_path(self, offline_client: CSTClient):
        offline_client.open_project("/tmp/some.cst")
        offline_client.close_project()
        assert offline_client.project_path is None

    def test_has_project_false_after_close(self, offline_client: CSTClient):
        offline_client.close_project()
        assert offline_client.has_project is False

    def test_close_message_in_result(self, offline_client: CSTClient):
        result = offline_client.close_project()
        assert "message" in result or result["status"] == "closed"


# ---------------------------------------------------------------------------
# connect() — offline mode (no CST library)
# ---------------------------------------------------------------------------

class TestConnectOffline:
    def test_connect_returns_offline_when_no_cst(self, offline_client: CSTClient):
        result = offline_client.connect()
        # On CI without CST installed the status must be offline
        assert result["status"] == "offline"

    def test_connect_has_message(self, offline_client: CSTClient):
        result = offline_client.connect()
        assert "message" in result


# ---------------------------------------------------------------------------
# disconnect()
# ---------------------------------------------------------------------------

class TestDisconnect:
    def test_disconnect_returns_disconnected_status(self, offline_client: CSTClient):
        result = offline_client.disconnect()
        assert result["status"] == "disconnected"


# ---------------------------------------------------------------------------
# execute_vba — connected mode (mocked)
# ---------------------------------------------------------------------------

class TestExecuteVbaConnected:
    def test_calls_add_to_history(self, mock_client: CSTClient):
        """Connected execute_vba should call model3d.add_to_history."""
        mock_client._project.model3d.add_to_history.return_value = None

        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            result = mock_client.execute_vba('Brick.Reset')
            assert result["status"] == "executed"
            mock_client._project.model3d.add_to_history.assert_called_once()

    def test_starts_and_stops_dialog_watcher(self, mock_client: CSTClient):
        """DialogWatcher should start before and stop after VBA execution."""
        mock_client._project.model3d.add_to_history.return_value = None

        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            mock_client.execute_vba('Brick.Reset')
            watcher_instance.start.assert_called_once()
            watcher_instance.stop.assert_called_once()

    def test_dialog_watcher_stops_on_exception(self, mock_client: CSTClient):
        """DialogWatcher must stop even if add_to_history raises."""
        mock_client._project.model3d.add_to_history.side_effect = RuntimeError("CST error")

        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            result = mock_client.execute_vba('Brick.Reset')
            assert result["status"] == "error"
            watcher_instance.stop.assert_called_once()

    def test_reports_dismissed_dialogs(self, mock_client: CSTClient):
        """If dialogs were dismissed, result should include count and log."""
        mock_client._project.model3d.add_to_history.return_value = None

        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = [
                {"title": "Results May Get Incompatible", "action": "clicked_ok"},
            ]
            MockWatcher.return_value = watcher_instance

            result = mock_client.execute_vba('Brick.Reset')
            assert result["status"] == "executed"
            assert result["dialogs_dismissed"] == 1
            assert len(result["dialog_log"]) == 1

    def test_custom_history_label(self, mock_client: CSTClient):
        """execute_vba should use custom history label if provided."""
        mock_client._project.model3d.add_to_history.return_value = None

        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            mock_client.execute_vba('Brick.Reset', history_label="Create Patch")
            call_args = mock_client._project.model3d.add_to_history.call_args
            assert call_args[0][0] == "Create Patch"


# ---------------------------------------------------------------------------
# execute_vba_silent — connected mode (mocked)
# ---------------------------------------------------------------------------

class TestExecuteVbaSilentConnected:
    def test_calls_schematic_execute(self, mock_client: CSTClient):
        """Connected execute_vba_silent should call schematic.execute_vba_code."""
        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            result = mock_client.execute_vba_silent("Sub Main()\nEnd Sub")
            assert result["status"] == "executed"
            mock_client._project.schematic.execute_vba_code.assert_called_once()

    def test_starts_and_stops_dialog_watcher(self, mock_client: CSTClient):
        """DialogWatcher should wrap schematic.execute_vba_code."""
        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            mock_client.execute_vba_silent("Sub Main()\nEnd Sub")
            watcher_instance.start.assert_called_once()
            watcher_instance.stop.assert_called_once()

    def test_dialog_watcher_stops_on_exception(self, mock_client: CSTClient):
        """DialogWatcher must stop even if execute_vba_code raises."""
        mock_client._project.schematic.execute_vba_code.side_effect = RuntimeError("err")

        with patch("mcp_cst_studio.cst_client.DialogWatcher") as MockWatcher:
            watcher_instance = MagicMock()
            watcher_instance.get_log.return_value = []
            MockWatcher.return_value = watcher_instance

            result = mock_client.execute_vba_silent("Sub Main()\nEnd Sub")
            assert result["status"] == "error"
            watcher_instance.stop.assert_called_once()
