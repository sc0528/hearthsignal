# Hearthsignal

A privacy-first daily operations briefing for people running a home lab.

> **Home lab health, interpreted.**

[**View Product Signal Portfolio**](https://sc0528.github.io/hearthsignal/analytics-dashboard/) · [View the source](https://github.com/sc0528/hearthsignal)

Hearthsignal tells you what is broken, what changed, why it matters, and what to do next—before you open six dashboards.

## See the briefing

[![Hearthsignal daily briefing](assets/hearthsignal-report.png)](reports/example-digest.html)

The briefing ranks incidents, explains their impact, recommends the next action, tracks health over time, and forecasts storage pressure. [Open the complete HTML example](reports/example-digest.html).

## Start in one command

Docker Compose is the recommended installation. It starts Hearthsignal safely with bundled example data:

```console
docker compose up -d
```

Open **http://localhost:8088**. Hearthsignal generates immediately, refreshes daily, survives restarts, and preserves its reports and history in Docker volumes. It listens on the local machine only by default.

Stop it with `docker compose down`. Remove Hearthsignal and its stored reports with `docker compose down --volumes`.

## Monitor Docker

When you are ready to inspect the local Docker engine:

```console
docker compose -f compose.yaml -f compose.docker.yaml up -d
```

Refresh **http://localhost:8088**. The report now covers container health, CPU, memory, restart counts, and images.

This mode deliberately mounts the Docker socket. Socket access is effectively root access to the Docker host, even with a read-only mount. Use it only on a host you control. Demo mode never mounts the socket and runs without Linux capabilities as an unprivileged user.

## Choose a mode

| Mode | Best for | Setup |
|---|---|---|
| `demo` | Seeing the complete product safely | `docker compose up -d` |
| `docker` | Monitoring containers on this Docker host | Add `compose.docker.yaml` |
| `live` | Docker, disks, backups, HTTP, and Discord | Copy the advanced config example |

### Advanced live checks

1. Copy `config.live.example.json` to `config.live.json`.
2. Copy `compose.live.example.yaml` to `compose.override.yaml`.
3. Enable only the checks you want and edit the read-only host mounts.
4. Run `docker compose up -d`.

Paths in `config.live.json` must be the paths visible inside the container, such as `/mnt/backups`. Discord webhooks stay in the `HEARTHSIGNAL_DISCORD_WEBHOOK` environment variable and are never stored in reports.

## What you get

- One browser-accessible daily briefing at a stable URL
- Immediate generation followed by automatic scheduled refreshes
- A health score and seven-day direction
- Incidents ranked by urgency, impact, and recommended action
- Change detection and disk-capacity forecasts
- Docker health, CPU, memory, restart, and image signals
- Optional disk, backup freshness, HTTP, and Discord integrations
- Last-good-report retention when a later collection fails
- A machine-readable status endpoint at `/api/status`
- Responsive, printable HTML plus Markdown output

Change the refresh interval with `HEARTHSIGNAL_INTERVAL` in seconds; the minimum is 300. Change the host port with `HEARTHSIGNAL_PORT`. Set `HEARTHSIGNAL_BIND=0.0.0.0` only when you intentionally want the briefing available to other devices on your network. For example:

```console
HEARTHSIGNAL_PORT=8090 HEARTHSIGNAL_INTERVAL=3600 docker compose up -d
```

On PowerShell, set the variables first with `$env:HEARTHSIGNAL_PORT = "8090"` and `$env:HEARTHSIGNAL_INTERVAL = "3600"`.

## Operate it

```console
docker compose logs --follow
docker compose restart
docker compose pull
docker compose up -d
```

The container exposes `/healthz` for liveness and `/api/status` for the latest generation result. A failed collection does not erase the most recent successful briefing.

## Run without Docker

Python 3.10 or newer is supported and requires no third-party packages:

```console
python scripts/generate_digest.py --dry-run
```

For direct live collection, copy `config.live.example.json`, enable selected checks, and run:

```console
python scripts/collect_health.py --config config.live.json --live
```

## Documentation

- [Installation and configuration](docs/setup.md)
- [Security model](docs/security.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Brand system](docs/brand.md)

Run the test suite with `python -m unittest discover -s tests -v`.

## License

Hearthsignal is provided under the [MIT License](LICENSE).
