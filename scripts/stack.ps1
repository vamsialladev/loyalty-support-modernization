# Local stack commands. Same as the make targets up / down / migrate / seed / reset-demo / demo-cases / clean / logs.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
# -EnvFile and -Project let a check run against throwaway values without touching your .env or your volume.
param(
    [ValidateSet("up", "down", "migrate", "seed", "reset-demo", "demo-cases", "clean", "logs", "status", "verify-roles")]
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

# Refuse to run when Compose would expand a variable to a blank string (it only warns). The warning names the
# variable, never its value. Typical cause: a .env line uses ${NAME} above the line that defines NAME.
$warnings = (& docker @compose config --quiet 2>&1 | Out-String)
if ($warnings -match "variable is not set") {
    $names = [regex]::Matches($warnings, 'The \\?"([A-Z0-9_]+)\\?" variable is not set') | ForEach-Object { $_.Groups[1].Value }
    throw "Compose would use a blank value for: $(($names | Select-Object -Unique) -join ', '). Run scripts\update-local-env.ps1, then: uv run python -m app.preflight"
}

switch ($Action) {
    "up" {
        if (-not (Test-Path "seed_data\v1\members.jsonl")) {
            Write-Host "seed_data\v1 is missing: generating it first"
            uv run python -m seed_data.generator generate
        }
        # The app and mock API containers migrate their own databases before they start serving. If the stack doesn't
        # come up, or the app database still isn't current, say why instead of only "unhealthy" (ADR-0052).
        & docker @compose up --build -d --wait
        $upCode = $LASTEXITCODE
        uv run python scripts/stack_diagnose.py --project $Project --env-file $EnvFile
        $diagnosis = $LASTEXITCODE
        if ($diagnosis -eq 3) {
            Write-Host "Migrating the app database now."
            Invoke-Compose @("exec", "-T", "app", "alembic", "upgrade", "head")
            uv run python scripts/stack_diagnose.py --project $Project --env-file $EnvFile
            $diagnosis = $LASTEXITCODE
        }
        if ($upCode -ne 0 -or $diagnosis -ne 0) {
            throw "The stack is not ready; the cause is above. Full logs: scripts\stack.ps1 -Action logs"
        }
    }
    "down" { Invoke-Compose @("down") }
    "migrate" { Invoke-Compose @("exec", "-T", "app", "alembic", "upgrade", "head") }
    "seed" { Invoke-Compose @("exec", "-T", "app", "python", "-m", "app.seed", "--dataset", "demo") }
    "reset-demo" { Invoke-Compose @("exec", "-T", "app", "python", "-m", "app.seed", "--dataset", "demo", "--reset") }
    "demo-cases" {
        # Puts 20 dev-split requests in the console's queue (request text only, never labels; ADR-0048). Runs on the
        # host because the images carry no benchmarks/ folder.
        uv run python -m benchmarks.intake --split dev --limit 20 --env-file $EnvFile
        if ($LASTEXITCODE -ne 0) { throw "loading demo cases failed ($LASTEXITCODE)" }
    }
    "clean" { Invoke-Compose @("down", "-v", "--remove-orphans") }
    "logs" { Invoke-Compose @("logs", "--tail", "100") }
    "status" { Invoke-Compose @("ps") }
    "verify-roles" {
        # Each role has a stored password, and a blank password is refused (tests/test_db_roles_postgres.py).
        $env:TEST_DB_ROLES_CONTAINER = "$Project-db-1"
        uv run pytest tests/test_db_roles_postgres.py -m postgres -v -p no:cacheprovider
        $code = $LASTEXITCODE
        Remove-Item Env:TEST_DB_ROLES_CONTAINER
        if ($code -ne 0) { throw "role checks failed ($code)" }
    }
}
exit 0
