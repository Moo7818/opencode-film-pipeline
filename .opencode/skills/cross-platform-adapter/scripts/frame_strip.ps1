#Requires -Version 5.1
# frame_strip.ps1 — PowerShell equivalent of frame_strip.sh
#
# Produce a side-by-side comparison strip from two videos.
#
# Usage:
#   .\frame_strip.ps1 <baseline.mp4> <translated.mp4> [output-dir] [samples]
#
# Defaults: output-dir=./strip-out, samples=8.
# Output:
#   strip.png         — comparison grid PNG
#   timestamps.txt    — sampled timestamps

param(
    [Parameter(Mandatory=$true)]
    [string]$Baseline,
    [Parameter(Mandatory=$true)]
    [string]$Translated,
    [string]$OutputDir = "./strip-out",
    [int]$Samples = 8
)

$ErrorActionPreference = "Stop"

# --- Helper: invoke Python with a script block ---
function Invoke-PythonInline {
    param([string]$ScriptBlock, [string[]]$Args)
    $tmpFile = Join-Path $env:TEMP "frame_strip_py_$([System.Guid]::NewGuid().ToString()).py"
    try {
        Set-Content -Path $tmpFile -Encoding UTF8 -Value $ScriptBlock
        $result = & python @tmpFile @Args 2>&1
        return $result
    }
    finally {
        Remove-Item -Path $tmpFile -ErrorAction SilentlyContinue
    }
}

# --- Check prerequisites ---
$ffmpeg  = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffmpeg -or -not $ffprobe) {
    Write-Host "[ERROR] ffmpeg/ffprobe not on PATH" -ForegroundColor Red
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

# --- Use Python to compute frame selections and build ffmpeg filter graph ---
$pythonScript = @'
import json, subprocess, sys
from pathlib import Path

baseline, translated, outdir, samples = sys.argv[1], sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])

# Read fps + duration from the baseline
probe = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=r_frame_rate,nb_read_frames,duration",
     "-show_entries", "format=duration",
     "-of", "json", "-count_frames", baseline],
    check=True, capture_output=True, text=True,
)
data = json.loads(probe.stdout)
stream = data["streams"][0]
num, den = stream["r_frame_rate"].split("/")
fps = float(num) / float(den)
nb_frames = int(stream.get("nb_read_frames") or 0)
if nb_frames <= 0:
    duration = float(stream.get("duration") or data["format"]["duration"])
    nb_frames = int(duration * fps)

# Even-spaced sample frames in the 5%-95% window
start = max(0, int(nb_frames * 0.05))
end = max(start, int(nb_frames * 0.95) - 1)
if samples == 1:
    frames = [start]
else:
    step = (end - start) / (samples - 1)
    frames = [int(start + i * step) for i in range(samples)]

(outdir / "timestamps.txt").write_text(
    "\n".join(f"{f / fps:.3f}" for f in frames) + "\n"
)

# Build filter graph: select + hstack + vstack
select_expr = "+".join(f"eq(n,{f})" for f in frames)
n = len(frames)
filter_parts = [
    f"[0:v]select='{select_expr}',setpts=N/FRAME_RATE/TB,split={n}" + "".join(f"[b{i}]" for i in range(n)),
    f"[1:v]select='{select_expr}',setpts=N/FRAME_RATE/TB,split={n}" + "".join(f"[t{i}]" for i in range(n)),
]
for i in range(n):
    filter_parts.append(f"[b{i}][t{i}]hstack=inputs=2[row{i}]")
filter_parts.append("".join(f"[row{i}]" for i in range(n)) + f"vstack=inputs={n}[out]")
filter_graph = ";".join(filter_parts)

cmd = [
    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
    "-i", baseline, "-i", translated,
    "-filter_complex", filter_graph,
    "-map", "[out]", "-frames:v", "1",
    str(outdir / "strip.png"),
]
subprocess.run(cmd, check=True)
print(f"strip.png written ({len(frames)} samples)")
'@

Write-Host "[STRIP] Generating comparison strip..." -ForegroundColor Cyan
$result = Invoke-PythonInline -ScriptBlock $pythonScript -Args @($Baseline, $Translated, (Resolve-Path $OutputDir), $Samples.ToString())
Write-Host "[STRIP] $result" -ForegroundColor Green
