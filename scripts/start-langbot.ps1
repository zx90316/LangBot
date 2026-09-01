# Start LangBot on Windows with local langbot-plugin patches applied.
param(
    [switch]$Sync
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if ($Sync) {
    uv sync --dev
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

uv run --no-sync python scripts/apply-langbot-plugin-patches.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:PYTHONIOENCODING = "utf-8"
$env:BOX__ENABLED = "false"

uv run --no-sync main.py
