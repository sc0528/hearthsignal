# Security model

Hearthsignal is local-first. Reports, history, and configuration remain on the host unless optional Discord delivery is enabled.

## Default container

The default `demo` mode:

- Uses fictional bundled data only
- Makes no network calls
- Mounts no host directories or Docker socket
- Runs as an unprivileged user
- Uses a read-only container filesystem with separate report and state volumes
- Drops all Linux capabilities and blocks privilege escalation
- Publishes the web port to `127.0.0.1` only
- Serves only generated report files and status metadata with restrictive browser security headers

## Live access

Every live integration is opt-in. Disk and backup checks require explicit read-only mounts. HTTP checks contact only configured URLs and use timeouts. Discord reads its webhook from an environment variable.

Docker socket access is different: control of the socket is effectively root access to the Docker host, even when the socket is mounted read-only. `compose.docker.yaml` therefore makes this access visible and separate from the safe default. Do not expose Hearthsignal's container or Docker socket to untrusted users.

## Report resilience

Hearthsignal writes run status separately from the report. If collection fails, the most recent successful report remains available and `/api/status` reports the error. Webhook values are never written to output.

## Never commit

- Real IP addresses, DNS names, internal URLs, or topology
- Usernames, passwords, API keys, tokens, cookies, or certificates
- Real service exports, logs, screenshots, dashboard captures, or backup paths
- `config.live.json` or `compose.override.yaml`
