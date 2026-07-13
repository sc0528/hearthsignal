#!/usr/bin/env python3
"""Run Hearthsignal as a self-contained scheduled web service."""

from __future__ import annotations

import html
import json
import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
RUNTIME = ROOT / "runtime"
STATUS_PATH = RUNTIME / "container-status.json"
CONFIG_PATH = RUNTIME / "container-config.json"
DEFAULT_INTERVAL = 86400
MINIMUM_INTERVAL = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def setting(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def interval_seconds(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("HEARTHSIGNAL_INTERVAL must be a whole number of seconds") from exc
    if value < MINIMUM_INTERVAL:
        raise ValueError(f"HEARTHSIGNAL_INTERVAL must be at least {MINIMUM_INTERVAL} seconds")
    return value


def write_status(**updates: object) -> dict[str, object]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    current: dict[str, object] = {}
    if STATUS_PATH.exists():
        try:
            current = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
    current.update(updates)
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, indent=2), encoding="utf-8")
    temporary.replace(STATUS_PATH)
    return current


def built_in_docker_config() -> dict[str, object]:
    config = json.loads((ROOT / "config.live.example.json").read_text(encoding="utf-8"))
    config["checks"]["docker"]["enabled"] = True
    config["checks"]["disks"] = []
    config["checks"]["backups"] = []
    config["checks"]["http"] = []
    config["outputs"] = {
        "markdown": "reports/latest-digest.md",
        "html": "reports/latest-digest.html",
    }
    return config


def prepare_live_config(mode: str) -> Path:
    external = setting("HEARTHSIGNAL_CONFIG", "/config/hearthsignal.json")
    if mode == "docker" and not Path(external).is_file():
        config = built_in_docker_config()
    else:
        source = Path(external)
        if not source.is_file():
            raise ValueError(
                f"live mode requires a config at {source}; mount it or use HEARTHSIGNAL_MODE=docker"
            )
        config = json.loads(source.read_text(encoding="utf-8"))
        config["outputs"] = {
            "markdown": "reports/latest-digest.md",
            "html": "reports/latest-digest.html",
        }
    RUNTIME.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return CONFIG_PATH


def command_for(mode: str) -> list[str]:
    if mode == "demo":
        return [sys.executable, str(ROOT / "scripts" / "generate_digest.py"), "--dry-run"]
    if mode in {"docker", "live"}:
        config = prepare_live_config(mode)
        return [
            sys.executable,
            str(ROOT / "scripts" / "collect_health.py"),
            "--config",
            str(config.relative_to(ROOT)),
            "--live",
        ]
    raise ValueError("HEARTHSIGNAL_MODE must be demo, docker, or live")


def error_page(message: str) -> None:
    report = REPORTS / "latest-digest.html"
    if report.exists():
        return
    safe = html.escape(message)
    report.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Hearthsignal setup</title><style>"
        "body{margin:0;background:#edf1f5;color:#0b1d33;font:16px/1.6 system-ui}"
        "main{max-width:720px;margin:8vh auto;background:white;padding:48px;border-radius:16px;"
        "box-shadow:0 18px 55px #182b4d1a}h1{font-size:2.6rem;margin:0}.brand{color:#ff6b57}"
        "code{display:block;padding:16px;background:#f5f7fa;border-radius:8px;overflow-wrap:anywhere}"
        "</style><main><h1>Hearthsignal<span class='brand'>.</span></h1>"
        "<p>Hearthsignal is running, but the first briefing could not be generated.</p>"
        f"<code>{safe}</code><p>Correct the configuration, then restart the container. "
        "The last successful report is always preserved.</p></main></html>",
        encoding="utf-8",
    )


def generate(mode: str, interval: int) -> bool:
    started = utc_now()
    write_status(state="running", mode=mode, last_run_started=started, error=None)
    try:
        result = subprocess.run(command_for(mode), cwd=ROOT, capture_output=True, text=True, timeout=120)
        if result.returncode:
            message = (result.stderr or result.stdout or "report generation failed").strip()
            raise RuntimeError(message)
        next_run = datetime.now(timezone.utc) + timedelta(seconds=interval)
        write_status(
            state="ready",
            mode=mode,
            last_run_started=started,
            last_success=utc_now(),
            next_run=next_run.isoformat(timespec="seconds"),
            error=None,
        )
        print(result.stdout.strip(), flush=True)
        return True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        message = str(exc)
        write_status(state="degraded", mode=mode, last_run_started=started, error=message)
        REPORTS.mkdir(parents=True, exist_ok=True)
        error_page(message)
        print(f"Hearthsignal run failed: {message}", file=sys.stderr, flush=True)
        return False


def scheduler(mode: str, interval: int, stop: threading.Event) -> None:
    while not stop.wait(interval):
        generate(mode, interval)


class HearthsignalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(REPORTS), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/latest-digest.html")
            self.end_headers()
            return
        if self.path in {"/healthz", "/api/status"}:
            payload = {"service": "hearthsignal", "status": "starting"}
            if STATUS_PATH.exists():
                try:
                    payload.update(json.loads(STATUS_PATH.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    payload["status"] = "degraded"
            body = json.dumps(payload).encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"web: {format % args}", flush=True)


def main() -> int:
    mode = setting("HEARTHSIGNAL_MODE", "demo").lower()
    try:
        interval = interval_seconds(setting("HEARTHSIGNAL_INTERVAL", str(DEFAULT_INTERVAL)))
        port = int(setting("HEARTHSIGNAL_PORT", "8080"))
        if not 1 <= port <= 65535:
            raise ValueError("HEARTHSIGNAL_PORT must be between 1 and 65535")
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    REPORTS.mkdir(parents=True, exist_ok=True)
    generate(mode, interval)
    if setting("HEARTHSIGNAL_RUN_ONCE", "false").lower() in {"1", "true", "yes"}:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        return 0 if status.get("state") == "ready" else 1

    stop = threading.Event()
    thread = threading.Thread(target=scheduler, args=(mode, interval, stop), daemon=True)
    thread.start()
    server = ThreadingHTTPServer(("0.0.0.0", port), HearthsignalHandler)

    def shutdown(_signum: int, _frame: object) -> None:
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(f"Hearthsignal is ready at http://0.0.0.0:{port} ({mode} mode)", flush=True)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
