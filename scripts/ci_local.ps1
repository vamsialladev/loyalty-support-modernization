# The CI pipeline, run on this machine: same steps, same pinned tools, no GitHub Actions minutes (Milestone 12,
# DEL-02, ADR-0076). Run it before every push; a pull request is opened only when it passes.
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\ci_local.ps1            # the jobs in .github/workflows/ci.yml
#   powershell -ExecutionPolicy Bypass -File scripts\ci_local.ps1 -Full      # + compose check (with browser) + labs check
#   powershell -ExecutionPolicy Bypass -File scripts\ci_local.ps1 -Skip checks   # re-run only the other jobs
# Jobs: checks (lint, format, types, tests with the coverage gate incl. browser tests, dependency audit),
# postgres (a CI-shaped Postgres in Docker, the shared setup script, `pytest -m postgres`), secrets (gitleaks over
# the full history). Needs Docker Desktop running and Chromium installed once (`uv run playwright install chromium`).
param([switch]$Full, [string[]]$Skip = @())
# `-File` passes "-Skip a,b" as one string, so split it here (found running `-Skip postgres,secrets`).
$Skip = @($Skip | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
# Docker writes progress to stderr; PowerShell 5.1 would turn that into errors under "Stop". Exit codes are checked.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$results = New-Object System.Collections.Generic.List[object]

function Step([string]$job, [string]$name, [scriptblock]$block) {
    Write-Host "== [$job] $name"
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $global:LASTEXITCODE = 0
    & $block
    $code = $LASTEXITCODE
    $watch.Stop()
    $results.Add([pscustomobject]@{ Job = $job; Step = $name; Result = $(if ($code -eq 0) { "pass" } else { "FAIL ($code)" }); Seconds = [int]$watch.Elapsed.TotalSeconds })
    if ($code -ne 0) { Write-Host "FAILED: [$job] $name" }
}

if ($Skip -notcontains "checks") {
    Step "checks" "uv sync --frozen" { uv sync --frozen }
    Step "checks" "ruff check" { uv run ruff check . }
    Step "checks" "ruff format --check" { uv run ruff format --check . }
    Step "checks" "mypy" { uv run mypy }
    Step "checks" "Chromium for the browser tests" { uv run playwright install chromium }
    Step "checks" "tests with the coverage gate (browser tests included)" { uv run pytest --cov --cov-report=term-missing -rs -p no:cacheprovider }
    Step "checks" "known vulnerabilities in the locked dependencies" {
        $req = Join-Path $env:TEMP "ci-local-requirements-audit.txt"
        uv export --frozen --no-hashes --no-emit-project --all-groups -o $req -q
        uvx pip-audit==2.10.1 -r $req --no-deps --disable-pip
        $code = $LASTEXITCODE
        Remove-Item $req -ErrorAction SilentlyContinue
        $global:LASTEXITCODE = $code
    }
}

if ($Skip -notcontains "postgres") {
    # The same shape as CI's service container: superuser mock_api, database mock_customer_api_test, throwaway password.
    $pgName = "loyalty-ci-local-pg"  # not $name: Step's own parameter would shadow it inside the blocks
    $port = Get-Random -Minimum 55500 -Maximum 55999
    $pw = "ci-only-throwaway"
    & docker rm -f $pgName 2>$null | Out-Null
    Step "postgres" "start a CI-shaped Postgres 16 on 127.0.0.1:$port" {
        & docker run -d --name $pgName -e POSTGRES_USER=mock_api -e "POSTGRES_PASSWORD=$pw" -e POSTGRES_DB=mock_customer_api_test `
            -p "127.0.0.1:${port}:5432" -v "${PWD}\scripts:/ci/scripts:ro" -v "${PWD}\infrastructure:/ci/infrastructure:ro" `
            --health-cmd "pg_isready -U mock_api -d mock_customer_api_test" --health-interval 3s --health-retries 40 postgres:16.15-alpine | Out-Null
        $ready = $false
        for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
            Start-Sleep -Seconds 2
            $ready = ((& docker inspect $pgName --format "{{.State.Health.Status}}" | Out-String).Trim() -eq "healthy")
        }
        $global:LASTEXITCODE = if ($ready) { 0 } else { 1 }
    }
    Step "postgres" "databases and roles (scripts/ci_postgres_setup.sh, shared with CI)" {
        & docker exec -e "CI_DB_PASSWORD=$pw" -e PGHOST_PORT=127.0.0.1:5432 -e SQL_DIR=/ci/infrastructure/postgres/sql $pgName sh /ci/scripts/ci_postgres_setup.sh
    }
    Step "postgres" "pytest -m postgres" {
        $env:TEST_MOCK_API_DATABASE_URL = "postgresql+psycopg://mock_api:${pw}@127.0.0.1:${port}/mock_customer_api_test"
        $env:TEST_APP_DATABASE_URL = "postgresql+psycopg://loyalty_app:${pw}@127.0.0.1:${port}/loyalty_test"
        $env:TEST_APP_OWNER_DATABASE_URL = "postgresql+psycopg://loyalty_owner:${pw}@127.0.0.1:${port}/loyalty_test"
        uv run pytest -m postgres -rs -p no:cacheprovider
        $code = $LASTEXITCODE
        Remove-Item Env:TEST_MOCK_API_DATABASE_URL, Env:TEST_APP_DATABASE_URL, Env:TEST_APP_OWNER_DATABASE_URL
        $global:LASTEXITCODE = $code
    }
    & docker rm -f $pgName 2>$null | Out-Null
}

if ($Skip -notcontains "secrets") {
    Step "secrets" "gitleaks over the full history (values redacted)" {
        & docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact --no-banner
    }
}

if ($Full) {
    Step "full" "compose check with the browser test" { powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 -Browser }
    Step "full" "labs profile check (one issuer, protocol services in containers)" { powershell -ExecutionPolicy Bypass -File scripts\labs_check.ps1 }
}

Write-Host ""
$results | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
$total = ($results | Measure-Object -Property Seconds -Sum).Sum
Write-Host ("Total: {0:N1} minutes on this machine (no Actions minutes used)" -f ($total / 60))
$failed = @($results | Where-Object { $_.Result -ne "pass" })
if ($failed.Count -gt 0) { Write-Host "local CI FAILED: $($failed.Count) step(s)"; exit 1 }
Write-Host "local CI passed."
exit 0
