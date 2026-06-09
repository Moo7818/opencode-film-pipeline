#!/usr/bin/env pwsh
# run_py.ps1 — Cross-platform Python launcher.
#
# Automatically detects the correct Python command (python3 on Unix, python on
# Windows) and invokes it with the given script and arguments.
#
# Usage:
#   & run_py.ps1 script.py [arg1 arg2 ...]
#
# Returns the exit code from the Python process.

param(
    [Parameter(Mandatory=$true)]
    [string]$Script,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

# Determine which Python command to use
$pythonCmd = "python3"  # Try python3 first (Unix / Git Bash)
$pythonPath = Get-Command $pythonCmd -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    $pythonCmd = "python"  # Fall back to python (Windows)
    $pythonPath = Get-Command $pythonCmd -ErrorAction SilentlyContinue
    if (-not $pythonPath) {
        Write-Host "[ERROR] 找不到 Python 解释器。请安装 Python 3.8+ 并加入 PATH。" -ForegroundColor Red
        exit 1
    }
}

# Resolve script path
$scriptPath = Resolve-Path $Script -ErrorAction SilentlyContinue
if (-not $scriptPath) {
    Write-Host "[ERROR] 找不到脚本: $Script" -ForegroundColor Red
    exit 1
}

# Invoke Python with the script and arguments
$allArgs = @($scriptPath.Path) + $Arguments
$proc = Start-Process -FilePath $pythonCmd -ArgumentList $allArgs -NoNewWindow -Wait -PassThru
exit $proc.ExitCode
