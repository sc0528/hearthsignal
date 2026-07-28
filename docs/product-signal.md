# Product Signal dashboard

Hearthsignal publishes a daily, public evidence dashboard at:

`https://sc0528.github.io/hearthsignal/analytics-dashboard/`

The dashboard is intended for product validation. It tracks GitHub repository
discovery, trial intent, and sustained interest without collecting personal data.

## Schedule

The `Refresh Product Signal` workflow captures data once daily at 9:15 AM
America/New_York. It uses two UTC triggers plus a timezone gate so daylight-saving
time does not shift the capture. It can also be run manually from GitHub Actions.

## Credentials

The workflow first uses an optional repository secret named `ANALYTICS_TOKEN`.
When that secret is absent it falls back to the repository-scoped `GITHUB_TOKEN`.
Public repository metrics always remain available. GitHub may require a
fine-grained token with read-only **Administration** access to expose traffic
views, clones, referrers, and popular paths.

Never add a token to the repository. If the fallback token cannot read traffic,
the collector records that limitation and the dashboard labels the missing data
instead of displaying stale or invented values.

## Data interpretation

- Visitors and views indicate discovery.
- Unique clones suggest trial intent but can include automation and maintainer tests.
- Stars are a stronger signal of sustained interest.
- GitHub traffic is a rolling 14-day window, so daily snapshots are directional.
- No usernames, IP addresses, credentials, or private home-lab details are stored.
