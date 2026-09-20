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
    connection_mode: str = "new"
    pid: int | None = None
    hidden: bool = True

    @classmethod
    def from_env(cls) -> CSTConfig:
        cst_path = os.environ.get("CST_PATH")
        work_dir = os.environ.get("CST_WORK_DIR", os.path.expanduser("~/cst_projects"))
        version = os.environ.get("CST_VERSION", "2026")

        if not cst_path:
            cst_path = _auto_detect_cst(version)

        log_level = os.environ.get("CST_LOG_LEVEL", "INFO")

        return cls(
            cst_path=cst_path,
            work_dir=work_dir,
            version=version,
            connected=False,
            log_level=log_level,
            connection_mode=os.environ.get("CST_CONNECTION_MODE", "new"),
            pid=int(os.environ["CST_PID"]) if os.environ.get("CST_PID") else None,
            hidden=os.environ.get("CST_HIDDEN", "1") == "1",
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
