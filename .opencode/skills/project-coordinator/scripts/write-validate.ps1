param(
    [Parameter(Mandatory=$true)]
    [string]$Path,
    [Parameter(Mandatory=$true)]
    [string]$Value,
    [string]$Encoding = "UTF8",
    [switch]$PassThru
)

$scriptsDir = Split-Path -Parent $PSCommandPath

$escapedValue = $Value -replace "'", "''"

$result = $Value | Set-Content -Path $Path -Encoding $Encoding
if (-not $?) {
    Write-Host "[ERROR] 写入失败: $Path" -ForegroundColor Red
    exit 1
}
Write-Host "[WRITE] $Path" -ForegroundColor Green

$validateResult = & python "$scriptsDir/validate.py" "$Path" 2>&1
$validateExitCode = $LASTEXITCODE

if ($validateExitCode -eq 0) {
    Write-Host "[VALIDATE] $Path — 通过" -ForegroundColor Green
} else {
    Write-Host "[VALIDATE] $Path — 失败" -ForegroundColor Red
    $validateResult | ForEach-Object { Write-Host $_ }
}

if ($PassThru) {
    return $validateResult
}

exit $validateExitCode