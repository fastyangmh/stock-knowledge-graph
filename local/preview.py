"""Read-only localhost preview of one validated private export.

Loads an allowlisted, size-bounded in-memory snapshot. Never serves a directory,
SQLite, raw inputs, credentials or arbitrary repo files; no Git operations.
Restart after regenerating JSON. Other local users can access this port.
"""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from .core import ROOT
from .safety import exclusive_lock, private_path
from .validate_release import validate_data_dir

MAX_BYTES = 64 * 1024 * 1024
ASSETS = {"index.html":"text/html; charset=utf-8", "css/style.css":"text/css; charset=utf-8",
          "js/app.js":"text/javascript; charset=utf-8", "js/graph-utils.js":"text/javascript; charset=utf-8"}


def snapshot(directory, *, root=ROOT, max_bytes=MAX_BYTES):
    directory = private_path(directory)
    root = Path(root).resolve()
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("Preview size budget must be a positive integer")
    remaining = max_bytes
    files = {}
    def read(path):
        nonlocal remaining
        path = Path(path)
        if path.is_symlink() or path.stat().st_size > remaining:
            raise ValueError("Preview file is a symlink or exceeds size budget")
        body = path.read_bytes()
        remaining -= len(body)
        if remaining < 0:
            raise ValueError("Preview exceeds size budget")
        return body
    with exclusive_lock(directory):
        # Fail before JSON parsing can allocate an oversized snapshot. The lock
        # coordinates our own exporters; it is not a hostile-filesystem sandbox.
        total = 0
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError("Symlink in preview")
            if path.is_file() and path.suffix == ".json":
                total += path.stat().st_size
                if total > max_bytes:
                    raise ValueError("Preview exceeds size budget")
        validate_data_dir(directory)
        manifest_bytes = read(directory / "manifest.json")
        manifest = json.loads(manifest_bytes)
        files["/data/manifest.json"] = (manifest_bytes, "application/json; charset=utf-8")
        for item in manifest["stocks"]:
            relative = item["path"].removeprefix("data/")
            path = directory / relative
            if not path.resolve().is_relative_to(directory):
                raise ValueError("Preview graph outside export")
            files["/" + item["path"]] = (read(path), "application/json; charset=utf-8")
    for name, mime in ASSETS.items():
        path = root / name
        if not path.resolve().is_relative_to(root):
            raise ValueError("Preview asset outside site root")
        files["/" + name] = (read(path), mime)
    files["/"] = files["/index.html"]
    return files


def make_server(directory, *, port=8765, root=ROOT):
    files = snapshot(directory, root=root)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not expose private paths or parameters in logs.
        def do_HEAD(self):
            self.serve(head=True)
        def do_GET(self):
            self.serve()
        def serve(self, head=False):
            allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed_hosts:
                self.send_error(403, "Host not allowed")
                return
            parsed = urlsplit(self.path)
            if parsed.scheme or parsed.netloc:
                self.send_error(400, "Origin-form path required")
                return
            path = unquote(parsed.path)
            entry = files.get(path)
            if entry is None:
                self.send_error(404, "Not found")
                return
            body, mime = entry
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            if not head:
                self.wfile.write(body)
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "local/private/preview")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be 1..65535")
    with make_server(args.data_dir, port=args.port) as server:
        print(f"Private preview: http://127.0.0.1:{server.server_port}/", flush=True)
        print("Read-only snapshot; no publish. Restart after exporting new data. Ctrl-C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
