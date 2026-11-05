# The exact upgrade an owner runs: a volume built by the real Milestone 5 code, then this checkout's stack.ps1 -Action up.
# Its own Compose project, ports and throwaway env file, so your .env and your own volume are never touched.
# Faking the old state isn't enough: a volume built by later code held a CONNECT right the real one didn't (ADR-0058).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\upgrade_check_m5.ps1
# Docker writes progress to stderr; PowerShell 5.1 would turn that into errors under "Stop". Exit codes are checked.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$lastMilestone5Commit = "68deba1"
$project = "loyalty-m5-upgrade"
$checkout = Join-Path $env:TEMP "loyalty-m5-checkout"
$envFile = Join-Path $env:TEMP "loyalty-m5-upgrade.env"
$failed = @()

function Step([string]$name, [scriptblock]$block) {
    Write-Host "== $name"
    & $block
    if ($LASTEXITCODE -ne 0) { $script:failed += $name; Write-Host "FAILED: $name" }
}

function Clean-Up {
    & docker compose -p $project --env-file $envFile down -v --remove-orphans 2>&1 | Out-Null
    & git worktree remove --force $checkout 2>&1 | Out-Null
    & git worktree prune
    Remove-Item $envFile -ErrorAction SilentlyContinue
}

if (Test-Path $envFile) { Remove-Item $envFile }
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1 -Path $envFile | Out-Null
$dbPort = 25432; $mockPort = 28020; $appPort = 28010
Add-Content -Path $envFile -Value "DB_HOST_PORT=$dbPort`nMOCK_API_HOST_PORT=$mockPort`nAPP_HOST_PORT=$appPort" -Encoding ascii
$values = @{}
Get-Content $envFile | Where-Object { $_ -match "^([A-Z0-9_]+)=([^#\s]*)" } | ForEach-Object { $values[$Matches[1]] = $Matches[2] }
& docker compose -p $project --env-file $envFile down -v --remove-orphans 2>&1 | Out-Null
& git worktree remove --force $checkout 2>&1 | Out-Null
& git worktree prune

if (-not (Test-Path "seed_data\v1\members.jsonl")) { uv run python -m seed_data.generator generate }
$old = @("compose", "-f", "$checkout\docker-compose.yml", "-p", $project, "--env-file", $envFile)
$new = @("compose", "-p", $project, "--env-file", $envFile)
$stack = @("-ExecutionPolicy", "Bypass", "-File", "scripts\stack.ps1", "-EnvFile", $envFile, "-Project", $project)

function Sql([string]$query) {
    (& docker @new exec -T db psql -U $values['POSTGRES_USER'] -d loyalty -tAc $query | Out-String).Trim()
}
function AppRole([string]$query) {
    (& docker @new exec -T -e "PGPASSWORD=$($values['APP_DB_PASSWORD'])" db psql -h 127.0.0.1 -U loyalty_app -d loyalty -tAc $query 2>&1 | Out-String).Trim()
}

Step "Milestone 5: the real code at $lastMilestone5Commit builds the volume" {
    & git worktree add --detach $checkout $lastMilestone5Commit
    Copy-Item -Recurse "seed_data\v1" "$checkout\seed_data\v1"
    & docker @old up --build -d --wait
}
Step "Milestone 5: its own seed runs" { & docker @old exec -T app python -m app.seed --dataset demo }
Step "Milestone 5: the volume holds a case and an event, as yours does" {
    $case = "INSERT INTO cases (reference, arm, customer_id, queue, status, created_by, received_at_utc, version, created_at_utc, updated_at_utc) VALUES ('A-000001', 'A', 'hg-demo', 'points', 'Resolved', 'agent.ana', '2026-01-06T00:00:00Z', 1, '2026-01-06T00:00:00Z', '2026-01-06T00:00:00Z')"
    $event = "INSERT INTO case_events (case_id, step, actor, actor_kind, action, detail, at_utc) VALUES (1, 1, 'agent.ana', 'human', 'case_closed', '{}', '2026-01-06T00:00:00Z')"
    Sql $case | Out-Null
    Sql $event | Out-Null
    $acl = Sql "select datacl from pg_database where datname = 'loyalty'"
    $owner = Sql "select pg_get_userbyid(datdba) from pg_database where datname = 'loyalty'"
    Write-Host "before the upgrade: database owner $owner, ACL $acl"
    $global:LASTEXITCODE = if ($owner -eq "loyalty_app" -and (Sql "select count(*) from case_events") -eq "1") { 0 } else { 1 }
}
& docker @old stop app mock-api 2>&1 | Out-Null

