# Local stack commands. Same as the make targets up / down / migrate / seed / reset-demo / clean / logs.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
# -EnvFile and -Project let a check run against throwaway values without touching your .env or your volume.
param(
    [ValidateSet("up", "down", "migrate", "seed", "reset-demo", "clean", "logs", "status")]
    [string]$Action = "up",
    [string]$EnvFile = ".env",
    [string]$Project = "loyalty"
)
# Docker writes progress to stderr; PowerShell 5.1 would turn that into errors under "Stop". Exit codes are checked.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$compose = @("compose", "-p", $Project, "--env-file", $EnvFile)

function Invoke-Compose([string[]]$Arguments) {
    & docker @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($Arguments -join ' ') failed ($LASTEXITCODE)" }
}

switch ($Action) {
    "up" {
        if (-not (Test-Path "seed_data\v1\members.jsonl")) {
            Write-Host "seed_data\v1 is missing: generating it first"
            uv run python -m seed_data.generator generate
        }
        Invoke-Compose @("up", "--build", "-d", "--wait")
    }
    "down" { Invoke-Compose @("down") }
    "migrate" { Invoke-Compose @("exec", "-T", "app", "alembic", "upgrade", "head") }
    "seed" { Invoke-Compose @("exec", "-T", "app", "python", "-m", "app.seed", "--dataset", "demo") }
    "reset-demo" { Invoke-Compose @("exec", "-T", "app", "python", "-m", "app.seed", "--dataset", "demo", "--reset") }
    "clean" { Invoke-Compose @("down", "-v", "--remove-orphans") }
    "logs" { Invoke-Compose @("logs", "--tail", "100") }
    "status" { Invoke-Compose @("ps") }
}
exit 0
