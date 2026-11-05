# Appendix C (Milestones 3-4): from an empty volume, `docker compose up`, migrate and seed must succeed; then the
# live checks, the image contents check and the real-Postgres tests run. Uses a throwaway env file and a separate
# Compose project ("loyalty-check"), so your .env and your own database volume are never touched.
# -Browser (Milestone 5) also runs the Playwright end-to-end test of legacy arm A against the running stack.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 [-Keep] [-Browser]
param([switch]$Keep, [switch]$Browser)
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
# Its own host ports, so the check runs next to your own stack (which keeps 5432 / 8020 / 8010).
$dbPort = 15432; $mockPort = 18020; $appPort = 18010
Add-Content -Path $envFile -Value "MOCK_API_FAULTS=true`nMOCK_API_SIM_CLOCK=true`nDB_HOST_PORT=$dbPort`nMOCK_API_HOST_PORT=$mockPort`nAPP_HOST_PORT=$appPort" -Encoding ascii
$values = @{}
Get-Content $envFile | Where-Object { $_ -match "^([A-Z0-9_]+)=([^#\s]*)" } | ForEach-Object { $values[$Matches[1]] = $Matches[2] }

$compose = @("compose", "-p", $project, "--env-file", $envFile)
Step "clean start (remove any old check volume)" { & docker @compose down -v --remove-orphans; $global:LASTEXITCODE = 0 }
if (-not (Test-Path "seed_data\v1\members.jsonl")) { Step "generate seed_data/v1" { uv run python -m seed_data.generator generate } }
Step "docker compose up --build (wait for health)" { & docker @compose up --build -d --wait }
Step "migrate and seed (python -m app.seed --dataset demo)" { & docker @compose exec -T app python -m app.seed --dataset demo }
Step "app /readyz is ready" {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$appPort/readyz" -TimeoutSec 10
    Write-Host ($r | ConvertTo-Json -Compress)
    $global:LASTEXITCODE = if ($r.status -eq "ready") { 0 } else { 1 }
}
Step "live adapter checks against the running mock API" { uv run python scripts/live_smoke.py --env-file $envFile --mock-url "http://127.0.0.1:$mockPort" }
foreach ($image in @("$project-mock-api", "$project-app")) {
    Step "no labels, generator or data inside $image" {
        # No double quotes inside: PowerShell 5.1 strips them when passing arguments to native programs.
        & docker run --rm --entrypoint sh $image -c 'for d in benchmarks evaluations seed_data docs tests; do test ! -e /srv/$d || exit 1; done; test -z $(find / -xdev -name *.jsonl 2>/dev/null) && test $(id -u) != 0'
    }
}
Step "real-Postgres integration tests (incl. stored role passwords, blank password refused)" {
    $env:TEST_MOCK_API_DATABASE_URL = "postgresql+psycopg://mock_api:$($values['MOCK_API_DB_PASSWORD'])@127.0.0.1:$dbPort/mock_customer_api_test"
    $env:TEST_APP_DATABASE_URL = "postgresql+psycopg://loyalty_app:$($values['APP_DB_PASSWORD'])@127.0.0.1:$dbPort/loyalty_test"
    $env:TEST_APP_OWNER_DATABASE_URL = "postgresql+psycopg://loyalty_owner:$($values['APP_OWNER_DB_PASSWORD'])@127.0.0.1:$dbPort/loyalty_test"
    $env:TEST_DB_ROLES_CONTAINER = "$project-db-1"
    uv run pytest -m postgres -p no:cacheprovider -rs
    Remove-Item Env:TEST_MOCK_API_DATABASE_URL, Env:TEST_APP_DATABASE_URL, Env:TEST_APP_OWNER_DATABASE_URL, Env:TEST_DB_ROLES_CONTAINER
}
if ($Browser) {
    Step "Playwright: legacy arm A end to end in the browser, against the stack (real Postgres)" {
        $env:E2E_BASE_URL = "http://127.0.0.1:$appPort"
        $env:E2E_MOCK_API_URL = "http://127.0.0.1:$mockPort"
        $env:E2E_DATABASE_URL = "postgresql+psycopg://loyalty_app:$($values['APP_DB_PASSWORD'])@127.0.0.1:$dbPort/loyalty"
        $env:E2E_MOCK_API_TOKEN = $values['MOCK_API_TOKEN']
        $env:E2E_DEMO_PASSWORD = $values['DEMO_USER_PASSWORD']
        uv run pytest tests/browser -m browser -p no:cacheprovider -rA --tb=short
        Remove-Item Env:E2E_BASE_URL, Env:E2E_MOCK_API_URL, Env:E2E_DATABASE_URL, Env:E2E_MOCK_API_TOKEN, Env:E2E_DEMO_PASSWORD
    }
}
Step "worker: SIGTERM stops it cleanly, with exit code 0, and it comes back" {
    & docker @compose stop worker
    $exit = (& docker inspect "$project-worker-1" --format "{{.State.ExitCode}}" | Out-String).Trim()
    Write-Host "worker exit code after SIGTERM: $exit"
    & docker @compose up -d --wait worker
    $code = $LASTEXITCODE
    $global:LASTEXITCODE = if ($exit -eq "0" -and $code -eq 0) { 0 } else { 1 }
}
Step "app role cannot connect to the mock database" {
    $out = & docker @compose exec -T -e "PGPASSWORD=$($values['APP_DB_PASSWORD'])" db psql -h 127.0.0.1 -U loyalty_app -d mock_customer_api -c "select 1" 2>&1
    $global:LASTEXITCODE = if ("$out" -match "permission denied|not permitted|FATAL") { 0 } else { 1 }
}
# The upgrade path (ADR-0052): a volume left by an earlier milestone has mock data loaded, the app database behind and
# no demo accounts. Recreate that state on this stack, then run the same commands the owner runs.
$stack = @("-ExecutionPolicy", "Bypass", "-File", "scripts\stack.ps1", "-EnvFile", $envFile, "-Project", $project)
$head = (Get-ChildItem migrations\versions -Filter *.py | Sort-Object Name | Select-Object -Last 1).Name.Substring(0, 4)
function Sql([string]$query) {
    (& docker @compose exec -T db psql -U $values['POSTGRES_USER'] -d loyalty -tAc $query | Out-String).Trim()
}
Step "upgrade path: back to the Milestone 4 schema (revision 0001), mock data kept" {
    & docker @compose run --rm migrate alembic downgrade 0001
    $code = $LASTEXITCODE
    & docker @compose rm -sf app
    $global:LASTEXITCODE = $code
}
Step "upgrade path: stack.ps1 -Action up migrates and reports ready" {
    powershell @stack -Action up
    $code = $LASTEXITCODE
    $version = Sql "select version_num from alembic_version"
    Write-Host "app database revision: $version"
    $global:LASTEXITCODE = if ($code -eq 0 -and $version -eq $head) { 0 } else { 1 }
}
Step "upgrade path: a running app on an old schema is seen and migrated by stack.ps1 -Action up" {
    & docker @compose run --rm migrate alembic downgrade 0001
    powershell @stack -Action up
    $code = $LASTEXITCODE
    $version = Sql "select version_num from alembic_version"
    Write-Host "app database revision: $version"
    $global:LASTEXITCODE = if ($code -eq 0 -and $version -eq $head) { 0 } else { 1 }
}
foreach ($round in 1, 2) {
    Step "upgrade path: stack.ps1 -Action seed on loaded data, run $round of 2" {
        $out = powershell @stack -Action seed | Out-String
        Write-Host $out
        $code = $LASTEXITCODE
        $users = Sql "select count(*) from users"
        Write-Host "demo accounts in the database: $users"
        $global:LASTEXITCODE = if ($code -eq 0 -and $out -match "mock data already loaded, skipped" -and $users -eq "6") { 0 } else { 1 }
    }
}
# A volume from before Milestone 6: one app role that owns everything, and no owner role (ADR-0058).
Step "upgrade path: a volume with one app role is split by stack.ps1 -Action up, and the audit rights hold" {
    foreach ($query in @(
        "DROP DATABASE loyalty_test",
        "REASSIGN OWNED BY loyalty_owner TO loyalty_app",
        "DROP OWNED BY loyalty_owner",
        "DROP ROLE loyalty_owner"
    )) { Sql $query | Out-Null }
    Write-Host "owner before: $(Sql "select tableowner from pg_tables where tablename = 'cases'")"
    powershell @stack -Action up
    $code = $LASTEXITCODE
    $owner = Sql "select tableowner from pg_tables where tablename = 'cases'"
    $canUpdate = Sql "select has_table_privilege('loyalty_app', 'case_events', 'UPDATE')"
    $canInsert = Sql "select has_table_privilege('loyalty_app', 'case_events', 'INSERT')"
    Write-Host "owner after: $owner; loyalty_app can update case_events: $canUpdate; can insert: $canInsert"
    $global:LASTEXITCODE = if ($code -eq 0 -and $owner -eq "loyalty_owner" -and $canUpdate -eq "f" -and $canInsert -eq "t") { 0 } else { 1 }
}
Step "upgrade path: a stopped app is named as the cause, not only 'unhealthy'" {
    & docker @compose stop app
    $out = uv run python scripts/stack_diagnose.py --project $project --env-file $envFile | Out-String
    $code = $LASTEXITCODE
    Write-Host $out
    $global:LASTEXITCODE = if ($code -eq 1 -and $out -match "app: stopped with exit code") { 0 } else { 1 }
}

if (-not $Keep) { & docker @compose down -v --remove-orphans | Out-Null }
Remove-Item $envFile -ErrorAction SilentlyContinue
if ($failed.Count -gt 0) { Write-Host "compose check FAILED: $($failed -join '; ')"; exit 1 }
Write-Host "compose check passed."
exit 0