Step "Upgrade: this checkout's stack.ps1 -Action up reports ready" { powershell @stack -Action up }
Step "After: /readyz says ready" {
    $body = try { Invoke-RestMethod -Uri "http://127.0.0.1:$appPort/readyz" -TimeoutSec 15 } catch { $_.ErrorDetails.Message | ConvertFrom-Json }
    Write-Host ($body | ConvertTo-Json -Compress)
    $global:LASTEXITCODE = if ($body.status -eq "ready") { 0 } else { 1 }
}
Step "After: the app role really connects, and the case is still there" {
    $count = AppRole "select count(*) from cases"
    Write-Host "app role sees cases: $count"
    $global:LASTEXITCODE = if ($count -eq "1") { 0 } else { 1 }
}
Step "After: the owner role owns the tables, and audit history is append-only for the app role" {
    $owner = Sql "select tableowner from pg_tables where tablename = 'cases'"
    $dbOwner = Sql "select pg_get_userbyid(datdba) from pg_database where datname = 'loyalty'"
    $refused = AppRole "update case_events set actor = 'someone-else'"
    Write-Host "table owner $owner, database owner $dbOwner; app role updating case_events: $refused"
    $global:LASTEXITCODE = if ($owner -eq "loyalty_owner" -and $dbOwner -eq "loyalty_owner" -and "$refused" -match "permission denied") { 0 } else { 1 }
}
Step "After: the schema is at this checkout's head" {
    $head = (Get-ChildItem migrations\versions -Filter *.py | Sort-Object Name | Select-Object -Last 1).Name.Substring(0, 4)
    $version = Sql "select version_num from alembic_version"
    Write-Host "revision $version, head $head"
    $global:LASTEXITCODE = if ($version -eq $head) { 0 } else { 1 }
}
Step "After: the seed loads the policies and the new accounts, and the old case survives" {
    powershell @stack -Action seed
    $code = $LASTEXITCODE
    $users, $versions, $cases = (Sql "select count(*) from users"), (Sql "select count(*) from policy_versions"), (Sql "select count(*) from cases")
    Write-Host "accounts $users, policy versions $versions, cases $cases"
    $global:LASTEXITCODE = if ($code -eq 0 -and $users -eq "6" -and [int]$versions -ge 4 -and $cases -eq "1") { 0 } else { 1 }
}
# A quiet log isn't proof: a tail can scroll a failure away. A job the worker must claim is. No handler knows this kind, so
# a worker that really claimed it marks it dead with `unknown_kind`; a worker that can't reach the database leaves it queued.
Step "After: the worker really claims a job, its whole log has no failed claim, and it reports healthy" {
    $probe = "INSERT INTO jobs (kind, dedupe_key, payload, status, attempts, max_attempts, run_after_utc, created_at_utc) VALUES ('upgrade_check_probe', 'upgrade_check_probe:system', '{}', 'queued', 0, 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')"
    Sql $probe | Out-Null
    $claimed = ""
    for ($i = 0; $i -lt 60 -and $claimed -ne "dead|unknown_kind"; $i++) {
        Start-Sleep -Seconds 2
        $claimed = Sql "select status || '|' || coalesce(last_error, '') from jobs where kind = 'upgrade_check_probe'"
    }
    $health = (& docker inspect "$project-worker-1" --format "{{.State.Health.Status}}" | Out-String).Trim()
    $failures = (& docker logs "$project-worker-1" 2>&1 | Select-String -SimpleMatch "claim failed" | Measure-Object).Count
    Write-Host "worker probe job: $claimed; health $health; failed claims in its whole log: $failures"
    $global:LASTEXITCODE = if ($claimed -eq "dead|unknown_kind" -and $health -eq "healthy" -and $failures -eq 0) { 0 } else { 1 }
}
Step "Safe to repeat: stack.ps1 -Action up again on the upgraded volume" {
    powershell @stack -Action up
    $code = $LASTEXITCODE
    $count = AppRole "select count(*) from cases"
    $refused = AppRole "update case_events set actor = 'someone-else'"
    $global:LASTEXITCODE = if ($code -eq 0 -and $count -eq "1" -and "$refused" -match "permission denied") { 0 } else { 1 }
}

Clean-Up
if ($failed.Count -gt 0) { Write-Host "M5 upgrade check FAILED: $($failed -join '; ')"; exit 1 }
Write-Host "M5 upgrade check passed."
exit 0
