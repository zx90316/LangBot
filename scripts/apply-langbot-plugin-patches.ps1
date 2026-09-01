# Apply local langbot-plugin Windows patches into .venv
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run --no-sync python scripts/apply-langbot-plugin-patches.py @args
exit $LASTEXITCODE
