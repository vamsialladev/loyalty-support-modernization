# The OIDC profile against a real local Keycloak (Appendix C, M9). Costs nothing: it pulls a free image, once, and tears it all down.
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File scripts\oidc_check.ps1
$ErrorActionPreference = "Stop"
$project = "loyalty-oidc-check"
$port = Get-Random -Minimum 18000 -Maximum 18999
$envFile = Join-Path $env:TEMP "loyalty-oidc-check.env"
$bytes = New-Object byte[] 24
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$password = [Convert]::ToBase64String($bytes).Replace("/", "x").Replace("+", "y").Replace("=", "z")
Set-Content -Path $envFile -Value "KEYCLOAK_ADMIN_PASSWORD=$password`nKEYCLOAK_HOST_PORT=$port" -Encoding ascii
$compose = @("compose", "-p", $project, "-f", "docker-compose.oidc.yml", "--env-file", $envFile)
try {
    & docker @compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw "Keycloak didn't become healthy" }
    $env:KEYCLOAK_URL = "http://127.0.0.1:$port"
    $env:KEYCLOAK_ADMIN_PASSWORD = $password
    uv run python scripts/oidc_check.py
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:KEYCLOAK_URL, Env:KEYCLOAK_ADMIN_PASSWORD -ErrorAction SilentlyContinue
    & docker @compose down -v | Out-Null
    Remove-Item $envFile -ErrorAction SilentlyContinue
}
if ($code -ne 0) { Write-Host "oidc check FAILED"; exit 1 }
Write-Host "oidc check passed."
