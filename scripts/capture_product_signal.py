#!/usr/bin/env python3
"""Capture a daily GitHub product-interest snapshot without third-party packages."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_VERSION = "2022-11-28"
MAX_SNAPSHOTS = 400


def api_get(path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "hearthsignal-product-signal",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def optional_get(path: str, token: str) -> tuple[Any | None, str | None]:
    try:
        return api_get(path, token), None
    except urllib.error.HTTPError as error:
        return None, f"GitHub returned HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError) as error:
        return None, f"GitHub request failed: {error.reason if hasattr(error, 'reason') else error}"


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "snapshots": []}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("snapshots"), list):
        raise ValueError(f"{path} is not a valid product-signal history file")
    return data


def capture(repository: str, token: str) -> dict[str, Any]:
    repo = api_get(f"/repos/{repository}", token)
    views, views_error = optional_get(f"/repos/{repository}/traffic/views?per=day", token)
    clones, clones_error = optional_get(f"/repos/{repository}/traffic/clones?per=day", token)
    paths, paths_error = optional_get(f"/repos/{repository}/traffic/popular/paths", token)
    referrers, referrers_error = optional_get(
        f"/repos/{repository}/traffic/popular/referrers", token
    )
    traffic_errors = [
        message
        for message in (views_error, clones_error, paths_error, referrers_error)
        if message
    ]
    traffic_available = views is not None and clones is not None

    return {
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository": repository,
        "repository_metrics": {
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "watchers": repo["subscribers_count"],
            "open_issues": repo["open_issues_count"],
            "size_kb": repo["size"],
            "pushed_at": repo["pushed_at"],
        },
        "traffic": {
            "available": traffic_available,
            "window_days": 14,
            "views": views,
            "clones": clones,
            "popular_paths": paths or [],
            "referrers": referrers or [],
            "errors": sorted(set(traffic_errors)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository", default=os.getenv("GITHUB_REPOSITORY", "sc0528/hearthsignal")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("analytics-data/snapshots.json"),
    )
    parser.add_argument("--token", default=os.getenv("ANALYTICS_TOKEN") or os.getenv("GH_TOKEN"))
    args = parser.parse_args()

    if not args.token:
        parser.error("Provide ANALYTICS_TOKEN, GH_TOKEN, or --token")

    history = load_history(args.output)
    snapshot = capture(args.repository, args.token)
    if (
        not snapshot["traffic"]["available"]
        and any(item.get("traffic", {}).get("available") for item in history["snapshots"])
    ):
        print(
            "Traffic access is unavailable; retaining the last complete snapshot.",
            file=sys.stderr,
        )
        return 0
    snapshots = history["snapshots"]

    # Manual reruns replace the same UTC day's capture instead of inflating history.
    today = snapshot["captured_at"][:10]
    snapshots = [item for item in snapshots if item.get("captured_at", "")[:10] != today]
    snapshots.append(snapshot)
    snapshots = sorted(snapshots, key=lambda item: item["captured_at"])[-MAX_SNAPSHOTS:]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            {
                "schema_version": 1,
                "product": "Hearthsignal",
                "repository": args.repository,
                "snapshots": snapshots,
            },
            handle,
            indent=2,
        )
        handle.write("\n")
    temporary.replace(args.output)

    availability = "complete" if snapshot["traffic"]["available"] else "public metrics only"
    print(f"Captured {args.repository}: {availability}")
    for error in snapshot["traffic"]["errors"]:
        print(f"warning: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
