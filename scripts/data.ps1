# Synthetic data commands. Same as the make targets data / data-reset / data-clean / data-verify / discovery.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
param(
    [ValidateSet("generate", "reset", "clean", "verify", "discovery")]
    [string]$Action = "generate",
    [int]$Seed = 20261102,
    [double]$Scale = 1.0
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

switch ($Action) {
    "generate" { uv run python -m seed_data.generator generate --seed $Seed --scale $Scale }
    "reset" {
        uv run python -m seed_data.generator clean
        if ($LASTEXITCODE -eq 0) { uv run python -m seed_data.generator generate --seed $Seed --scale $Scale }
    }
    "clean" { uv run python -m seed_data.generator clean }
    "verify" { uv run python -m seed_data.generator verify --seed $Seed --scale $Scale }
    "discovery" { uv run python -m evaluations.discovery_analysis }
}
exit $LASTEXITCODE
