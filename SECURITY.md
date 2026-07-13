# Security policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, or private infrastructure information. Use the repository owner's private security-reporting channel when one is published.

## Security model

Fixture mode performs no network or process calls. Live mode is opt-in and may:

- run the read-only `docker ps` command;
- read disk-capacity and configured backup-file metadata;
- send unauthenticated HEAD requests to configured HTTP URLs.

Live configuration and generated runtime data are ignored by Git. Review configuration before every first run and grant the executing account only the access it needs.
