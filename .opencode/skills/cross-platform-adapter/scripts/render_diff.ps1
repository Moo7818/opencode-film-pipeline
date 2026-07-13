#Requires -Version 5.1
# render_diff.ps1 — PowerShell equivalent of render_diff.sh
#
# Computes per-frame SSIM between two video files using ffmpeg.
#
# Usage:
#   .\render_diff.ps1 <baseline.mp4> <translated.mp4> [output-dir]
#
# Output (in output-dir, defaults to ./diff-out):
#   ssim.log          — per-frame SSIM lines from ffmpeg
#   summary.json      — { mean, min, p05, p95, frame_count, pass, threshold }
#
# Exit codes:
#   0  — pass (mean SSIM >= threshold)
#   1  — fail (mean SSIM <  threshold)
#   2  — usage / setup error

param(
    [Parameter(Mandatory=$true)]
    [string]$Baseline,
    [Parameter(Mandatory=$true)]
    [string]$Translated,
    [string]$OutputDir = "./diff-out",
    [double]$Threshold = 0.85
)

$ErrorActionPreference = "Stop"

# --- Helper: invoke Python with a script block ---
function Invoke-PythonInline {
    param([string]$ScriptBlock, [string[]]$PyArgs)
    $tmpFile = Join-Path $env:TEMP "render_diff_py_$([System.Guid]::NewGuid().ToString()).py"
    try {
        Set-Content -Path $tmpFile -Encoding UTF8 -Value $ScriptBlock
        # Detect python3 first (Unix), fall back to python (Windows)
        $pyCmd = "python3"
        if (-not (Get-Command $pyCmd -ErrorAction SilentlyContinue)) { $pyCmd = "python" }
        $result = & $pyCmd $tmpFile @PyArgs 2>&1
        $global:LASTEXITCODE = $LASTEXITCODE
        return $result
    }
    finally {
        Remove-Item -Path $tmpFile -ErrorAction SilentlyContinue
    }
}

# --- Check prerequisites ---
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Host "[ERROR] ffmpeg not on PATH" -ForegroundColor Red
    exit 2
}

if (-not (Test-Path $Baseline -PathType Leaf)) {
    Write-Host "[ERROR] baseline not found: $Baseline" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path $Translated -PathType Leaf)) {
    Write-Host "[ERROR] translated not found: $Translated" -ForegroundColor Red
    exit 2
}

# --- Setup output directory ---
$OutputDir = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
if (-not $OutputDir) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $OutputDir = Resolve-Path $OutputDir
}
$ssimLog = Join-Path $OutputDir "ssim.log"
$summaryFile = Join-Path $OutputDir "summary.json"

# --- Run ffmpeg SSIM ---
Write-Host "[SSIM] baseline: $Baseline" -ForegroundColor Gray
Write-Host "[SSIM] translated: $Translated" -ForegroundColor Gray

# ffmpeg's ssim filter: reverse inputs (main vs ref) to match render_diff.sh behavior
# Original: [0:v]scale=iw:ih[ref];[1:v]scale=iw:ih[main];[main][ref]ssim=stats_file=$SSIM_LOG
$ffmpegArgs = @(
    "-hide_banner", "-nostats", "-loglevel", "info",
    "-i", $Baseline,
    "-i", $Translated,
    "-lavfi", "[0:v]scale=iw:ih[ref];[1:v]scale=iw:ih[main];[main][ref]ssim=stats_file=$ssimLog",
    "-f", "null",
    "-"
)

$ffmpegResult = & ffmpeg @ffmpegArgs 2>&1
$ffmpegStderr = $ffmpegResult | Out-String
$ffmpegStderr | Set-Content -Path (Join-Path $OutputDir "ffmpeg.stderr") -Encoding UTF8

if (-not (Test-Path $ssimLog -PathType Leaf)) {
    Write-Host "[ERROR] ssim.log not produced" -ForegroundColor Red
    exit 2
}

# --- Parse SSIM log and produce summary ---
$pythonScript = @'
import json, math, re, sys
from pathlib import Path

log_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
threshold = float(sys.argv[3])

values = []
pattern = re.compile(r"All:([\d.]+)")
for line in log_path.read_text().splitlines():
    m = pattern.search(line)
    if m:
        try:
            values.append(float(m.group(1)))
        except ValueError:
            pass

if not values:
    print(f"error: no SSIM samples parsed from {log_path}", file=sys.stderr)
    sys.exit(2)

values.sort()
n = len(values)
mean = sum(values) / n
p_idx = lambda p: min(n - 1, max(0, int(math.floor(p * n))))
summary = {
    "frame_count": n,
    "mean": round(mean, 6),
    "min": round(values[0], 6),
    "max": round(values[-1], 6),
    "p05": round(values[p_idx(0.05)], 6),
    "p95": round(values[p_idx(0.95)], 6),
    "threshold": threshold,
    "pass": bool(mean >= threshold),
}
out_path.write_text(json.dumps(summary, indent=2) + "\n")
print(f"mean={mean:.6f} pass={mean >= threshold}")
'@

$parseResult = Invoke-PythonInline -ScriptBlock $pythonScript -Args @($ssimLog, $summaryFile, $Threshold.ToString())
Write-Host "[SSIM] $parseResult" -ForegroundColor Gray

# --- Read result ---
if (Test-Path $summaryFile -PathType Leaf) {
    $summaryRaw = Get-Content -Path $summaryFile -Encoding UTF8 -Raw
    $summary = $summaryRaw | ConvertFrom-Json
    Write-Host "[RESULT] mean SSIM = $($summary.mean), pass = $($summary.pass)" -ForegroundColor Cyan
    if ($summary.pass) {
        exit 0
    } else {
        exit 1
    }
} else {
    Write-Host "[ERROR] summary.json not produced" -ForegroundColor Red
    exit 2
}
