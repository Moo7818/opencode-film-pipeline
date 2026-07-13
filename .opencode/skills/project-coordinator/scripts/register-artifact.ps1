param(
    [Parameter(Mandatory=$true)]
    [string]$ManifestPath,
    [Parameter(Mandatory=$true)]
    [string]$EventsPath,
    [Parameter(Mandatory=$true)]
    [string]$Type,
    [Parameter(Mandatory=$true)]
    [string]$Name,
    [Parameter(Mandatory=$true)]
    [string]$ArtifactPath,
    [Parameter(Mandatory=$true)]
    [string]$Stage,
    [string]$Actor = "project-coordinator",
    [string]$ArtifactId,
    [string[]]$Tags,
    [string]$ProjectId,
    [switch]$PassThru
)

$scriptsDir = Split-Path -Parent $PSCommandPath
$timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz") -replace "([+-]\d{2})(\d{2})$", '$1:$2'

if (-not (Test-Path $ArtifactPath)) {
    Write-Host "[ERROR] 产物文件不存在: $ArtifactPath" -ForegroundColor Red
    exit 1
}

$hashResult = & python "$scriptsDir/hash.py" --fast "$ArtifactPath" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 哈希计算失败: $ArtifactPath" -ForegroundColor Red
    exit 1
}

$hashValue = ""
$sizeValue = 0
foreach ($line in $hashResult) {
    if ($line -match "^HASH=(.+)") { $hashValue = $matches[1] }
    if ($line -match "^SIZE=(\d+)") { $sizeValue = [int]$matches[1] }
}

if (-not $hashValue) {
    Write-Host "[ERROR] 无法解析哈希结果" -ForegroundColor Red
    exit 1
}

Write-Host "[HASH] $ArtifactPath → $hashValue ($sizeValue bytes)" -ForegroundColor Green

if (-not (Test-Path $ManifestPath)) {
    $manifest = @{ _version = 1; artifacts = @() }
} else {
    $manifestJson = Get-Content -Path $ManifestPath -Encoding UTF8 -Raw
    $manifest = $manifestJson | ConvertFrom-Json
    if (-not $manifest.artifacts) { $manifest.artifacts = @() }
}

if (-not $ArtifactId) {
    $existingIds = $manifest.artifacts | ForEach-Object { $_.id }
    $maxNum = 0
    foreach ($aid in $existingIds) {
        if ($aid -match "^art_(\d+)$") {
            $num = [int]$matches[1]
            if ($num -gt $maxNum) { $maxNum = $num }
        }
    }
    $ArtifactId = "art_{0:D3}" -f ($maxNum + 1)
}

$existingIdx = -1
for ($i = 0; $i -lt $manifest.artifacts.Count; $i++) {
    if ($manifest.artifacts[$i].path -eq $ArtifactPath) { $existingIdx = $i; break }
}

if ($existingIdx -ge 0) {
    $manifest.artifacts[$existingIdx].status = "deprecated"
    Write-Host "[DEPRECATE] $($manifest.artifacts[$existingIdx].id) — 旧条目标记为 deprecated" -ForegroundColor Yellow
}

$artifact = @{
    id = $ArtifactId
    type = $Type
    name = $Name
    path = $ArtifactPath
    stage = $Stage
    status = "final"
    created_at = $timestamp
    updated_at = $timestamp
    hash = $hashValue
    size = $sizeValue
}
if ($Tags -and $Tags.Count -gt 0) {
    $artifact.tags = $Tags
}
$manifest.artifacts += $artifact

$manifestJson = $manifest | ConvertTo-Json -Depth 10
$manifestJson | Set-Content -Path $ManifestPath -Encoding UTF8

if (-not $?) {
    Write-Host "[ERROR] manifest.json 写入失败: $ManifestPath" -ForegroundColor Red
    exit 1
}
Write-Host "[MANIFEST] $ManifestPath ← $ArtifactId ($Type)" -ForegroundColor Green

$validateResult = & python "$scriptsDir/validate.py" "$ManifestPath" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[VALIDATE] manifest.json — 失败" -ForegroundColor Red
    $validateResult | ForEach-Object { Write-Host $_ }
    exit 1
}
Write-Host "[VALIDATE] manifest.json — 通过" -ForegroundColor Green

$eventData = @{
    artifact_id = $ArtifactId
    type = $Type
    path = $ArtifactPath
    hash = $hashValue
    size = $sizeValue
} | ConvertTo-Json -Compress -Depth 10

$event = @{
    timestamp = $timestamp
    type = "artifact.created"
    actor = $Actor
    data = (ConvertFrom-Json $eventData)
}
if ($ProjectId) { $event.project_id = $ProjectId }
$eventJson = $event | ConvertTo-Json -Compress -Depth 10

Add-Content -Path $EventsPath -Value $eventJson -Encoding UTF8
if (-not $?) {
    Write-Host "[ERROR] 事件写入失败: $EventsPath" -ForegroundColor Red
    exit 1
}
Write-Host "[EVENT] $EventsPath ← artifact.created ($ArtifactId)" -ForegroundColor Green

$validateResult = & python "$scriptsDir/validate.py" "$EventsPath" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[VALIDATE] events.jsonl — 失败" -ForegroundColor Red
    $validateResult | ForEach-Object { Write-Host $_ }
    exit 1
}
Write-Host "[VALIDATE] events.jsonl — 通过" -ForegroundColor Green

Write-Host "[DONE] 产物注册完成: $Name → $ArtifactPath" -ForegroundColor Green

if ($PassThru) {
    $result = @{
        artifact_id = $ArtifactId
        hash = $hashValue
        size = $sizeValue
    }
    return ($result | ConvertTo-Json -Compress)
}

exit 0