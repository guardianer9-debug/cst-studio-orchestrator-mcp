"""Optional append-only local MCP call evidence. Never stored in the public checkout."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def record(event: dict) -> None:
    directory = os.environ.get("CST_EVIDENCE_DIR")
    if not directory:
        return
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": time.time(), **event}
    path = root / f"{time.time_ns()}-{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def implementation_identity() -> dict:
    root = Path(__file__).parent
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*.py"))}
