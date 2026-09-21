"""Session-local native bundles and a readable index; no CST import or solver calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        value = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
        return value.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def within(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Path escapes the session workspace")
    return resolved


def bind(project: Path, session_id: str, created_at: float | None = None) -> Path:
    """The stable ID, never a chat title or runtime ID, owns the directory."""
    if not session_id or len(session_id) > 4096:
        raise ValueError("A stable session ID is required")
    key = hashlib.sha256(session_id.encode()).hexdigest()[:24]
    index = project.resolve() / ".cst-sessions" / (key + ".json")
    if index.exists():
        return await_binding(index, project, session_id)
    # Exclusive creation makes simultaneous Pi/UI startup choose one association.
    index.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.fromtimestamp(created_at or time.time(), timezone.utc).strftime("%Y-%m-%d")
    root = project.resolve() / "sessions" / f"{date}_{key}"
    payload = {"session_id": session_id, "directory": str(root), "bound_at": time.time()}
    try:
        with index.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
    except FileExistsError:
        return await_binding(index, project, session_id)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("工程", "导出结果", "过程记录"):
        (root / name).mkdir(exist_ok=True)
    info = root / "会话信息.json"
    if not info.exists():
        write_json(info, {"schema": 1, **payload, "project_directory": str(project.resolve()),
                          "title": "CST会话", "projects": [], "links": [],
                          "recommended_project": None, "simulation_policy": "paused",
                          "human_acceptance": "pending", "model_usage": None})
        render_entry(root)
    return root


def await_binding(index: Path, project: Path, session_id: str) -> Path:
    """Pi and the desktop may bind concurrently; return only initialized metadata."""
    for _ in range(100):
        try:
            binding = read_json(index)
            if binding["session_id"] != session_id:
                raise ValueError("Session identity mismatch")
            root = within(project / "sessions", Path(binding["directory"]))
            read_json(root / "会话信息.json")
            return root
        except (json.JSONDecodeError, FileNotFoundError):
            time.sleep(.02)
    raise RuntimeError("Incomplete session binding; retain the receipt for recovery")


def render_entry(root: Path) -> None:
    info = read_json(root / "会话信息.json")
    def link(label, path):
        return f"[{label}](<{Path(path).as_posix()}>)"
    lines = [f"# {info.get('title', 'CST会话')}", "", f"会话ID：`{info['session_id']}`", "",
             "本轮自动求解暂停。建模/修改 → 实际读回 → 保存完整工程 → 人工检查/运行。", "",
             "## 当前建议打开", ""]
    recommended = info.get("recommended_project")
    lines.append(link("原生CST工程", recommended) if recommended else "尚无推荐工程；未生成运行结果。")
    lines += ["", "## 模型版本与已有结果", ""]
    for item in info.get("projects", []):
        lines.append(f"- {link(item['label'], item['path'])} · {link('文件夹', Path(item['path']).parent)} — "
                     f"{item.get('status', '待核对')}；结果来源：{item.get('result_origin', 'unknown')}；"
                     f"{item.get('result_note', '没有已验证的新结果')}。")
    lines += ["", "## 过程与尚未归集资料", ""]
    for item in info.get("links", []):
        lines.append(f"- {link(item['label'], item['path'])} — {item.get('status', '原位置保留')}")
    lines += ["", "人工验收：待用户确认。流程通过和数值通过分别记录。", ""]
    (root / "阅读入口.md").write_text("\n".join(lines), encoding="utf-8")


def bundle_files(source: Path) -> list[Path]:
    source = source.resolve(strict=True)
    if source.suffix.lower() != ".cst":
        raise ValueError("A native .cst project is required")
    sidecar = source.with_suffix("")
    files = [source] + (sorted(p for p in sidecar.rglob("*") if p.is_file()) if sidecar.is_dir() else [])
    if any(p.is_symlink() or not p.resolve().is_relative_to(source.parent) for p in files):
        raise ValueError("External links in native bundle require explicit dependency review")
    return files


def copy_bundle(source: Path, destination: Path) -> dict:
    """Preserve basename/sidecar relationships, verify every byte, never overwrite."""
    source = source.resolve(strict=True)
    files = bundle_files(source)
    required = sum(p.stat().st_size for p in files)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < required + 128 * 1024**2:
        raise OSError("Insufficient free space for full native bundle plus reserve")
    if destination.exists():
        raise FileExistsError(destination)
    # Windows exclusive open detects CST-held files. No lock deletion or forced unlock.
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        for path in files:
            handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
            if handle == wintypes.HANDLE(-1).value:
                raise OSError(ctypes.get_last_error(), f"Bundle file occupied/unreadable: {path}")
            kernel.CloseHandle(handle)
    destination.mkdir(exist_ok=False)
    receipt = {"source": str(source), "destination": str(destination), "created_at": time.time(),
               "state": "copying", "files": [], "external_dependencies": "not_inferred",
               "source_untouched": True}
    try:
        sidecar = source.with_suffix("")
        if sidecar.is_dir():
            for directory in [sidecar, *(p for p in sidecar.rglob("*") if p.is_dir())]:
                within(source.parent, directory)
                (destination / directory.relative_to(source.parent)).mkdir(parents=True, exist_ok=True)
        for path in files:
            before = (path.stat().st_size, path.stat().st_mtime_ns)
            source_hash = digest(path)
            target = destination / path.relative_to(source.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if before != (path.stat().st_size, path.stat().st_mtime_ns) or digest(path) != source_hash or digest(target) != source_hash:
                raise RuntimeError(f"Source changed during copy or hash mismatch: {path}")
            receipt["files"].append({"old": str(path), "new": str(target), "sha256": source_hash, "bytes": before[0]})
        if any(digest(Path(item["old"])) != item["sha256"] for item in receipt["files"]):
            raise RuntimeError("Source bundle changed before copy verification completed")
        receipt["state"] = "verified_copy"
    except Exception as exc:
        receipt.update(state="failed_partial_copy", error=str(exc))
        raise
    finally:
        write_json(destination / "bundle-copy.json", receipt)
    return receipt


def inventory(root: Path) -> dict:
    """Read disk provenance only. A changed model invalidates old snapshot currency."""
    info = read_json(root / "会话信息.json")
    result = {**info, "directory": str(root), "entry": str(root / "阅读入口.md"), "projects": []}
    known = {str(Path(p["path"]).resolve()).casefold(): p for p in info.get("projects", [])}
    # Only CST files under model/run nodes; evidence copies are not selectable projects.
    candidates = [p for name in ("工程", "运行") for p in (root / name).rglob("*.cst")]
    for path in candidates:
        path = within(root, path)
        item = dict(known.get(str(path).casefold(), {"path": str(path), "label": path.stem,
                    "status": "待实际读回", "result_origin": "unknown"}))
        item["sha256"] = digest(path)
        item["native_directory"] = str(path.with_suffix(""))
        item["native_directory_exists"] = path.with_suffix("").is_dir()
        item["snapshot_current"] = item.get("snapshot_project_sha256") == item["sha256"]
        if item.get("snapshot_results_fingerprint"):
            item["snapshot_current"] &= item["snapshot_results_fingerprint"] == results_fingerprint(path)
        item["result_binding"] = item.get("result_binding", "unknown")
        result["projects"].append(item)
    return result


def results_fingerprint(project: Path) -> str:
    """Detect external result changes cheaply; this is not numerical validation."""
    folder = project.with_suffix("") / "Result"
    value = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        stat = path.stat()
        value.update(f"{path.relative_to(folder)}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["bind", "inventory"])
    parser.add_argument("--project", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--created", type=float)
    args = parser.parse_args()
    root = bind(Path(args.project), args.session, args.created)
    print(json.dumps(inventory(root) if args.action == "inventory" else {"directory": str(root)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
