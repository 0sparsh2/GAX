from __future__ import annotations

import json
import os
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import click

from gax.executor import invoke
from gax.paths import DEFAULT_HOST, DEFAULT_PORT, PID_PATH, ensure_gax_home
from gax.registry import Registry

_REGISTRY = Registry()


class GaxdHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return  # quiet by default

    def _json_response(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode() or "{}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/health":
            self._json_response(200, {"ok": True, "service": "gaxd", "commands": len(_REGISTRY.list_commands())})
            return

        if path == "/commands":
            items = [
                {"command": m.command, "version": m.version, "description": m.description}
                for m in _REGISTRY.list_commands()
            ]
            self._json_response(200, {"commands": items})
            return

        if path.startswith("/commands/") and path.endswith("/doc"):
            cmd = path.split("/")[2]
            doc = _REGISTRY.doc_stub(cmd)
            if not doc:
                self._json_response(404, {"error": "not_found"})
                return
            self._json_response(200, doc)
            return

        if path == "/search":
            q = (qs.get("q") or [""])[0]
            hits = _REGISTRY.search(q)
            self._json_response(
                200,
                {
                    "query": q,
                    "results": [
                        {"command": m.command, "description": m.description, "category": m.category}
                        for m in hits
                    ],
                },
            )
            return

        if path.startswith("/schema/"):
            cmd = path.split("/schema/", 1)[1]
            m = _REGISTRY.get(cmd)
            if not m:
                self._json_response(404, {"error": "not_found"})
                return
            self._json_response(
                200,
                {"command": cmd, "input_schema": m.input_schema, "output_schema": m.output_schema},
            )
            return

        self._json_response(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/invoke":
            self._json_response(404, {"error": "not_found"})
            return
        body = self._read_json()
        cap = self.headers.get("GAX-Capability") or body.get("capability")
        env, exit_code = invoke(
            _REGISTRY,
            command=str(body.get("command", "")),
            args=dict(body.get("args") or {}),
            surface=str(body.get("surface") or "model"),
            capability=cap,
        )
        http_code = 200 if env.get("ok") else 400
        self._json_response(http_code, {"envelope": env, "exit_code": exit_code})


def run_server(host: str, port: int) -> None:
    server = HTTPServer((host, port), GaxdHandler)
    click.echo(f"gaxd listening on http://{host}:{port}")
    server.serve_forever()


@click.group()
def main() -> None:
    """GAX daemon (gaxd)."""


@main.command("start")
@click.option("--host", default=DEFAULT_HOST)
@click.option("--port", default=DEFAULT_PORT, type=int)
@click.option("--background", is_flag=True, help="Daemonize (write pid file)")
def start(host: str, port: int, background: bool) -> None:
    ensure_gax_home()
    if background:
        pid = os.fork()
        if pid > 0:
            PID_PATH.write_text(str(pid))
            click.echo(f"gaxd started pid={pid} http://{host}:{port}")
            return
        os.setsid()
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    else:
        PID_PATH.write_text(str(os.getpid()))
    run_server(host, port)


@main.command("stop")
def stop() -> None:
    if not PID_PATH.exists():
        click.echo("gaxd not running (no pid file)")
        return
    pid = int(PID_PATH.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        PID_PATH.unlink(missing_ok=True)
        click.echo(f"stopped gaxd pid={pid}")
    except ProcessLookupError:
        PID_PATH.unlink(missing_ok=True)
        click.echo("stale pid file removed")


@main.command("status")
@click.option("--host", default=DEFAULT_HOST)
@click.option("--port", default=DEFAULT_PORT, type=int)
def status(host: str, port: int) -> None:
    import httpx

    try:
        r = httpx.get(f"http://{host}:{port}/health", timeout=2.0)
        click.echo(r.text)
    except Exception as e:
        click.echo(f"gaxd unreachable: {e}")


if __name__ == "__main__":
    main()
