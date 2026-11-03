# Fill only the MISSING local development values in an env file. Prints names only, never values.
# - Adds any variable the template has and the file lacks (empty, as in the template).
# - Generates random values for empty local-only secrets (database role passwords, local tokens).
# - Rewrites DATABASE_URL / MOCK_API_DATABASE_URL only if they still use the pre-Milestone-4 admin form.
# - Moves a definition above any line that uses it as ${NAME} (order matters when the file is read).
# - Never changes a value that is already set. Keeps a backup at <file>.bak (Git-ignored).
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1 -Path <scratch env file>
param(
    [string]$Path = ".env",
    [string]$Template = ".env.example"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$LocalSecrets = @("POSTGRES_PASSWORD", "APP_DB_PASSWORD", "MOCK_API_DB_PASSWORD", "MOCK_API_TOKEN", "APP_SECRET_KEY", "DEMO_USER_PASSWORD")
$OldUrls = @{
    "DATABASE_URL"          = 'postgresql+psycopg://loyalty:${POSTGRES_PASSWORD}@localhost:5432/loyalty'
    "MOCK_API_DATABASE_URL" = 'postgresql+psycopg://loyalty:${POSTGRES_PASSWORD}@localhost:5432/mock_customer_api'
}

function Get-Value([string]$line) {
    $rest = $line.Substring($line.IndexOf("=") + 1)
    if ($rest -match "^\s*#") { return "" }
    $hash = $rest.IndexOf(" #")
    if ($hash -ge 0) { $rest = $rest.Substring(0, $hash) }
    return $rest.Trim()
}

function New-Secret {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

$templateLines = Get-Content -LiteralPath $Template -Encoding UTF8
if (-not (Test-Path -LiteralPath $Path)) {
    $lines = [System.Collections.Generic.List[string]]::new()
    $templateLines | ForEach-Object { $lines.Add($_) }
    $created = $true
} else {
    $lines = [System.Collections.Generic.List[string]]::new()
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object { $lines.Add($_) }
    $created = $false
}

$keyPattern = "^([A-Z0-9_]+)="
$present = @{}
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match $keyPattern) { $present[$Matches[1]] = $i }
}

$added = @(); $generated = @(); $rewritten = @()
foreach ($tl in $templateLines) {
    if ($tl -match $keyPattern -and -not $present.ContainsKey($Matches[1])) {
        $lines.Add($tl); $present[$Matches[1]] = $lines.Count - 1; $added += $Matches[1]
    }
}
foreach ($name in $OldUrls.Keys) {
    if ($present.ContainsKey($name)) {
        $i = $present[$name]
        if ((Get-Value $lines[$i]) -eq $OldUrls[$name]) {
            $new = $templateLines | Where-Object { $_ -match "^$name=" } | Select-Object -First 1
            $lines[$i] = $new; $rewritten += $name
        }
    }
}
foreach ($name in $LocalSecrets) {
    $i = $present[$name]
    if ((Get-Value $lines[$i]) -eq "") {
        $lines[$i] = "$name=$(New-Secret)"; $generated += $name
    }
}

# python-dotenv and Docker Compose expand ${NAME} top to bottom: a variable used before its own line expands to
# a blank string. Move each definition above the first line that uses it (this also repairs files written by the
# earlier version of this script, which appended new keys after the URL lines that use them).
$moved = @()
for ($pass = 0; $pass -lt 50; $pass++) {
    $present = @{}
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $keyPattern) { $present[$Matches[1]] = $i }
    }
    $move = $null
    for ($i = 0; $i -lt $lines.Count -and $null -eq $move; $i++) {
        if ($lines[$i] -notmatch $keyPattern) { continue }
        foreach ($ref in [regex]::Matches((Get-Value $lines[$i]), '\$\{([A-Z0-9_]+)')) {
            $name = $ref.Groups[1].Value
            if ($present.ContainsKey($name) -and $present[$name] -gt $i) { $move = @($present[$name], $i, $name); break }
        }
    }
    if ($null -eq $move) { break }
    $line = $lines[$move[0]]
    $lines.RemoveAt($move[0]); $lines.Insert($move[1], $line)
    if ($moved -notcontains $move[2]) { $moved += $move[2] }
}

if (-not $created -and ($added.Count + $generated.Count + $rewritten.Count + $moved.Count) -gt 0) {
    Copy-Item -LiteralPath $Path -Destination "$Path.bak" -Force
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
$full = if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path (Get-Location) $Path }
[System.IO.File]::WriteAllText($full, (($lines -join "`n") + "`n"), $utf8)

Write-Host "Updated $Path (values are never printed):"
Write-Host "  added from template: $(if ($added) { $added -join ', ' } else { 'none' })"
Write-Host "  generated (were empty): $(if ($generated) { $generated -join ', ' } else { 'none' })"
Write-Host "  URL lines updated to the per-role form: $(if ($rewritten) { $rewritten -join ', ' } else { 'none' })"
Write-Host "  moved above the lines that use them: $(if ($moved) { $moved -join ', ' } else { 'none' })"
Write-Host "Values already set were left unchanged. Check with: uv run python -m app.preflight --profile portfolio"
