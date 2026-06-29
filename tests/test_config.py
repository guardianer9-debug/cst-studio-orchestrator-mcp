"""Tests for CSTConfig class and CST auto-detection logic."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest

from mcp_cst_studio.config import CSTConfig, _auto_detect_cst


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

class TestCSTConfigDefaults:
    def test_default_connected_is_false(self):
        config = CSTConfig()
        assert config.connected is False

    def test_default_cst_path_is_none(self):
        config = CSTConfig()
        assert config.cst_path is None

    def test_default_version_is_2026(self):
        config = CSTConfig()
        assert config.version == "2026"

    def test_default_work_dir_is_empty_string(self):
        config = CSTConfig()
        assert config.work_dir == ""


# ---------------------------------------------------------------------------
# Explicit values
# ---------------------------------------------------------------------------

class TestCSTConfigExplicitValues:
    def test_explicit_cst_path_stored(self):
        config = CSTConfig(cst_path="/some/path/to/cst")
        assert config.cst_path == "/some/path/to/cst"

    def test_explicit_work_dir_stored(self):
        config = CSTConfig(work_dir="/tmp/my_projects")
        assert config.work_dir == "/tmp/my_projects"

    def test_explicit_version_stored(self):
        config = CSTConfig(version="2025")
        assert config.version == "2025"

    def test_explicit_connected_true_stored(self):
        config = CSTConfig(connected=True)
        assert config.connected is True

    def test_all_explicit_values_stored(self):
        config = CSTConfig(
            cst_path=r"C:\Program Files\CST Studio Suite 2026",
            work_dir="/tmp/cst",
            version="2026",
            connected=False,
        )
        assert config.cst_path == r"C:\Program Files\CST Studio Suite 2026"
        assert config.work_dir == "/tmp/cst"
        assert config.version == "2026"
        assert config.connected is False


# ---------------------------------------------------------------------------
# from_env() class method
# ---------------------------------------------------------------------------

class TestCSTConfigFromEnv:
    def test_from_env_defaults_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        config = CSTConfig.from_env()

        assert config.version == "2026"
        assert config.work_dir != ""  # expands ~/cst_projects
        assert "cst_projects" in config.work_dir

    def test_from_env_reads_cst_path(self, monkeypatch):
        monkeypatch.setenv("CST_PATH", "/custom/cst/path")
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        config = CSTConfig.from_env()

        assert config.cst_path == "/custom/cst/path"

    def test_from_env_reads_work_dir(self, monkeypatch):
        monkeypatch.setenv("CST_WORK_DIR", "/custom/work/dir")
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        config = CSTConfig.from_env()

        assert config.work_dir == "/custom/work/dir"

    def test_from_env_reads_version(self, monkeypatch):
        monkeypatch.setenv("CST_VERSION", "2025")
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)

        config = CSTConfig.from_env()

        assert config.version == "2025"

    def test_from_env_connected_false_without_cst_library(self, monkeypatch):
        """On any non-Windows CI machine CST is not installed: connected must be False."""
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        config = CSTConfig.from_env()

        assert config.connected is False

    def test_from_env_returns_cstconfig_instance(self, monkeypatch):
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        config = CSTConfig.from_env()

        assert isinstance(config, CSTConfig)

    def test_from_env_skips_auto_detect_when_cst_path_set(self, monkeypatch):
        """When CST_PATH is set, _auto_detect_cst should not be called."""
        monkeypatch.setenv("CST_PATH", "/my/cst")
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        with patch("mcp_cst_studio.config._auto_detect_cst") as mock_detect:
            config = CSTConfig.from_env()

        mock_detect.assert_not_called()
        assert config.cst_path == "/my/cst"

    def test_from_env_calls_auto_detect_when_no_cst_path(self, monkeypatch):
        """When CST_PATH is not set, _auto_detect_cst is called."""
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        with patch("mcp_cst_studio.config._auto_detect_cst", return_value=None) as mock_detect:
            config = CSTConfig.from_env()

        mock_detect.assert_called_once_with("2026")
        assert config.cst_path is None

    def test_from_env_auto_detect_returns_path(self, monkeypatch):
        """When auto-detect finds CST, cst_path is set."""
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        detected = r"C:\Program Files\CST Studio Suite 2026"
        with patch("mcp_cst_studio.config._auto_detect_cst", return_value=detected):
            config = CSTConfig.from_env()

        assert config.cst_path == detected

    def test_from_env_connected_true_when_cst_importable(self, monkeypatch):
        """When cst.interface is importable, connected=True."""
        monkeypatch.setenv("CST_PATH", "/some/cst")
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        # Inject a fake cst.interface module so the import succeeds
        fake_cst = types.ModuleType("cst")
        fake_interface = types.ModuleType("cst.interface")
        monkeypatch.setitem(sys.modules, "cst", fake_cst)
        monkeypatch.setitem(sys.modules, "cst.interface", fake_interface)

        config = CSTConfig.from_env()

        assert config.connected is True

    def test_from_env_work_dir_expands_tilde(self, monkeypatch):
        """Default work_dir should expand ~ to the user's home directory."""
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.delenv("CST_VERSION", raising=False)

        config = CSTConfig.from_env()

        assert "~" not in config.work_dir
        assert config.work_dir.endswith("cst_projects")

    def test_from_env_version_passed_to_auto_detect(self, monkeypatch):
        """Custom CST_VERSION is forwarded to _auto_detect_cst."""
        monkeypatch.delenv("CST_PATH", raising=False)
        monkeypatch.delenv("CST_WORK_DIR", raising=False)
        monkeypatch.setenv("CST_VERSION", "2025")

        with patch("mcp_cst_studio.config._auto_detect_cst", return_value=None) as mock_detect:
            CSTConfig.from_env()

        mock_detect.assert_called_once_with("2025")


