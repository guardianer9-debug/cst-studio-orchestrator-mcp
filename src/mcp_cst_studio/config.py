"""Configuration and CST path auto-detection."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CSTConfig:
    cst_path: str | None = None
    work_dir: str = ""
    version: str = "2026"
    connected: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> CSTConfig:
        cst_path = os.environ.get("CST_PATH")
        work_dir = os.environ.get("CST_WORK_DIR", os.path.expanduser("~/cst_projects"))
        version = os.environ.get("CST_VERSION", "2026")

        if not cst_path:
            cst_path = _auto_detect_cst(version)

        connected = False
        if cst_path:
            try:
                import cst.interface  # noqa: F401
                connected = True
            except ImportError:
                pass

        log_level = os.environ.get("CST_LOG_LEVEL", "INFO")

        return cls(
            cst_path=cst_path,
            work_dir=work_dir,
            version=version,
            connected=connected,
            log_level=log_level,
        )


def _auto_detect_cst(version: str) -> str | None:
    """Try to find CST installation on Windows."""
    candidates = [
        rf"C:\Program Files (x86)\CST Studio Suite {version}",
        rf"C:\Program Files\CST Studio Suite {version}",
        rf"C:\CST Studio Suite {version}",
        os.path.expanduser(rf"~\CST Studio Suite {version}"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None
