# Troubleshooting

## `--dry-run` is required

The flag is an intentional safety acknowledgement. Run `python scripts/generate_digest.py --dry-run`.

## Python is not found

Install Python 3.10 or newer, or try the Windows launcher: `py scripts/generate_digest.py --dry-run`.

## A JSON parsing error appears

Check commas, quotation marks, and braces in your local config or fixture. JSON does not allow trailing commas or comments.

## An input references an unknown service

Every `service_id` in the check-results file must match an `id` in the services file.

## A path is rejected

All config, input, template, and output files must remain within this project directory. Remote URLs are intentionally unsupported.

## The HTML report looks stale

Run the generator again, then refresh the browser. The stable `example-digest.html` does not change; local output is written to `latest-digest.html`.