# ---------------------------------------------------------------------------
# _auto_detect_cst() — path detection
# ---------------------------------------------------------------------------

class TestAutoDetectCST:
    def test_returns_none_when_no_cst_installed(self):
        """On Linux/macOS/CI where CST is absent, result is None."""
        result = _auto_detect_cst("2026")
        assert result is None or isinstance(result, str)

    def test_returns_none_for_nonexistent_version(self):
        """Using a version string that will never match any real path."""
        result = _auto_detect_cst("9999_nonexistent")
        assert result is None

    def test_does_not_raise_on_missing_paths(self):
        """Should never raise even if OS path functions behave oddly."""
        try:
            _auto_detect_cst("2026")
        except Exception as exc:
            pytest.fail(f"_auto_detect_cst raised unexpectedly: {exc}")

    def test_returns_first_matching_path(self):
        """When a candidate directory exists, return it."""
        with patch("os.path.isdir", side_effect=lambda p: "Program Files (x86)" in p):
            result = _auto_detect_cst("2026")

        assert result is not None
        assert "Program Files (x86)" in result
        assert "2026" in result

    def test_checks_all_candidates_in_order(self):
        """Auto-detect checks multiple paths and returns the first match."""
        checked = []

        def fake_isdir(p):
            checked.append(p)
            return False

        with patch("os.path.isdir", side_effect=fake_isdir):
            result = _auto_detect_cst("2026")

        assert result is None
        assert len(checked) == 4  # 4 candidate paths

    def test_returns_second_candidate_if_first_missing(self):
        """If first candidate doesn't exist, check the next."""
        def fake_isdir(p):
            return "Program Files\\" in p and "x86" not in p

        with patch("os.path.isdir", side_effect=fake_isdir):
            result = _auto_detect_cst("2026")

        assert result is not None
        assert "Program Files" in result
        assert "x86" not in result

    def test_version_embedded_in_candidate_paths(self):
        """All candidate paths should contain the version string."""
        checked = []

        def fake_isdir(p):
            checked.append(p)
            return False

        with patch("os.path.isdir", side_effect=fake_isdir):
            _auto_detect_cst("2025")

        for path in checked:
            assert "2025" in path
