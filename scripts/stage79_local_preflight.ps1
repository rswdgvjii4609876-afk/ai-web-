param(
    [switch]$SkipFrontendBuild,
    [switch]$SkipAdminBuild,
    [switch]$SkipPytest,
    [switch]$StrictClosedLoopRecords,
    [string]$ClosedLoopCsvPath = "",
    [int]$MinCases = 5,
    [int]$MinCompleteFlows = 5,
    [int]$MinHumanScoredRows = 5,
    [int]$MinRepeatedCases = 1,
    [switch]$ValidateServerReport,
    [string]$ServerReportPath = "docs\competition\server_validation_reports\stage79_server_verify_latest.md"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "ai-interview-backend"
$FrontendDir = Join-Path $RepoRoot "ai-interview-frontend"
$AdminDir = Join-Path $RepoRoot "ai-interview-admin"

$Failures = New-Object System.Collections.Generic.List[string]

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "== $Title =="
}

function Invoke-Checked {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "+ $Name"
    try {
        & $Command
        if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
            throw "exit code $LASTEXITCODE"
        }
        Write-Host "PASS: $Name"
    }
    catch {
        Write-Host "FAIL: $Name"
        Write-Host $_
        $script:Failures.Add($Name) | Out-Null
    }
}

function Test-IgnoredPath {
    param([string]$Path)
    git check-ignore -q $Path
    return $LASTEXITCODE -eq 0
}

Push-Location $RepoRoot
try {
    Write-Section "Repository"
    git branch --show-current
    git log --oneline -1
    git status --short

    Write-Section "Ignored build artifacts"
    $ignoredPaths = @(
        "ai-interview-frontend/.vite-build-check/index.html",
        "ai-interview-admin/.vite-build-check/index.html",
        "ai-interview-frontend/node_modules/.package-lock.json",
        "ai-interview-admin/node_modules/.package-lock.json",
        "ai-interview-frontend/dist/index.html",
        "ai-interview-admin/dist/index.html"
    )

    foreach ($path in $ignoredPaths) {
        if (Test-IgnoredPath $path) {
            Write-Host "PASS: ignored $path"
        }
        else {
            Write-Host "FAIL: not ignored $path"
            $Failures.Add("ignore $path") | Out-Null
        }
    }

    Write-Section "Git diff check"
    Invoke-Checked "git diff --check" {
        git diff --check
    }

    Write-Section "Backend"
    Push-Location $BackendDir
    try {
        Invoke-Checked "python -m compileall app" {
            python -m compileall app
        }

        if (-not $SkipPytest) {
            Invoke-Checked "pytest key tests" {
                pytest tests/test_matching_engine_ability_gap.py tests/test_position_knowledge_base_slice_service.py tests/test_ai_service_panel_structure.py -q
            }
        }
        else {
            Write-Host "SKIP: pytest key tests"
        }
    }
    finally {
        Pop-Location
    }

    Write-Section "Frontend"
    if (-not $SkipFrontendBuild) {
        Push-Location $FrontendDir
        try {
            Invoke-Checked "frontend build" {
                npm run build -- --outDir .vite-build-check
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "SKIP: frontend build"
    }

    Write-Section "Admin"
    if (-not $SkipAdminBuild) {
        Push-Location $AdminDir
        try {
            Invoke-Checked "admin build" {
                npm run build -- --outDir .vite-build-check
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "SKIP: admin build"
    }

    Write-Section "Real closed-loop record schema"
    $closedLoopArgs = @("scripts\validate_real_closed_loop_records.py")
    if ($ClosedLoopCsvPath) {
        if ([System.IO.Path]::IsPathRooted($ClosedLoopCsvPath)) {
            $resolvedClosedLoopCsvPath = $ClosedLoopCsvPath
        }
        else {
            $resolvedClosedLoopCsvPath = Join-Path $RepoRoot $ClosedLoopCsvPath
        }
        $closedLoopArgs += @("--csv", $resolvedClosedLoopCsvPath)
    }

    if ($StrictClosedLoopRecords) {
        $closedLoopArgs += @(
            "--strict",
            "--min-cases", $MinCases,
            "--min-complete-flows", $MinCompleteFlows,
            "--min-human-scored-rows", $MinHumanScoredRows,
            "--min-repeated-cases", $MinRepeatedCases
        )
        Invoke-Checked "validate real closed-loop CSV strict thresholds" {
            python @closedLoopArgs
        }
    }
    else {
        Invoke-Checked "validate real closed-loop CSV" {
            python @closedLoopArgs
        }
        Write-Host "TIP: add -StrictClosedLoopRecords after real cases, human scores, and repeated runs are complete."
    }

    Write-Section "Server validation report"
    if ($ValidateServerReport) {
        if ([System.IO.Path]::IsPathRooted($ServerReportPath)) {
            $resolvedReportPath = $ServerReportPath
        }
        else {
            $resolvedReportPath = Join-Path $RepoRoot $ServerReportPath
        }
        Invoke-Checked "validate server report" {
            python scripts\validate_server_validation_report.py --report $resolvedReportPath
        }
    }
    else {
        Write-Host "SKIP: server report validation"
        Write-Host "TIP: add -ValidateServerReport after copying the server report back to the repo."
    }

    Write-Section "Summary"
    if ($Failures.Count -eq 0) {
        Write-Host "PASS: local preflight checks passed."
        exit 0
    }

    Write-Host "FAIL: $($Failures.Count) local preflight check(s) failed."
    foreach ($failure in $Failures) {
        Write-Host "- $failure"
    }
    exit 1
}
finally {
    Pop-Location
}
