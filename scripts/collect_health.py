#!/usr/bin/env python3
"""Collect read-only home-lab health signals and produce a Hearthsignal briefing."""

from __future__ import annotations

import argparse
import glob
import json
import os
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


def run_json_lines(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=True)
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def number(raw):
    try:
        return float(str(raw).strip().rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def docker_checks(config):
    rows = run_json_lines(["docker", "ps", "-a", "--format", "{{json .}}"])
    ids = [row.get("ID") for row in rows if row.get("ID")]
    stats_rows = run_json_lines(["docker", "stats", "--no-stream", "--format", "{{ json . }}"]) if ids else []
    stats = {row.get("ID", row.get("Container")): row for row in stats_rows}
    inspections = run_json_lines(["docker", "inspect", "--format", "{{json .}}", *ids]) if ids else []
    inspect_by_id = {row.get("Id", "")[:12]: row for row in inspections}
    services, checks = [], []
    limits = config.get("thresholds", {})
    for index, row in enumerate(rows):
        container_id = row.get("ID", ""); sid = f"docker-{container_id or index}"
        name = row.get("Names", f"Container {index + 1}"); status_text = row.get("Status", "unknown")
        unhealthy = "unhealthy" in status_text.lower() or "exited" in status_text.lower()
        services.append(service(sid, name, "container"))
        checks.append({"service_id": sid, "type": "container_health", "status": "critical" if unhealthy else "ok", "value": status_text, "summary": status_text})
        stat = stats.get(container_id, stats.get(name, {})); inspect = inspect_by_id.get(container_id, {})
        if not unhealthy and stat:
            checks.append({"service_id": sid, "type": "container_cpu", "status": "auto", "value": number(stat.get("CPUPerc")), "unit": "%", "summary": "Current container CPU usage"})
            if stat.get("MemPerc") is not None:
                checks.append({"service_id": sid, "type": "container_memory", "status": "auto", "value": number(stat.get("MemPerc")), "unit": "%", "summary": "Current container memory usage"})
        restarts = int(inspect.get("RestartCount", 0)); image = inspect.get("Config", {}).get("Image", row.get("Image", "unknown"))
        checks.append({"service_id": sid, "type": "container_restarts", "status": "auto", "value": restarts, "unit": "restarts", "summary": f"Restart count · image {image}", "metadata": {"image": image}})
    return services, checks


def collect(config):
    services, checks = [], []
    if config["checks"].get("docker", {}).get("enabled"):
        found_services, found_checks = docker_checks(config); services += found_services; checks += found_checks
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
            request = urllib.request.Request(item["url"], method="HEAD", headers={"User-Agent": "Hearthsignal/0.2"})
            with urllib.request.urlopen(request, timeout=item.get("timeout_seconds", 5)) as response:
                ok = 200 <= response.status < 400; summary = f"HTTP {response.status}"
        except Exception as exc: summary = f"Unavailable ({type(exc).__name__})"
        services.append(service(sid, item["name"], "web service")); checks.append({"service_id": sid, "type": "http_availability", "status": "ok" if ok else "critical", "value": ok, "summary": summary})
    if not checks: raise ValueError("no live checks are enabled; edit config.live.json or run setup_hearthsignal.py --init")
    return services, checks


def state_status(check, thresholds):
    if check["status"] != "auto": return check["status"]
    value = check["value"]; check_type = check["type"]
    pairs = {
        "disk_usage": ("disk_warning_percent", "disk_critical_percent"),
        "backup_freshness": ("backup_warning_hours", "backup_critical_hours"),
        "container_cpu": ("container_cpu_warning_percent", "container_cpu_critical_percent"),
        "container_memory": ("container_memory_warning_percent", "container_memory_critical_percent"),
        "container_restarts": ("container_restart_warning", "container_restart_critical"),
    }
    warning_key, critical_key = pairs[check_type]
    return "critical" if value >= thresholds[critical_key] else "warning" if value >= thresholds[warning_key] else "ok"


def score_checks(checks, thresholds):
    statuses = [state_status(check, thresholds) for check in checks]
    return max(0, 100 - statuses.count("critical") * 15 - statuses.count("warning") * 7)


def update_history(checks, thresholds, now, existing):
    measurements = {f"{c['service_id']}:{c['type']}": c["value"] for c in checks if isinstance(c.get("value"), (int, float)) and not isinstance(c.get("value"), bool)}
    entry = {"timestamp": now.isoformat(timespec="seconds"), "score": score_checks(checks, thresholds), "measurements": measurements}
    return (existing + [entry])[-30:]


def add_capacity_forecasts(checks, history, critical_percent):
    if len(history) < 2: return []
    forecasts = []
    first, last = history[0], history[-1]
    elapsed_days = max((datetime.fromisoformat(last["timestamp"]) - datetime.fromisoformat(first["timestamp"])).total_seconds() / 86400, 1 / 24)
    for check in checks:
        if check["type"] != "disk_usage": continue
        key = f"{check['service_id']}:{check['type']}"; start = first.get("measurements", {}).get(key); current = check["value"]
        if not isinstance(start, (int, float)) or current <= start: continue
        growth = (current - start) / elapsed_days
        days = (critical_percent - current) / growth if growth > 0 else 0
        if 0 < days <= 90:
            forecast = f"Projected to reach {critical_percent}% in about {max(1, round(days))} days at the current growth rate."
            check["forecast"] = forecast; check["impact"] = f"{check['summary']}. {forecast}"
            forecasts.append({"service_id": check["service_id"], "message": forecast})
    return forecasts


def build_discord_message(services, checks, thresholds):
    flagged = [(state_status(c, thresholds), c) for c in checks if state_status(c, thresholds) != "ok"]
    flagged.sort(key=lambda item: {"warning": 1, "critical": 2}[item[0]], reverse=True)
    score = score_checks(checks, thresholds); lines = [f"**Hearthsignal · {score}/100**", f"{len(flagged)} signals need attention."]
    for status, check in flagged[:3]: lines.append(f"• **{status.upper()}** {services[check['service_id']]['name']}: {check['summary']}")
    if not flagged: lines.append("All monitored systems are within their configured limits.")
    return "\n".join(lines)


def deliver_discord(config, message):
    delivery = config.get("delivery", {}).get("discord", {})
    if not delivery.get("enabled"): return False
    env_name = delivery.get("webhook_env", "HEARTHSIGNAL_DISCORD_WEBHOOK"); url = os.environ.get(env_name)
    if not url: raise ValueError(f"Discord delivery is enabled but {env_name} is not set")
    request = urllib.request.Request(url, data=json.dumps({"content": message[:2000]}).encode(), headers={"Content-Type": "application/json", "User-Agent": "Hearthsignal/0.2"}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in {200, 204}: raise ValueError(f"Discord delivery returned HTTP {response.status}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", default="config.live.json"); parser.add_argument("--live", action="store_true"); parser.add_argument("--no-delivery", action="store_true")
    args = parser.parse_args()
    if not args.live: parser.error("live collection requires the explicit --live flag")
    path = (ROOT / args.config).resolve()
    if ROOT not in path.parents: parser.error("config must be inside the project")
    try:
        config = json.loads(path.read_text(encoding="utf-8")); services, checks = collect(config); RUNTIME.mkdir(exist_ok=True); now = datetime.now().astimezone()
        previous_path = RUNTIME / "previous-status.json"; previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
        current = {f"{c['service_id']}:{c['type']}": state_status(c, config["thresholds"]) for c in checks}; changes = [f"{key} changed from {previous[key]} to {value}." for key, value in current.items() if key in previous and previous[key] != value]
        history_path = RUNTIME / "health-history.json"; old_history = json.loads(history_path.read_text()) if history_path.exists() else []
        history = update_history(checks, config["thresholds"], now, old_history); forecasts = add_capacity_forecasts(checks, history, config["thresholds"]["disk_critical_percent"])
        (RUNTIME / "services.json").write_text(json.dumps(services, indent=2), encoding="utf-8"); (RUNTIME / "checks.json").write_text(json.dumps({"generated_at": now.isoformat(timespec="seconds"), "checks": checks}, indent=2), encoding="utf-8")
        previous_path.write_text(json.dumps(current, indent=2), encoding="utf-8"); history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
        chart_history = [{"label": datetime.fromisoformat(item["timestamp"]).strftime("%a"), "score": item["score"]} for item in history[-7:]]
        render_config = {"report": config["report"], "inputs": {"services": "runtime/services.json", "checks": "runtime/checks.json"}, "outputs": config["outputs"], "thresholds": config["thresholds"], "changes": changes, "forecasts": forecasts, "history": chart_history, "source_note": "Generated locally from explicitly enabled, read-only live checks."}
        (RUNTIME / "render-config.json").write_text(json.dumps(render_config, indent=2), encoding="utf-8")
        code = subprocess.call([sys.executable, str(ROOT / "scripts" / "generate_digest.py"), "--config", "runtime/render-config.json", "--live-report"])
        if code == 0 and not args.no_delivery: deliver_discord(config, build_discord_message({s["id"]: s for s in services}, checks, config["thresholds"]))
        return code
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
