# Installation and configuration

## Recommended installation

Requirements: Docker Engine or Docker Desktop with Docker Compose.

```console
docker compose up -d
```

Open http://localhost:8088. The default is a complete, offline demonstration using bundled fictional data. It makes no network calls and requires no host access.

## Enable Docker monitoring

```console
docker compose -f compose.yaml -f compose.docker.yaml up -d
```

The override changes the mode to `docker` and grants access to the local Docker socket. No JSON configuration is required. Remove the override from the command to return to demo mode.

## Enable custom live checks

```console
cp config.live.example.json config.live.json
cp compose.live.example.yaml compose.override.yaml
```

PowerShell equivalents:

```powershell
Copy-Item config.live.example.json config.live.json
Copy-Item compose.live.example.yaml compose.override.yaml
```

Edit both private files:

- Enable selected checks in `config.live.json`.
- Add only the required read-only host mounts to `compose.override.yaml`.
- Use container paths in the JSON, such as `/mnt/backups`.
- Uncomment the socket mount and `user: "0:0"` only when Docker checks are enabled.

Then run `docker compose up -d`. Both private files are ignored by Git.

## Runtime settings

| Variable | Default | Purpose |
|---|---:|---|
| `HEARTHSIGNAL_MODE` | `demo` | `demo`, `docker`, or `live` |
| `HEARTHSIGNAL_INTERVAL` | `86400` | Seconds between runs; minimum 300 |
| `HEARTHSIGNAL_PORT` | `8088` | Browser port on the host |
| `HEARTHSIGNAL_BIND` | `127.0.0.1` | Host interface; use `0.0.0.0` for LAN access |
| `TZ` | `UTC` | Container timezone |
| `HEARTHSIGNAL_CONFIG` | `/config/hearthsignal.json` | Live configuration path |
| `HEARTHSIGNAL_DISCORD_WEBHOOK` | unset | Optional Discord webhook |

## Updating

```console
docker compose pull
docker compose up -d
```

Reports and history are kept in the `hearthsignal-data` and `hearthsignal-state` Docker volumes during updates.

## Direct Python installation

Python 3.10 or newer is supported without third-party packages.

```console
python scripts/generate_digest.py --dry-run
python scripts/setup_hearthsignal.py --init
python scripts/collect_health.py --config config.live.json --live
```
