"""Loopback viewer for immutable artifacts produced by the CST backend.

The stop button uses the same cancellation receipt as MCP. No second CST
connection or independent solver implementation lives here.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import re
from urllib.parse import unquote, urlsplit


class ArtifactHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root: Path, three: Path, token: str, **kwargs):
        self.root, self.three, self.token = root, three, token
        super().__init__(*args, directory=str(root), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        prefix = f"/{self.token}/"
        if not path.startswith(prefix):
            self.send_error(404)
            return
        path = path[len(prefix):]
        if path == "jobs.json":
            jobs = []
            for item in self.root.parent.glob("*/jobs/*/status.json"):
                if item.resolve().is_relative_to(self.root.parent):
                    data = json.loads(item.read_text(encoding="utf-8"))
                    data["cancel_path"] = f"cancel/{item.parents[2].name}/{item.parent.name}"
                    jobs.append(data)
            body = json.dumps(jobs, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "index.json":
            entries = []
            for item in sorted(self.root.glob("*/snapshot.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                if not item.resolve().is_relative_to(self.root):
                    continue
                try:
                    data = json.loads(item.read_text(encoding="utf-8"))
                    entries.append({"label": data["case_label"], "file": f"{item.parent.name}/snapshot.json"})
                except (OSError, ValueError, KeyError):
                    continue
            body = json.dumps(entries, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("", "index.html"):
            candidate = Path(__file__).parent / "web" / "index.html"
        elif path.startswith("lib/"):
            candidate = (self.three / path[4:]).resolve()
            if not candidate.is_relative_to(self.three):
                self.send_error(403)
                return
        else:
            candidate = (self.root / path).resolve()
            if not candidate.is_relative_to(self.root):
                self.send_error(403)
                return
        if not candidate.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(str(candidate)))
        self.send_header("Content-Length", str(candidate.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        with candidate.open("rb") as f:
            import shutil
            shutil.copyfileobj(f, self.wfile)

    def do_POST(self):
        # Capability URL + same-origin browser policy; never accept a filesystem path.
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.send_error(403)
            return
        origin = self.headers.get("Origin")
        expected = f"http://127.0.0.1:{self.server.server_port}"
        if origin and origin != expected:
            self.send_error(403)
            return
        path = unquote(urlsplit(self.path).path)
        match = re.fullmatch(r"/" + re.escape(self.token) + r"/cancel/([A-Za-z0-9_-]+)/([a-f0-9]{32})", path)
        if not match:
            self.send_error(404)
            return
        job = (self.root.parent / match[1] / "jobs" / match[2]).resolve()
        if not job.is_relative_to(self.root.parent) or not (job / "status.json").is_file():
            self.send_error(404)
            return
        from mcp_cst_studio.task_runner import request_cancellation
        body = json.dumps(request_cancellation(job)).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # The local capability token must not be echoed into routine access logs.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--three", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    root, three = args.root.resolve(), args.three.resolve(strict=True)
    root.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    previous = root / "viewer-local.json"
    if previous.exists():
        saved = urlsplit(json.loads(previous.read_text(encoding="utf-8"))["url"])
        if saved.hostname == "127.0.0.1" and saved.port == args.port and re.fullmatch(r"/[A-Za-z0-9_-]{32}/", saved.path):
            token = saved.path.strip("/")
    handler = partial(ArtifactHandler, root=root, three=three, token=token)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{server.server_port}/{token}/"
    (root / "viewer-local.json").write_text(json.dumps({"url": url}), encoding="utf-8")
    print("Read-only viewer ready; URL saved to viewer-local.json", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
