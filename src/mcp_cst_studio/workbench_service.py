"""One session-owned CST backend shared by MCP and the desktop. Loopback only."""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

from mcp_cst_studio.session_workspace import bind, inventory, read_json, write_json


def ensure(project: Path, session_id: str, created_at=None) -> dict:
    """Start/reuse a metadata-ready service; never start CST or a provider here."""
    root = bind(project, session_id, created_at)
    receipt = root / ".backend.json"
    if receipt.exists():
        old = read_json(receipt)
        try:
            request = urllib.request.Request(old["url"] + "/health", headers={"Authorization": "Bearer " + old["token"]})
            with urllib.request.urlopen(request, timeout=2) as response:
                if json.load(response).get("session_id") == session_id:
                    return old
        except (OSError, ValueError):
            # A synchronous CST call can temporarily block health responses.
            # Never create a second owner just because the first is busy.
            import psutil
            try:
                process = psutil.Process(old["pid"])
                command = process.cmdline()
                if ("mcp_cst_studio.workbench_service" in command and session_id in command
                        and abs(process.create_time() - old["started_at"]) < 10):
                    return old
            except (psutil.Error, KeyError):
                pass
    lock = root / ".backend-start.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("Backend startup already in progress; retry after it finishes")
    try:
        os.close(fd)
        config = read_json(project / ".cst-workspace.json")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        token = secrets.token_urlsafe(32)
        env = {**os.environ, "PYTHONUTF8": "1", "CST_SESSION_DIR": str(root), "CST_WORK_DIR": str(root),
               "CST_SESSION_ID": session_id, "CST_SIMULATION_PAUSED": "1", "CST_CONNECTION_MODE": "new",
               "CST_EVIDENCE_DIR": str(root / "过程记录" / "mcp"), "CST_PATH": config["cst_path"],
               "CST_VERSION": config.get("cst_version", "2025"), "CST_BACKEND_TOKEN": token,
               "PYTHONPATH": os.pathsep.join([config["source"], config["cst_python"]])}
        log_path = root / "过程记录" / f"backend-{time.time_ns()}.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen([sys.executable, "-m", "mcp_cst_studio.workbench_service", "serve", "--project", str(project),
                                        "--session", session_id, "--port", str(port)], env=env,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        value = {"url": f"http://127.0.0.1:{port}", "token": token, "pid": process.pid,
                 "session_id": session_id, "directory": str(root), "started_at": time.time()}
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError(f"Backend exited; see {log_path}")
            try:
                req = urllib.request.Request(value["url"] + "/health", headers={"Authorization": "Bearer " + token})
                with urllib.request.urlopen(req, timeout=.5):
                    write_json(receipt, value)
                    return value
            except OSError:
                time.sleep(.1)
        raise RuntimeError(f"Backend startup timed out; inspect PID {process.pid} and {log_path}")
    finally:
        lock.unlink(missing_ok=True)


def create_app(root: Path, session_id: str, token: str, stop=None):
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, Mount
    from mcp_cst_studio.server import create_server
    from mcp_cst_studio.tools import _registry
    from mcp_cst_studio.evidence import implementation_identity, record
    server, client = create_server()
    info = read_json(root / "会话信息.json")
    info["active_project"] = None
    write_json(root / "会话信息.json", info)
    manager = StreamableHTTPSessionManager(server, json_response=True, stateless=True)
    record({"event": "shared_backend_start", "session_id": session_id,
            "implementation_sha256": implementation_identity(), "simulation_policy": "paused"})

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield
        client.disconnect()

    async def health(request):
        return JSONResponse({"session_id": session_id, "cst_connected": client.connected,
                             "project": client.project_path, "simulation_policy": "paused"})

    async def action(request):
        payload = await request.json()
        tool = payload.get("tool")
        args = payload.get("arguments", {})
        allowed = {"cst_open_project", "cst_reload_project", "cst_close_project", "cst_save_project", "cst_readback",
                   "cst_refresh_view", "cst_refresh_results", "cst_set_parameter", "cst_edit_case", "cst_connection_status",
                   "cst_get_simulation_status", "cst_stop_simulation", "cst_project_tree", "cst_read_curve"}
        if tool not in allowed or not isinstance(args, dict):
            return JSONResponse({"error": "Unsupported desktop action"}, status_code=400)
        record({"event": "manual_workbench_request", "tool": tool, "arguments": args,
                "expected_project": payload.get("project"), "session_id": session_id})
        if tool not in ("cst_open_project", "cst_reload_project", "cst_connection_status"):
            if payload.get("project") != client.project_path:
                return JSONResponse({"error": "Selected project differs from the backend's actual open project"}, status_code=409)
        try:
            result = await _registry.invoke(tool, args)
            return JSONResponse({**result.model_dump(mode="json"), "active_project": client.project_path})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    async def shutdown(request):
        if getattr(client, "_unsaved_backend_edits", False):
            return JSONResponse({"error": "Unsaved backend edits"}, status_code=409)
        if client.has_project and client.solver_status().get("running") is not False:
            return JSONResponse({"error": "Running/unknown solver; backend retained"}, status_code=409)
        result = client.disconnect()
        if result.get("status") != "disconnected":
            return JSONResponse(result, status_code=409)
        info = read_json(root / "会话信息.json")
        info["active_project"] = None
        write_json(root / "会话信息.json", info)
        record({"event": "shared_backend_shutdown", "session_id": session_id})
        from starlette.background import BackgroundTask
        return JSONResponse(result, background=BackgroundTask(stop) if stop else None)

    async def mcp_app(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    app = Starlette(routes=[Route("/health", health), Route("/action", action, methods=["POST"]),
                            Route("/shutdown", shutdown, methods=["POST"]),
                            Mount("/mcp", app=mcp_app)], lifespan=lifespan)

    class AuthenticatedLocalApp:
        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope.get("headers", []))
                origin = headers.get(b"origin")
                # Desktop/Pi use non-browser HTTP. Do not enable browser CORS.
                if origin or not secrets.compare_digest(headers.get(b"authorization", b""), ("Bearer " + token).encode()):
                    await JSONResponse({"error": "Unauthorized"}, status_code=403)(scope, receive, send)
                    return
            await app(scope, receive, send)
    return AuthenticatedLocalApp()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["ensure", "serve"])
    parser.add_argument("--project", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--created", type=float)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    project = Path(args.project)
    if args.action == "ensure":
        print(json.dumps(ensure(project, args.session, args.created), ensure_ascii=False))
    else:
        import uvicorn
        root = Path(os.environ["CST_SESSION_DIR"])
        holder = {}
        def stop():
            holder["server"].should_exit = True
        config = uvicorn.Config(create_app(root, args.session, os.environ["CST_BACKEND_TOKEN"], stop),
                                host="127.0.0.1", port=args.port, access_log=False)
        holder["server"] = uvicorn.Server(config)
        holder["server"].run()


if __name__ == "__main__":
    main()
