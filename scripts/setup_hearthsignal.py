#!/usr/bin/env python3
"""Initialize Hearthsignal and report whether its optional integrations are ready."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def doctor(config_path):
    results = [("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0]), ("Docker CLI", shutil.which("docker") is not None, shutil.which("docker") or "not detected")]
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8")); enabled = []
        if config.get("checks", {}).get("docker", {}).get("enabled"): enabled.append("Docker")
        for name in ("disks", "backups", "http"):
            if any(item.get("enabled") for item in config.get("checks", {}).get(name, [])): enabled.append(name.title())
        results.append(("Live configuration", True, str(config_path.name)))
        results.append(("Enabled checks", bool(enabled), ", ".join(enabled) or "none yet"))
        discord = config.get("delivery", {}).get("discord", {})
        results.append(("Discord delivery", discord.get("enabled", False), "enabled" if discord.get("enabled") else "optional"))
    else: results.append(("Live configuration", False, "run with --init"))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--init", action="store_true"); parser.add_argument("--config", default="config.live.json")
    args = parser.parse_args(); target = (ROOT / args.config).resolve()
    if ROOT not in target.parents: parser.error("config must be inside the project")
    if args.init and not target.exists():
        shutil.copyfile(ROOT / "config.live.example.json", target); print(f"Created {target.name}")
    print("\nHearthsignal setup doctor\n")
    for label, ready, detail in doctor(target): print(f"{'[OK]' if ready else '[--]'} {label}: {detail}")
    print("\nNext: enable selected checks, then run python scripts/collect_health.py --live --no-delivery")
    return 0


if __name__ == "__main__": raise SystemExit(main())
