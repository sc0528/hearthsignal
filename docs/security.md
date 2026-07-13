# Security and sanitization

Hearthsignal provides an offline example-data workflow and an explicitly enabled, read-only live collector.

## Current safety properties

- Reads local JSON files only.
- Rejects URLs and paths outside the project.
- Requires an explicit `--dry-run` flag.
- Fixture mode uses no network calls or subprocesses.
- Live mode runs `docker ps` only when Docker is enabled, reads disk/file metadata, and sends HEAD requests only to configured URLs.
- Docker insights also use read-only `docker stats` and `docker inspect` calls.
- Measurement history remains in the ignored local `runtime/` directory.
- Discord webhook URLs are read from an environment variable and are never written to generated reports.
- Ships only purpose-built example names, timestamps, results, and platform descriptions.
- Escapes fixture content before inserting it into HTML.

## Never commit

- Real IP addresses, DNS names, internal URLs, or topology
- Usernames, passwords, API keys, tokens, cookies, or certificates
- Real service exports, logs, screenshots, dashboard captures, or backup paths
- Data copied from a live home-lab repository, even if it appears harmless

## Future live checks

Live integrations remain opt-in, use read-only operations and timeouts, and require `--live`. The collector does not accept credentials. Docker socket access is powerful even for read operations; users should run the collector as an account with only the access they intentionally grant.
