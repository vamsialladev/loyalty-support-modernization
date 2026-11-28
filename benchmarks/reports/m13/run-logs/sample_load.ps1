# Samples machine CPU load once a minute while the Phase 3 runner is alive, so runs that overlapped other work can be
# flagged with evidence (Milestone 13, 2026-11-27). Writes cpu-load.csv next to this file. No secrets: load and a
# count of other Python processes only.
$out = Join-Path $PSScriptRoot "cpu-load.csv"
if (-not (Test-Path $out)) { "utc,cpu_percent,other_python_processes" | Out-File -FilePath $out -Encoding utf8 }
while ($true) {
    $runner = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*evaluations.run*' }
    if (-not $runner) { break }
    $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    $others = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -notlike '*lsm-m13*' }).Count
    "$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')),$cpu,$others" | Out-File -FilePath $out -Append -Encoding utf8
    Start-Sleep -Seconds 60
}
