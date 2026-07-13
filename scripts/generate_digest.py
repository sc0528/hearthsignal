#!/usr/bin/env python3
"""Generate Markdown and HTML health digests from normalized local check data."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SEVERITY = {"ok": 0, "warning": 1, "critical": 2}


def local_path(raw: str, purpose: str) -> Path:
    if "://" in raw:
        raise ValueError(f"{purpose} must be a local path, not a URL")
    candidate = (ROOT / raw).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{purpose} must stay inside the project directory") from exc
    return candidate


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def classify(check: dict[str, Any], thresholds: dict[str, Any]) -> str:
    declared = check.get("status", "auto")
    if declared in SEVERITY:
        return declared
    value = check.get("value")
    if check.get("type") == "disk_usage":
        if value >= thresholds["disk_critical_percent"]:
            return "critical"
        if value >= thresholds["disk_warning_percent"]:
            return "warning"
        return "ok"
    if check.get("type") == "backup_freshness":
        if value >= thresholds["backup_critical_hours"]:
            return "critical"
        if value >= thresholds["backup_warning_hours"]:
            return "warning"
        return "ok"
    threshold_pairs = {
        "container_cpu": ("container_cpu_warning_percent", "container_cpu_critical_percent"),
        "container_memory": ("container_memory_warning_percent", "container_memory_critical_percent"),
        "container_restarts": ("container_restart_warning", "container_restart_critical"),
    }
    if check.get("type") in threshold_pairs:
        warning_key, critical_key = threshold_pairs[check["type"]]
        if value >= thresholds[critical_key]: return "critical"
        if value >= thresholds[warning_key]: return "warning"
        return "ok"
    raise ValueError(f"check type {check.get('type')!r} requires an explicit status")


def validate(config: dict[str, Any], services: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    required = {"report", "inputs", "outputs", "thresholds"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"config is missing: {', '.join(sorted(missing))}")
    service_ids = [item.get("id") for item in services]
    if len(service_ids) != len(set(service_ids)) or None in service_ids:
        raise ValueError("every service must have a unique id")
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise ValueError("check-results.json must contain a checks list")
    unknown = {item.get("service_id") for item in checks} - set(service_ids)
    if unknown:
        raise ValueError(f"checks reference unknown services: {', '.join(sorted(unknown))}")
    for check in checks:
        check["resolved_status"] = classify(check, config["thresholds"])
    return checks


def display_value(check: dict[str, Any]) -> str:
    value = check.get("value", "—")
    if isinstance(value, bool):
        value = "yes" if value else "no"
    unit = check.get("unit", "")
    separator = "" if unit in {"", "%"} else " "
    return f"{value}{separator}{unit}"


def detail(check: dict[str, Any], service: dict[str, Any]) -> str:
    if check["type"] == "disk_usage":
        return f"{service['name']} disk usage is at {display_value(check)}."
    if check["type"] == "backup_freshness":
        return f"{service['name']} last completed {display_value(check)} ago."
    return f"{service['name']}: {check['summary']}."


def action(check: dict[str, Any]) -> str:
    return check.get("action", {
        "disk_usage": "Remove unneeded data or increase the volume capacity.",
        "backup_freshness": "Review the backup job and run or repair it.",
        "availability": "Confirm the service is running and review its recent logs.",
        "container_health": "Inspect the container health check and recent logs.",
        "container_restarts": "Inspect container logs and resource limits.",
        "http_availability": "Confirm the service and its proxy or DNS route are available.",
    }.get(check.get("type"), "Review this service and its recent logs."))


def render_markdown(config: dict[str, Any], services: dict[str, dict[str, Any]], checks: list[dict[str, Any]], generated_at: str) -> str:
    attention = sorted((c for c in checks if c["resolved_status"] != "ok"), key=lambda c: SEVERITY[c["resolved_status"]], reverse=True)
    overall = "ATTENTION" if attention else "HEALTHY"
    title = config["report"]["title"]
    service_word = "service" if len(services) == 1 else "services"
    lines = [f"# {title}", "", f"**Overall status: {overall}**", "", f"{len(attention)} items need attention across {len(services)} {service_word}.", "", "## Needs attention", ""]
    if attention:
        lines.extend(f"- **{c['resolved_status'].title()}:** {detail(c, services[c['service_id']])} **Next step:** {action(c)}" for c in attention)
    else:
        lines.append("- Nothing needs attention.")
    lines.extend(["", "## All checks", "", "| Service | Check | Status | Value | Summary |", "|---|---|---:|---:|---|"])
    for check in checks:
        service = services[check["service_id"]]
        lines.append(f"| {service['name']} | {check['type'].replace('_', ' ').title()} | {check['resolved_status'].upper()} | {display_value(check)} | {check['summary']} |")
    changes = config.get("changes", [])
    lines.extend(["", "## Changes since the previous run", ""])
    lines.extend(f"- {item}" for item in changes) if changes else lines.append("- No status changes detected.")
    forecasts = [c for c in checks if c.get("forecast")]
    lines.extend(["", "## Looking ahead", ""])
    lines.extend(f"- **{services[c['service_id']]['name']}:** {c['forecast']}" for c in forecasts) if forecasts else lines.append("- No near-term capacity risks detected.")
    source_note = config.get("source_note", "Generated locally from bundled example data. Live systems were not contacted.")
    lines.extend(["", "---", f"Generated: {generated_at} ({config['report']['timezone_label']}) · {config['report']['owner_label']}", "", f"_{source_note}_", ""])
    return "\n".join(lines)


def render_html(config: dict[str, Any], services: dict[str, dict[str, Any]], checks: list[dict[str, Any]], generated_at: str, template: str, history: list[dict[str, Any]] | None = None) -> str:
    esc = lambda value: html.escape(str(value))
    attention = sorted((c for c in checks if c["resolved_status"] != "ok"), key=lambda c: SEVERITY[c["resolved_status"]], reverse=True)
    counts = Counter(c["resolved_status"] for c in checks)
    score = max(0, 100 - counts["critical"] * 15 - counts["warning"] * 7)
    try: date_label = datetime.fromisoformat(generated_at).strftime("%A, %B %d")
    except ValueError: date_label = generated_at
    mark = '<svg class="brand-mark" viewBox="0 0 64 64" role="img" aria-label="Hearthsignal"><path d="M10 28V16a22 22 0 0 1 44 0v12" fill="none" stroke="#2E7D48" stroke-width="5" stroke-linecap="round"/><path d="M18 27V18a14 14 0 0 1 28 0v9" fill="none" stroke="#2563EB" stroke-width="5" stroke-linecap="round"/><circle cx="32" cy="18" r="4" fill="#2563EB"/><path d="M32 22v9" stroke="#2563EB" stroke-width="5"/><path d="M13 43 32 27l19 16v17H39V47H25v13H13Z" fill="none" stroke="#0B1D33" stroke-width="6" stroke-linejoin="round"/><path d="M28 50h8v10h-8z" fill="#FF6B57"/></svg>'
    header = f'<header><div class="brand-lockup">{mark}<div><h1>{esc(config["report"]["title"])}</h1><div class="tagline">Home lab health, <em>interpreted.</em></div><div class="muted">{esc(date_label)} · {esc(config["report"]["owner_label"])}</div></div></div><div class="actions"><button class="button" data-print>Print briefing</button><button class="button primary" data-details>View signals</button></div></header>'
    headline = "All systems healthy" if not attention else "Attention needed"
    summary = "No action is required today." if not attention else f"Your lab is mostly healthy, but {len(attention)} {'issue requires' if len(attention)==1 else 'issues require'} attention. Start with the prioritized incidents."
    overview = f'<div class="overview"><div class="score" style="--score:{score}"><strong>{score}</strong><span>/100<br>Health score</span></div><div><div class="headline">{headline}</div><p>{esc(summary)}</p><div class="statline"><div class="stat ok"><strong>{counts["ok"]}</strong>Healthy</div><div class="stat warning"><strong>{counts["warning"]}</strong>Warnings</div><div class="stat critical"><strong>{counts["critical"]}</strong>Critical</div></div></div></div>'
    incident_html = "".join(f'<article class="incident {c["resolved_status"]}"><div class="incident-head"><h3>{esc(services[c["service_id"]]["name"])} — {esc(display_value(c))}</h3><span class="severity">{c["resolved_status"]}</span></div><p class="why"><strong>Why it matters</strong>{esc(c.get("impact", detail(c, services[c["service_id"]])))}</p><p class="next"><strong>Recommended action</strong>{esc(action(c))}</p></article>' for c in attention) or '<p class="muted">Nothing needs attention. Your monitored systems are within their configured limits.</p>'
    points = history or [{"label": "Today", "score": score}]
    coords = []; labels = []
    for i, item in enumerate(points):
        x = 25 + (i * 550 / max(1, len(points)-1)); y = 120 - float(item["score"])
        coords.append(f"{x:.1f},{y:.1f}"); labels.append(f'<text class="trend-label" x="{x:.1f}" y="145" text-anchor="middle">{esc(item["label"])}</text><circle class="trend-dot" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{item["score"]}/100</title></circle>')
    joined_coords = " ".join(coords)
    joined_labels = "".join(labels)
    trend = f'<div class="section trend"><h2>Health trend (7 days)</h2><svg viewBox="0 0 600 155" role="img" aria-label="Health score trend"><line class="trend-grid" x1="20" y1="30" x2="580" y2="30"/><line class="trend-grid" x1="20" y1="70" x2="580" y2="70"/><line class="trend-grid" x1="20" y1="110" x2="580" y2="110"/><polyline class="trend-line" points="{joined_coords}"/>{joined_labels}</svg></div>'
    changes = config.get("changes", [])
    changes_html = "".join(f'<div class="timeline-item"><time>{"Today" if i==0 else "Earlier"}</time><i></i><p>{esc(item)}</p></div>' for i,item in enumerate(changes)) or '<div class="timeline-item"><time>Latest</time><i></i><p>No status changes detected.</p></div>'
    forecast_checks = [c for c in checks if c.get("forecast")]
    forecasts_html = "".join(f'<div class="forecast-item"><strong>{esc(services[c["service_id"]]["name"])}</strong><span>{esc(c["forecast"])}</span></div>' for c in forecast_checks) or '<p class="muted">No near-term capacity risks detected.</p>'
    grouped = defaultdict(list)
    for c in checks: grouped[services[c["service_id"]].get("category", "other")].append(c)
    category_html = ""
    for category, items in grouped.items():
        worst = max((c["resolved_status"] for c in items), key=lambda value: SEVERITY[value]); note = "All healthy" if worst == "ok" else f'{sum(c["resolved_status"] != "ok" for c in items)} need attention'
        category_html += f'<div class="category-row"><strong>{esc(category.title())}</strong><span>{len(items)} checks</span><span class="status-{worst}">{esc(note)}</span></div>'
    healthy = "".join(f'<span class="healthy-item">{esc(services[c["service_id"]]["name"])}</span>' for c in checks if c["resolved_status"] == "ok") or '<span class="muted">Healthy systems will appear here.</span>'
    replacements = {"{{PAGE_TITLE}}":esc(config["report"]["title"]),"{{HEADER}}":header,"{{OVERVIEW}}":overview,"{{TREND}}":trend,"{{INCIDENTS}}":incident_html,"{{FORECASTS}}":forecasts_html,"{{CHANGES}}":changes_html,"{{CATEGORIES}}":category_html,"{{HEALTHY}}":healthy,"{{SOURCE_NOTE}}":esc(config.get("source_note", "Generated locally from bundled example data."))}
    for key, value in replacements.items(): template = template.replace(key, value)
    return template


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.example.json", help="local config path relative to the project")
    parser.add_argument("--dry-run", action="store_true", help="required safety acknowledgement for fixture-only generation")
    parser.add_argument("--live-report", action="store_true", help="render data created by the opt-in live collector")
    parser.add_argument("--example", action="store_true", help="write the checked-in static example report names")
    args = parser.parse_args()
    if args.dry_run == args.live_report:
        parser.error("pass exactly one of --dry-run or --live-report")
    try:
        config = load_json(local_path(args.config, "config"))
        if args.example:
            config["outputs"] = {"markdown": "reports/example-digest.md", "html": "reports/example-digest.html"}
        services_list = load_json(local_path(config["inputs"]["services"], "services input"))
        payload = load_json(local_path(config["inputs"]["checks"], "checks input"))
        checks = validate(config, services_list, payload)
        services = {item["id"]: item for item in services_list}
        generated_at = payload.get("generated_at", "timestamp not supplied")
        template = local_path("templates/report.html", "HTML template").read_text(encoding="utf-8")
        markdown = render_markdown(config, services, checks, generated_at)
        history = config.get("history") or (load_json(local_path(config["inputs"]["history"], "history input")) if config["inputs"].get("history") else None)
        html_report = render_html(config, services, checks, generated_at, template, history)
        md_path = local_path(config["outputs"]["markdown"], "Markdown output")
        html_path = local_path(config["outputs"]["html"], "HTML output")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
        html_path.write_text(html_report, encoding="utf-8")
        print(f"Wrote {md_path.relative_to(ROOT)}")
        print(f"Wrote {html_path.relative_to(ROOT)}")
        return 0
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
