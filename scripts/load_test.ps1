# Milestone 12 (OPS-01, ADR-0083): the bounded load test. Starts its own stack (throwaway env file, Compose project
# "loyalty-load", its own ports), loads the demo accounts, runs `scripts/load_test.py` through the stages declared in
# docs/load-profile.md, and tears the stack down. Your .env and your own stack are never touched. Mock customer API
# and mock AI: costs nothing. Local laptop: not production capacity.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\load_test.ps1 [-Keep] [-Stages ...]
param([switch]$Keep, [string]$Stages = "baseline:2:1:120,x4:8:2:120,x10:20:4:120")
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$project = "loyalty-load"
$envFile = Join-Path $env:TEMP "loyalty-load.env"
if (Test-Path $envFile) { Remove-Item $envFile }
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1 -Path $envFile | Out-Null
$dbPort = 45432; $mockPort = 48020; $appPort = 48010
# Rate limits are per signed-in user, and the virtual users share four demo accounts, so the per-user limit is lifted
# for the run (recorded in the report's ADR); everything else is the default stack.
Add-Content -Path $envFile -Encoding ascii -Value @"
DB_HOST_PORT=$dbPort
MOCK_API_HOST_PORT=$mockPort
APP_HOST_PORT=$appPort
MOCK_API_SIM_CLOCK=true
RATE_LIMIT_PER_MINUTE=100000
"@
$values = @{}
Get-Content $envFile | Where-Object { $_ -match "^([A-Z0-9_]+)=([^#\s]*)" } | ForEach-Object { $values[$Matches[1]] = $Matches[2] }
$compose = @("compose", "-p", $project, "--env-file", $envFile)
$code = 1
try {
    if (-not (Test-Path "seed_data\v1\members.jsonl")) { uv run python -m seed_data.generator generate }
    & docker @compose down -v --remove-orphans 2>$null | Out-Null
    & docker @compose up --build -d --wait
    if ($LASTEXITCODE -ne 0) { & docker @compose ps; throw "the stack didn't become healthy" }
    & docker @compose exec -T app python -m app.seed --dataset demo
    $env:LOAD_APP_URL = "http://127.0.0.1:$appPort"
    $env:LOAD_DEMO_PASSWORD = $values["DEMO_USER_PASSWORD"]
    $env:LOAD_DATABASE_URL = "postgresql+psycopg://loyalty_app:$($values['APP_DB_PASSWORD'])@127.0.0.1:$dbPort/loyalty"
    & docker stats --no-stream --format "{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}" | Select-String $project
    uv run python scripts/load_test.py --stages $Stages
    $code = $LASTEXITCODE
    & docker stats --no-stream --format "{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}" | Select-String $project
} finally {
    Remove-Item Env:LOAD_APP_URL, Env:LOAD_DEMO_PASSWORD, Env:LOAD_DATABASE_URL -ErrorAction SilentlyContinue
    if (-not $Keep) {
        & docker @compose down -v --remove-orphans 2>$null | Out-Null
        Remove-Item $envFile -ErrorAction SilentlyContinue
    } else { Write-Host "kept: docker compose -p $project --env-file $envFile down -v" }
}
if ($code -ne 0) { Write-Host "load test FAILED to run"; exit 1 }
Write-Host "load test finished; report in performance\reports"
exit 0
