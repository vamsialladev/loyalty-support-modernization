# Configuration readiness without printing any value. Same as `make preflight PROFILE=...`.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1 -Profile live-model
param([string]$Profile = "portfolio")
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run python -m app.preflight --profile $Profile
exit $LASTEXITCODE
