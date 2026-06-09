param(
    [Parameter(Mandatory=$true)]
    [string]$EventsPath,
    [Parameter(Mandatory=$true)]
    [string]$Timestamp,
    [Parameter(Mandatory=$true)]
    [string]$Type,
    [Parameter(Mandatory=$true)]
    [string]$Actor,
    [Parameter(Mandatory=$true)]
    [string]$Data,
    [string]$ProjectId,
    [string]$BatchId,
    [switch]$PassThru
)

$scriptsDir = Split-Path -Parent $PSCommandPath

$event = @{
    timestamp = $Timestamp
    type = $Type
    actor = $Actor
    data = (ConvertFrom-Json $Data)
}
if ($ProjectId) { $event.project_id = $ProjectId }
if ($BatchId) { $event.batch_id = $BatchId }

$jsonLine = $event | ConvertTo-Json -Compress -Depth 10

Add-Content -Path $EventsPath -Value $jsonLine -Encoding UTF8
if (-not $?) {
    Write-Host "[ERROR] 写入事件失败: $EventsPath" -ForegroundColor Red
    exit 1
}
Write-Host "[EVENT] $EventsPath ← $Type ($Actor)" -ForegroundColor Green

$validateResult = & python "$scriptsDir/validate.py" "$EventsPath" 2>&1
$validateExitCode = $LASTEXITCODE

if ($validateExitCode -eq 0) {
    Write-Host "[VALIDATE] $EventsPath — 通过" -ForegroundColor Green
} else {
    Write-Host "[VALIDATE] $EventsPath — 失败" -ForegroundColor Red
    $validateResult | ForEach-Object { Write-Host $_ }
}

if ($PassThru) {
    $result = @{
        event = $event
        validate = ($validateExitCode -eq 0)
    }
    return ($result | ConvertTo-Json -Compress)
}

exit $validateExitCode