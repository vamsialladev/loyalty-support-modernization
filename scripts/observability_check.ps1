# Milestone 12 (OPS-04, ADR-0080): the observability profile end to end. Starts the stack with `--profile
# observability` and the app, worker and mock API exporting to it; makes some traffic; then checks that the traces,
# the gauges and the HTTP metrics reached Prometheus and Tempo, and that Grafana loaded the dashboards and the alert
# rules. Throwaway env file, its own Compose project ("loyalty-obs-check") and ports, torn down after: your .env and
# your own stack are never touched. Costs nothing: local images only.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\observability_check.ps1 [-Keep]
param([switch]$Keep)
# Docker writes progress to stderr; PowerShell 5.1 would turn that into errors under "Stop". Exit codes are checked.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$project = "loyalty-obs-check"
$envFile = Join-Path $env:TEMP "loyalty-obs-check.env"
if (Test-Path $envFile) { Remove-Item $envFile }
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1 -Path $envFile | Out-Null
$dbPort = 35432; $mockPort = 38020; $appPort = 38010; $grafanaPort = 33000; $promPort = 39090; $tempoPort = 33200
Add-Content -Path $envFile -Encoding ascii -Value @"
DB_HOST_PORT=$dbPort
MOCK_API_HOST_PORT=$mockPort
APP_HOST_PORT=$appPort
GRAFANA_HOST_PORT=$grafanaPort
PROMETHEUS_HOST_PORT=$promPort
TEMPO_HOST_PORT=$tempoPort
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-lgtm:4318
OTEL_METRIC_EXPORT_INTERVAL=5000
"@
$values = @{}
Get-Content $envFile | Where-Object { $_ -match "^([A-Z0-9_]+)=([^#\s]*)" } | ForEach-Object { $values[$Matches[1]] = $Matches[2] }
$compose = @("compose", "-p", $project, "--env-file", $envFile, "--profile", "observability")
$code = 1
try {
    if (-not (Test-Path "seed_data\v1\members.jsonl")) { uv run python -m seed_data.generator generate }
    & docker @compose down -v --remove-orphans 2>$null | Out-Null
    & docker @compose up --build -d --wait
    if ($LASTEXITCODE -ne 0) {
        & docker @compose ps
        throw "the observability stack didn't become healthy"
    }
    & docker @compose exec -T app python -m app.seed --dataset demo
    $env:OBS_APP_URL = "http://127.0.0.1:$appPort"
    $env:OBS_GRAFANA_URL = "http://127.0.0.1:$grafanaPort"
    $env:OBS_PROMETHEUS_URL = "http://127.0.0.1:$promPort"
    $env:OBS_TEMPO_URL = "http://127.0.0.1:$tempoPort"
    $env:OBS_DATABASE_URL = "postgresql+psycopg://loyalty_app:$($values['APP_DB_PASSWORD'])@127.0.0.1:$dbPort/loyalty"
    $env:OBS_DEMO_PASSWORD = $values["DEMO_USER_PASSWORD"]
    $env:OBS_LGTM_CONTAINER = "$project-otel-lgtm-1"
    uv run python scripts/observability_check.py
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:OBS_APP_URL, Env:OBS_GRAFANA_URL, Env:OBS_PROMETHEUS_URL, Env:OBS_TEMPO_URL, Env:OBS_DATABASE_URL, Env:OBS_DEMO_PASSWORD, Env:OBS_LGTM_CONTAINER -ErrorAction SilentlyContinue
    if (-not $Keep) {
        & docker @compose down -v --remove-orphans 2>$null | Out-Null
        Remove-Item $envFile -ErrorAction SilentlyContinue
    } else { Write-Host "kept: docker compose -p $project --env-file $envFile --profile observability down -v" }
}
if ($code -ne 0) { Write-Host "observability check FAILED"; exit 1 }
Write-Host "observability check passed."
exit 0
