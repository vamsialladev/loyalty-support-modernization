# Milestone 12 (DEL-06, ADR-0085): check the AWS Terraform without an AWS account. Runs Terraform and Trivy from
# their pinned images: `fmt -check`, `init -backend=false` (downloads the pinned provider, no credentials),
# `validate`, then Trivy's config scan of the Terraform (fixable HIGH/CRITICAL misconfigurations fail).
# **Never plans or applies.** Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\terraform_check.ps1
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$tf = "hashicorp/terraform:1.17.1"
$dir = "${PWD}\infrastructure\terraform\aws"
$failed = @()
function Step([string]$label, [scriptblock]$block) {
    Write-Host "== $label"
    & $block
    if ($LASTEXITCODE -ne 0) { $script:failed += $label; Write-Host "FAILED: $label" }
}
Step "terraform fmt -check" { & docker run --rm -v "${dir}:/tf" -w /tf $tf fmt -check -recursive -diff }
Step "terraform init -backend=false" { & docker run --rm -v "${dir}:/tf" -w /tf $tf init -backend=false -input=false -no-color }
Step "terraform validate" { & docker run --rm -v "${dir}:/tf" -w /tf $tf validate -no-color }
Step "trivy config (HIGH, CRITICAL)" {
    & docker run --rm -v "${dir}:/tf:ro" aquasec/trivy:0.76.1 config --quiet --severity HIGH,CRITICAL --exit-code 1 --skip-dirs /tf/.terraform /tf
}
if ($failed.Count -gt 0) { Write-Host "terraform check FAILED: $($failed -join '; ')"; exit 1 }
Write-Host "terraform check passed."
exit 0
