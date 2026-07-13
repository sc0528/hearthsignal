# Setup

## Requirements

- Python 3.10 or newer
- A terminal (PowerShell, Command Prompt, Bash, or zsh)
- No third-party Python packages

## Generate the sample digest

From the project root:

```powershell
python scripts/generate_digest.py --dry-run
```

Hearthsignal reads the bundled example fixtures and creates `reports/latest-digest.md` and `reports/latest-digest.html`.

## Use a separate local config

```powershell
Copy-Item config.example.json config.local.json
python scripts/generate_digest.py --config config.local.json --dry-run
```

`config.local.json` is ignored by Git. Keep input and output paths relative to this project; paths outside the project and URLs are rejected.

## Enable live checks

Copy `config.live.example.json` to `config.live.json`, enable selected entries, replace placeholder paths/URLs, then run:

```powershell
python scripts/collect_health.py --config config.live.json --live
```

Docker checks require the Docker CLI to be installed and accessible. Disk and backup paths may point to local or mounted storage. HTTP checks use an unauthenticated HEAD request and a configurable timeout.

## Reset generated output

Delete `reports/latest-digest.md` and `reports/latest-digest.html`. The checked-in `example-digest` files remain as stable product samples.
