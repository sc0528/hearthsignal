# Troubleshooting

## The page does not open

Run `docker compose ps` and `docker compose logs hearthsignal`. Confirm port 8088 is free, or set `HEARTHSIGNAL_PORT` to another host port before starting Compose.

## The report still shows example data

The default is intentionally safe demo mode. Start Docker monitoring with:

```console
docker compose -f compose.yaml -f compose.docker.yaml up -d
```

## Docker checks show permission denied

Use `compose.docker.yaml`, which includes both the socket mount and the user required to access it. Rootless Docker users may need to replace `/var/run/docker.sock` with their actual socket path.

## Live mode says no checks are enabled

Set `enabled` to `true` for at least one check in `config.live.json`, then restart with `docker compose restart`.

## A mounted path is missing

The path in `config.live.json` must match its path inside the container. For example, a host mount `/srv/backups:/mnt/backups:ro` uses `/mnt/backups` in the JSON.

## The latest run failed

Open `/api/status` or run `docker compose logs hearthsignal`. Hearthsignal preserves the last successful report while showing the collection error in status metadata.

## The report looks stale

Check `/api/status` for `last_success` and `next_run`. Restarting the container triggers an immediate run. The minimum supported interval is five minutes.

## Reset everything

`docker compose down --volumes` removes the container and its stored reports. The next `docker compose up -d` starts cleanly.
