#!/usr/bin/env python3
"""Opt-in, read-only health collector for a small Docker home lab."""

from __future__ import annotations

import argparse
import glob
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"


def service(service_id, name, category):
    return {"id": service_id, "name": name, "category": category, "platform": category.title(), "importance": "normal"}


def docker_checks():
    result = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, timeout=15, check=True)
    services, checks = [], []
    for index, line in enumerate(result.stdout.splitlines()):
        row = json.loads(line); sid = f"docker-{index}"
        name = row.get("Names", f"Container {index + 1}"); status_text = row.get("Status", "unknown")
        unhealthy = "unhealthy" in status_text.lower() or "exited" in status_text.lower()
        services.append(service(sid, name, "container"))
        checks.append({"service_id": sid, "type": "container_health", "status": "critical" if unhealthy else "ok", "value": status_text, "summary": status_text})
    return services, checks


def collect(config):
    services, checks = [], []
    if config["checks"].get("docker", {}).get("enabled"):
        found_services, found_checks = docker_checks(); services += found_services; checks += found_checks
    for index, item in enumerate(config["checks"].get("disks", [])):
        if not item.get("enabled"): continue
        sid = f"disk-{index}"; usage = shutil.disk_usage(item["path"]); percent = round(usage.used / usage.total * 100, 1)
        services.append(service(sid, item["name"], "storage")); checks.append({"service_id": sid, "type": "disk_usage", "status": "auto", "value": percent, "unit": "%", "summary": "Storage capacity used"})
    now = datetime.now(timezone.utc)
    for index, item in enumerate(config["checks"].get("backups", [])):
        if not item.get("enabled"): continue
        sid = f"backup-{index}"; matches = [Path(p) for p in glob.glob(str(Path(item["path"]) / item.get("pattern", "*")))]
        hours = round((now.timestamp() - max(p.stat().st_mtime for p in matches)) / 3600, 1) if matches else 99999
        services.append(service(sid, item["name"], "backup")); checks.append({"service_id": sid, "type": "backup_freshness", "status": "auto", "value": hours, "unit": "hours", "summary": "Time since newest matching backup"})
    for index, item in enumerate(config["checks"].get("http", [])):
        if not item.get("enabled"): continue
        sid = f"http-{index}"; ok = False; summary = "Request failed"
        try:
            request = urllib.request.Request(item["url"], method="HEAD", headers={"User-Agent": "Hearthsignal/0.1"})
            with urllib.request.urlopen(request, timeout=item.get("timeout_seconds", 5)) as response:
                ok = 200 <= response.status < 400; summary = f"HTTP {response.status}"
        except Exception as exc: summary = f"Unavailable ({type(exc).__name__})"
        services.append(service(sid, item["name"], "web service")); checks.append({"service_id": sid, "type": "http_availability", "status": "ok" if ok else "critical", "value": ok, "summary": summary})
    if not checks: raise ValueError("no live checks are enabled; edit a copy of config.live.example.json")
    return services, checks


def state_status(check, thresholds):
    if check["status"] != "auto": return check["status"]
    value = check["value"]
    if check["type"] == "disk_usage":
        return "critical" if value >= thresholds["disk_critical_percent"] else "warning" if value >= thresholds["disk_warning_percent"] else "ok"
    return "critical" if value >= thresholds["backup_critical_hours"] else "warning" if value >= thresholds["backup_warning_hours"] else "ok"


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", default="config.live.json"); parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live: parser.error("live collection requires the explicit --live flag")
    path = (ROOT / args.config).resolve()
    if ROOT not in path.parents: parser.error("config must be inside the project")
    try:
        config = json.loads(path.read_text(encoding="utf-8")); services, checks = collect(config); RUNTIME.mkdir(exist_ok=True)
        previous_path = RUNTIME / "previous-status.json"; previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
        current = {f"{c['service_id']}:{c['type']}": state_status(c, config["thresholds"]) for c in checks}; changes = [f"{key} changed from {previous[key]} to {value}." for key, value in current.items() if key in previous and previous[key] != value]
        (RUNTIME / "services.json").write_text(json.dumps(services, indent=2), encoding="utf-8")
        (RUNTIME / "checks.json").write_text(json.dumps({"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "checks": checks}, indent=2), encoding="utf-8")
        previous_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        render_config = {"report": config["report"], "inputs": {"services": "runtime/services.json", "checks": "runtime/checks.json"}, "outputs": config["outputs"], "thresholds": config["thresholds"], "changes": changes, "source_note": "Generated locally from explicitly enabled, read-only live checks."}
        (RUNTIME / "render-config.json").write_text(json.dumps(render_config, indent=2), encoding="utf-8")
        return subprocess.call([sys.executable, str(ROOT / "scripts" / "generate_digest.py"), "--config", "runtime/render-config.json", "--live-report"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
