# Milestone 13, Phase 3: the pre-registered live runs (docs/m13-phase3-plan.md; CACHE-03).
#
# SPENDS REAL MONEY. Run it only after the owner's "go" (approved 2026-11-27: about $0.71 expected, $1.55 hard limit).
# Order: preflight, a 5-case smoke run of arm D on dev (stops unless the cache is read), then the held-out runs
# alternating A, D, A, D, A, D. Each run has its own --budget-usd; the runner also checks the ledger's overall cap
# before every call. Any refusal or failure stops the script; nothing is retried automatically.
#
#   powershell -ExecutionPolicy Bypass -File scripts\m13_phase3.ps1            # everything
#   powershell -ExecutionPolicy Bypass -File scripts\m13_phase3.ps1 -From m13-d-r2   # resume at a run
#
# Console output of every step is kept in benchmarks\reports\m13\run-logs\ (no secrets: case IDs, counts, costs).

param([string]$From = "")

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$logs = "benchmarks\reports\m13\run-logs"
New-Item -ItemType Directory -Force $logs | Out-Null

$runs = @(
    @{ Name = "m13-smoke-cache"; Arm = "c-live-cache"; Split = "dev"; Run = 1; Budget = "0.05"; Cases = "DV-001,DV-002,DV-003,DV-004,DV-005" },
    @{ Name = "m13-a-r1"; Arm = "c-live"; Split = "heldout"; Run = 1; Budget = "0.25"; Cases = "" },
    @{ Name = "m13-d-r1"; Arm = "c-live-cache"; Split = "heldout"; Run = 1; Budget = "0.25"; Cases = "" },
    @{ Name = "m13-a-r2"; Arm = "c-live"; Split = "heldout"; Run = 2; Budget = "0.25"; Cases = "" },
    @{ Name = "m13-d-r2"; Arm = "c-live-cache"; Split = "heldout"; Run = 2; Budget = "0.25"; Cases = "" },
    @{ Name = "m13-a-r3"; Arm = "c-live"; Split = "heldout"; Run = 3; Budget = "0.25"; Cases = "" },
    @{ Name = "m13-d-r3"; Arm = "c-live-cache"; Split = "heldout"; Run = 3; Budget = "0.25"; Cases = "" }
)

function Invoke-Logged([string]$Log, [string[]]$Command) {
    Write-Host "> $($Command -join ' ')"
    # Windows PowerShell 5.1 turns every stderr line of a native command into an error record, and with "Stop" the
    # first one ends the script. On 2026-11-27 that killed m13-d-r2 at about 60 of 80 cases, on a worker log line
    # ("job requeued ... OperationalError") the runner itself had recovered from. So the exit code decides, not stderr.
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command[0] $Command[1..($Command.Length - 1)] 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $Log
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $saved
    }
    if ($code -ne 0) { throw "stopped: exit $code (full output in $Log)" }
}

Invoke-Logged "$logs\preflight.log" @("uv", "run", "python", "-m", "app.preflight", "--profile", "live-model")
if (-not (Select-String -Path "$logs\preflight.log" -Pattern "Result: READY" -Quiet)) { throw "preflight isn't READY" }

$started = [string]::IsNullOrEmpty($From)
foreach ($r in $runs) {
    if (-not $started) { if ($r.Name -eq $From) { $started = $true } else { continue } }
    $command = @("uv", "run", "python", "-m", "evaluations.run", "--arm", $r.Arm, "--split", $r.Split, "--name", $r.Name,
        "--run-number", "$($r.Run)", "--budget-usd", $r.Budget)
    if ($r.Split -eq "heldout") { $command += "--confirm-frozen" }
    if ($r.Cases) { $command += @("--cases", $r.Cases) }
    Invoke-Logged "$logs\$($r.Name).log" $command
    if (Select-String -Path "$logs\$($r.Name).log" -Pattern "REFUSED|interrupted" -Quiet) { throw "$($r.Name) was refused or interrupted" }
    if ($r.Name -eq "m13-smoke-cache") {
        # Before spending on the full runs: the smoke run must have read the cache at least once.
        Invoke-Logged "$logs\smoke-check.log" @("uv", "run", "python", "-m", "evaluations.m13_results", "--smoke", $r.Name)
    }
}
Invoke-Logged "$logs\results.log" @("uv", "run", "python", "-m", "evaluations.m13_results")
Write-Host "Done. Now set .env back to mock (the owner's rule, 2026-11-10) and commit benchmarks\results\live\m13-* and benchmarks\reports\m13\."
