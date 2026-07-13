# Contributing

Thanks for helping make home-lab health easier to understand.

## Before opening a change

1. Never include real infrastructure identifiers, credentials, logs, screenshots, or exports.
2. Keep fixture mode offline and deterministic.
3. Make live checks explicitly enabled, read-only, timeout-bound, and narrowly scoped.
4. Use only the Python standard library unless a dependency has a clear security and maintenance justification.

## Development

```powershell
python -m unittest discover -s tests -v
python scripts/generate_digest.py --dry-run --example
```

Open `reports/example-digest.html` and inspect desktop, mobile, and print layouts. Describe user-visible behavior and safety implications in pull requests.
