#Requires -Version 5.1
# smoke.ps1 — PowerShell equivalent of smoke.sh
#
# Exercises the render_diff and frame_strip scripts against synthetic inputs.
#
# Usage:
#   .\smoke.ps1 <scripts-dir>
#
# Where <scripts-dir> points to the directory containing render_diff.ps1 and
# frame_strip.ps1 (defaults to the directory containing this script).
#
# Exit 0 on pass, 1 on fail.

param(
    [string]$ScriptsDir
)

$ErrorActionPreference = "Stop"

# --- Resolve scripts directory ---
if (-not $ScriptsDir) {
    $ScriptsDir = Split-Path -Parent $PSCommandPath
}
$ScriptsDir = Resolve-Path $ScriptsDir
$renderDiff  = Join-Path $ScriptsDir "render_diff.ps1"
$frameStrip  = Join-Path $ScriptsDir "frame_strip.ps1"

# --- Setup temp working directory ---
$WORK = Join-Path $env:TEMP "smoke_$([System.Guid]::NewGuid().ToString())"
New-Item -ItemType Directory -Path $WORK -Force | Out-Null

try {
    # --- Check ffmpeg ---
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) {
        Write-Host "[FAIL] ffmpeg not found on PATH" -ForegroundColor Red
        exit 1
    }

    Write-Host "==> smoke: render_diff.ps1 against identical inputs" -ForegroundColor Yellow

    # Generate identical test videos
    & ffmpeg -y -hide_banner -loglevel error `
        -f lavfi -i "testsrc=duration=2:size=320x240:rate=30" `
        -pix_fmt yuv420p "$WORK/baseline.mp4" 2>$null
    Copy-Item "$WORK/baseline.mp4" "$WORK/translated.mp4"

    # Run render_diff.ps1
    $diffOut = Join-Path $WORK "diff"
    $global:LASTEXITCODE = 0
    & $renderDiff -Baseline "$WORK/baseline.mp4" -Translated "$WORK/translated.mp4" -OutputDir $diffOut -Threshold 0.99 2>&1 | Out-Null

    # Check result
    $summaryPath = Join-Path $diffOut "summary.json"
    if (Test-Path $summaryPath) {
        $summary = Get-Content -Encoding UTF8 -Raw $summaryPath | ConvertFrom-Json
        $mean = $summary.mean
        $pass = $summary.pass
        Write-Host "    identical inputs -> mean SSIM=$mean (pass=$pass)" -ForegroundColor Gray
        if (-not $pass) {
            Write-Host "[FAIL] identical inputs failed pass check" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[FAIL] summary.json not produced" -ForegroundColor Red
        exit 1
    }

    Write-Host "==> smoke: render_diff.ps1 against different inputs" -ForegroundColor Yellow

    # Generate different test pattern
    & ffmpeg -y -hide_banner -loglevel error `
        -f lavfi -i "testsrc2=duration=2:size=320x240:rate=30" `
        -pix_fmt yuv420p "$WORK/different.mp4" 2>$null

    # Run render_diff.ps1 - should FAIL at threshold 0.99
    $diffOut2 = Join-Path $WORK "diff2"
    $global:LASTEXITCODE = 0
    & $renderDiff -Baseline "$WORK/baseline.mp4" -Translated "$WORK/different.mp4" -OutputDir $diffOut2 -Threshold 0.99 2>&1 | Out-Null
    $rc = $global:LASTEXITCODE

    $summaryPath2 = Join-Path $diffOut2 "summary.json"
    if (Test-Path $summaryPath2) {
        $summary2 = Get-Content -Encoding UTF8 -Raw $summaryPath2 | ConvertFrom-Json
        $diffMean = $summary2.mean
        if ($rc -eq 0) {
            Write-Host "[FAIL] different inputs unexpectedly passed at threshold 0.99 (mean=$diffMean)" -ForegroundColor Red
            exit 1
        }
        Write-Host "    different inputs -> mean SSIM=$diffMean (correctly failed at 0.99)" -ForegroundColor Gray
    }

    Write-Host "==> smoke: frame_strip.ps1 produces a strip" -ForegroundColor Yellow

    $stripOut = Join-Path $WORK "strip"
    & $frameStrip -Baseline "$WORK/baseline.mp4" -Translated "$WORK/different.mp4" -OutputDir $stripOut -Samples 4 2>&1 | Out-Null

    $stripPng = Join-Path $stripOut "strip.png"
    if (-not (Test-Path $stripPng -PathType Leaf)) {
        Write-Host "[FAIL] frame_strip.ps1 did not produce strip.png" -ForegroundColor Red
        exit 1
    }
    $stripSize = (Get-Item $stripPng).Length
    Write-Host "    strip.png written ($stripSize bytes)" -ForegroundColor Gray

    Write-Host "`n[PASS] smoke tests passed" -ForegroundColor Green
    exit 0
}
finally {
    Remove-Item -Recurse -Force $WORK -ErrorAction SilentlyContinue
}
