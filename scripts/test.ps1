# Offline checks: lint, format, types, tests with coverage. Same as `make test`. No API key needed.
# Usage (from the repository root):  powershell -ExecutionPolicy Bypass -File scripts\test.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Step($name, [scriptblock]$command) {
    Write-Host "== $name"
    & $command
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $name"; exit $LASTEXITCODE }
}

Step "ruff check" { uv run ruff check . }
Step "ruff format --check" { uv run ruff format --check . }
Step "mypy" { uv run mypy }
Step "pytest" { uv run pytest --cov --cov-report=term-missing }
Write-Host "All offline checks passed."
