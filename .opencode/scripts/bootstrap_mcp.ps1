# bootstrap_mcp.ps1 — 一键部署根项目 + grsai-server MCP 依赖（Windows）
#
# 用法（PowerShell 5.1+ / 7+，在仓库根或任意位置）：
#   .\.opencode\scripts\bootstrap_mcp.ps1
#   .\.opencode\scripts\bootstrap_mcp.ps1 -SkipRoot
#   $env:UV_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
#   .\.opencode\scripts\bootstrap_mcp.ps1
#
# 所有依赖安装到项目内 .venv，不写用户全局 site-packages。

[CmdletBinding()]
param(
    [switch]$SkipRoot,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Content -LiteralPath $PSCommandPath -TotalCount 12 | Select-Object -Skip 1
    exit 0
}

$ScriptDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$GrsaiDir = Join-Path $ProjectRoot ".opencode\mcp-servers\grsai-server"

Set-Location -LiteralPath $ProjectRoot

Write-Host "=== MCP / 项目环境 Bootstrap ==="
Write-Host "项目根: $ProjectRoot"
Write-Host "平台:   $([System.Runtime.InteropServices.RuntimeInformation]::OSDescription)"

# --- 前置：uv ---
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host "错误: 未找到 uv。" -ForegroundColor Red
    Write-Host '  安装: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host "  然后重新打开终端，再运行本脚本。"
    exit 1
}
Write-Host "uv: $(uv --version)"

if ($env:UV_INDEX_URL) {
    Write-Host "镜像: UV_INDEX_URL=$($env:UV_INDEX_URL)"
}
if ($env:HTTPS_PROXY -or $env:HTTP_PROXY -or $env:ALL_PROXY) {
    Write-Host "代理: HTTPS_PROXY=$($env:HTTPS_PROXY) HTTP_PROXY=$($env:HTTP_PROXY) ALL_PROXY=$($env:ALL_PROXY)"
}

# --- 根项目 .venv ---
if (-not $SkipRoot) {
    Write-Host ""
    Write-Host "→ [1/2] 同步根项目依赖 → .venv/"
    uv sync
    $rootPyUnix = Join-Path $ProjectRoot ".venv\bin\python3"
    $rootPyWin = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $rootPyWin) {
        $ver = & $rootPyWin --version 2>&1
        Write-Host "  Python: $ver"
    } elseif (Test-Path -LiteralPath $rootPyUnix) {
        $ver = & $rootPyUnix --version 2>&1
        Write-Host "  Python: $ver"
    } else {
        Write-Host "错误: 根 .venv 中未找到 Python" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "→ [1/2] 跳过根项目 (-SkipRoot)"
}

# --- grsai-server ---
Write-Host ""
Write-Host "→ [2/2] 同步 grsai-server → .opencode/mcp-servers/grsai-server/.venv/"
$grsaiToml = Join-Path $GrsaiDir "pyproject.toml"
if (-not (Test-Path -LiteralPath $grsaiToml)) {
    Write-Host "错误: 找不到 $grsaiToml" -ForegroundColor Red
    exit 1
}
Push-Location -LiteralPath $GrsaiDir
try {
    uv sync
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "→ 验证 grsai-server 导入与 CLI"
# 单行 -c，避免 PowerShell 多行字符串传参问题
$verifyCode = "import sys,cryptography,httpx,mcp,grsai_server; assert cryptography.__version__.startswith('48.'), cryptography.__version__; print('  python     :', sys.version.split()[0], sys.platform); print('  cryptography:', cryptography.__version__); print('  httpx      :', httpx.__version__); print('  mcp        : OK'); print('  grsai_server: OK')"
uv run --no-sync --directory $GrsaiDir python -c $verifyCode
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run --no-sync --directory $GrsaiDir python -m grsai_server --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "  --help      : OK"

# --- 凭证提示 ---
$cred = Join-Path $ProjectRoot ".opencode\credentials\media_gen_config.json"
Write-Host ""
if (Test-Path -LiteralPath $cred) {
    Write-Host "凭证: 已找到 $cred"
} else {
    Write-Host "警告: 未找到凭证文件:" -ForegroundColor Yellow
    Write-Host "  $cred"
    Write-Host "  见 .opencode/rules/credential-management.md"
}

Write-Host ""
Write-Host "=== Bootstrap 完成 ==="
Write-Host "下一步:"
Write-Host "  1. 确认 media_gen_config.json 已就位"
Write-Host "  2. 重启 opencode（MCP 命令见 opencode.json → grsai-mcp）"
Write-Host ""
Write-Host "手动验证:"
Write-Host "  uv run --no-sync --directory .opencode/mcp-servers/grsai-server -m grsai_server --help"
