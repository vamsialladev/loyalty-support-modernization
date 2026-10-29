# Appendix C (Milestones 3-4): from an empty volume, `docker compose up`, migrate and seed must succeed; then the
# live checks, the image contents check and the real-Postgres tests run. Uses a throwaway env file and a separate
# Compose project ("loyalty-check"), so your .env and your own database volume are never touched.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 [-Keep]
param([switch]$Keep)
# Docker writes progress to stderr; PowerShell 5.1 would turn that into errors under "Stop". Exit codes are checked.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$project = "loyalty-check"
$envFile = Join-Path $env:TEMP "loyalty-compose-check.env"
$failed = @()

function Step([string]$name, [scriptblock]$block) {
    Write-Host "== $name"
    & $block
    if ($LASTEXITCODE -ne 0) { $script:failed += $name; Write-Host "FAILED: $name" }
}

if (Test-Path $envFile) { Remove-Item $envFile }
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1 -Path $envFile | Out-Null
Add-Content -Path $envFile -Value "MOCK_API_FAULTS=true`nMOCK_API_SIM_CLOCK=true" -Encoding ascii
$values = @{}
Get-Content $envFile | Where-Object { $_ -match "^([A-Z0-9_]+)=([^#\s]*)" } | ForEach-Object { $values[$Matches[1]] = $Matches[2] }

$compose = @("compose", "-p", $project, "--env-file", $envFile)
Step "clean start (remove any old check volume)" { & docker @compose down -v --remove-orphans; $global:LASTEXITCODE = 0 }
if (-not (Test-Path "seed_data\v1\members.jsonl")) { Step "generate seed_data/v1" { uv run python -m seed_data.generator generate } }
Step "docker compose up --build (wait for health)" { & docker @compose up --build -d --wait }
Step "migrate and seed (python -m app.seed --dataset demo)" { & docker @compose exec -T app python -m app.seed --dataset demo }
Step "app /readyz is ready" {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8010/readyz" -TimeoutSec 10
    Write-Host ($r | ConvertTo-Json -Compress)
    $global:LASTEXITCODE = if ($r.status -eq "ready") { 0 } else { 1 }
}
Step "live adapter checks against the running mock API" { uv run python scripts/live_smoke.py --env-file $envFile }
foreach ($image in @("$project-mock-api", "$project-app")) {
    Step "no labels, generator or data inside $image" {
        # No double quotes inside: PowerShell 5.1 strips them when passing arguments to native programs.
        & docker run --rm --entrypoint sh $image -c 'for d in benchmarks evaluations seed_data docs tests; do test ! -e /srv/$d || exit 1; done; test -z $(find / -xdev -name *.jsonl 2>/dev/null) && test $(id -u) != 0'
    }
}
Step "real-Postgres integration tests" {
    $env:TEST_MOCK_API_DATABASE_URL = "postgresql+psycopg://mock_api:$($values['MOCK_API_DB_PASSWORD'])@127.0.0.1:5432/mock_customer_api_test"
    uv run pytest -m postgres -q -p no:cacheprovider
    Remove-Item Env:TEST_MOCK_API_DATABASE_URL
}
Step "app role cannot connect to the mock database" {
    $out = & docker @compose exec -T -e "PGPASSWORD=$($values['APP_DB_PASSWORD'])" db psql -h 127.0.0.1 -U loyalty_app -d mock_customer_api -c "select 1" 2>&1
    $global:LASTEXITCODE = if ("$out" -match "permission denied|not permitted|FATAL") { 0 } else { 1 }
}

if (-not $Keep) { & docker @compose down -v --remove-orphans | Out-Null }
Remove-Item $envFile -ErrorAction SilentlyContinue
if ($failed.Count -gt 0) { Write-Host "compose check FAILED: $($failed -join '; ')"; exit 1 }
Write-Host "compose check passed."
exit 0
