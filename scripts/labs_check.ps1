# Milestone 12 (TD-52, TD-53): the protocol services in Compose (`--profile labs`), one public issuer for host and
# containers. Throwaway env file, its own Compose project ("loyalty-labs-check") and ports, torn down after: your .env
# and your own stack are never touched. Costs nothing: local images only.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\labs_check.ps1 [-Keep]
param([switch]$Keep)
# Docker writes progress to stderr; PowerShell 5.1 would turn that into errors under "Stop". Exit codes are checked.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$project = "loyalty-labs-check"
$envFile = Join-Path $env:TEMP "loyalty-labs-check.env"
if (Test-Path $envFile) { Remove-Item $envFile }
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1 -Path $envFile | Out-Null
$bytes = New-Object byte[] 24
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$kcPassword = [Convert]::ToBase64String($bytes).Replace("/", "x").Replace("+", "y").Replace("=", "z")
$dbPort = 25432; $mockPort = 28020; $appPort = 28010; $kcPort = 28090; $mcpPort = 28030; $a2aPort = 28041
Add-Content -Path $envFile -Encoding ascii -Value @"
KEYCLOAK_ADMIN_PASSWORD=$kcPassword
DB_HOST_PORT=$dbPort
MOCK_API_HOST_PORT=$mockPort
APP_HOST_PORT=$appPort
KEYCLOAK_HOST_PORT=$kcPort
MCP_HOST_PORT=$mcpPort
A2A_HOST_PORT=$a2aPort
"@
$compose = @("compose", "-p", $project, "--env-file", $envFile, "--profile", "labs")
$code = 1
try {
    if (-not (Test-Path "seed_data\v1\members.jsonl")) { uv run python -m seed_data.generator generate }
    & docker @compose down -v --remove-orphans 2>$null | Out-Null
    & docker @compose up --build -d --wait
    if ($LASTEXITCODE -ne 0) {
        & docker @compose ps
        throw "the labs stack didn't become healthy"
    }
    $env:KEYCLOAK_URL = "http://127.0.0.1:$kcPort"
    $env:KEYCLOAK_ADMIN_PASSWORD = $kcPassword
    $env:LABS_MCP_URL = "http://127.0.0.1:$mcpPort/mcp"
    $env:LABS_A2A_URL = "http://127.0.0.1:$a2aPort"
    $env:LABS_MCP_CONTAINER = "$project-mcp-1"
    uv run python scripts/labs_check.py
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:KEYCLOAK_URL, Env:KEYCLOAK_ADMIN_PASSWORD, Env:LABS_MCP_URL, Env:LABS_A2A_URL, Env:LABS_MCP_CONTAINER -ErrorAction SilentlyContinue
    if (-not $Keep) { & docker @compose down -v --remove-orphans 2>$null | Out-Null }
    Remove-Item $envFile -ErrorAction SilentlyContinue
}
if ($code -ne 0) { Write-Host "labs check FAILED"; exit 1 }
Write-Host "labs check passed."
exit 0
