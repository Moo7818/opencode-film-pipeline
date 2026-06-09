# PowerShell ↔ Bash 等价命令对照表

用于将 `heygen-skills` 中的 Bash 脚本翻译为 PowerShell 版本。

## 基础语法对照

| Bash | PowerShell | 说明 |
|------|-----------|------|
| `set -euo pipefail` | `$ErrorActionPreference = "Stop"` | 遇到错误即停止 |
| `#!/usr/bin/env bash` | `#Requires -Version 5.1` | 版本声明（可选） |
| `$VAR` | `$VAR` | 变量语法完全相同 |
| `"$VAR"` | `"$VAR"` | 双引号插值相同 |
| `$(cmd)` | `$(cmd)` | 命令替换语法相同 |
| `> /dev/null` | `> $null` | 抑制输出 |
| `2>&1` | `2>&1` | 标准错误合并到标准输出 |
| `\` 续行 | `` ` `` 反引号续行 | PowerShell 使用反引号 |
| `&&` | `-and` | 逻辑与 |
| `\|\|` | `-or` | 逻辑或 |
| `# 注释` | `# 注释` | 注释语法相同 |

## 常用命令对照

### 文件和目录操作

| Bash | PowerShell | 示例 |
|------|-----------|------|
| `mkdir -p "$DIR"` | `New-Item -ItemType Directory -Path $DIR -Force \| Out-Null` | 创建目录 |
| `rm -rf "$DIR"` | `Remove-Item -Recurse -Force $DIR -ErrorAction SilentlyContinue` | 删除目录 |
| `cp src dst` | `Copy-Item src dst` | 复制文件 |
| `mv src dst` | `Move-Item src dst` | 移动文件 |
| `ls "$DIR"` | `Get-ChildItem $DIR` | 列出目录 |
| `find "$DIR" -name "*.py"` | `Get-ChildItem $DIR -Filter "*.py" -Recurse` | 递归查找 |
| `stat -c%s "$FILE"` | `(Get-Item $FILE).Length` | 获取文件大小 |
| `stat -f%z "$FILE"` | `(Get-Item $FILE).Length` | macOS stat 文件大小 |

### 路径操作

| Bash | PowerShell | 示例 |
|------|-----------|------|
| `$(dirname "$0")` | `Split-Path -Parent $PSCommandPath` | 脚本所在目录 |
| `$(dirname "${BASH_SOURCE[0]}")` | `Split-Path -Parent $PSCommandPath` | 脚本所在目录（PS 更简单）|
| `$(cd .. && pwd)` | `(Get-Item ..).FullName` | 上级目录绝对路径 |
| 路径拼接用 `/` | `Join-Path $parent $child` | 安全拼接路径 |
| 检查文件存在: `[[ -f "$F" ]]` | `if (Test-Path $F -PathType Leaf)` | 判断文件 |
| 检查目录存在: `[[ -d "$D" ]]` | `if (Test-Path $D -PathType Container)` | 判断目录 |

### 进程和命令执行

| Bash | PowerShell | 示例 |
|------|-----------|------|
| `command -v ffmpeg` | `Get-Command ffmpeg -ErrorAction SilentlyContinue` | 检查命令是否存在 |
| `ffmpeg ...` | `& ffmpeg ...` | 执行外部命令（& 前缀）|
| `$(ffmpeg ...)` | `& ffmpeg ... \| Out-String` | 捕获外部命令输出 |
| `exit 0` / `exit 1` | `exit 0` / `exit 1` | 退出码相同 |
| `$?` | `$LASTEXITCODE` | 获取上条命令退出码 |
| `trap 'cmd' EXIT` | `try { ... } finally { cmd }` | 退出清理 |

### 字符串和数组

| Bash | PowerShell | 示例 |
|------|-----------|------|
| `for f in "${array[@]}"` | `foreach ($f in $array)` | 遍历数组 |
| `"${var#prefix}"` | `$var -replace "^prefix", ""` | 去除前缀 |
| `"${var%suffix}"` | `$var -replace "suffix$", ""` | 去除后缀 |
| `wc -l` | `Measure-Object \| Select-Object -ExpandProperty Count` | 行数统计 |
| `head -n 5` | `Get-Content ... \| Select-Object -First 5` | 取前N行 |
| `tail -n 5` | `Get-Content ... \| Select-Object -Last 5` | 取后N行 |

### JSON 处理

| Bash | PowerShell | 示例 |
|------|-----------|------|
| `echo "$json" \| python3 -c "import json,sys; ..."` | `$jsonObj = $jsonStr \| ConvertFrom-Json` | 解析 JSON |
| `python3 -c "import json; print(json.dumps(...))"` | `$jsonStr = $jsonObj \| ConvertTo-Json -Depth 10` | 输出 JSON |

### 临时文件/目录

| Bash | PowerShell |
|------|-----------|
| `mktemp -d` | `$tmp = [System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid().ToString(); New-Item -ItemType Directory -Path $tmp -Force \| Out-Null` |
| `trap 'rm -rf "$WORK"' EXIT` | `try { ... } finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }` |

## 模式对应：完整脚本结构

### Bash 模板
```bash
#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "error: ffmpeg not found" >&2
  exit 1
fi

# ... main logic ...
```

### PowerShell 等价模板
```powershell
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$THIS_DIR = Split-Path -Parent $PSCommandPath
$WORK = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $WORK -Force | Out-Null

try {
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Host "error: ffmpeg not found" -ForegroundColor Red
        exit 1
    }

    # ... main logic ...
}
finally {
    Remove-Item -Recurse -Force $WORK -ErrorAction SilentlyContinue
}
```

## `heygen-skills` 特殊注意事项

`heygen-skills` 中的 `.sh` 脚本有以下特殊之处，翻译为 `.ps1` 时需注意：

1. **`python3` → `python`**：Windows 上 `python3` 通常不存在，始终使用 `python`
2. **`ffmpeg` 子进程**：PowerShell 中调用 `& ffmpeg ...` 时，`2>$null` 等价于 Bash 的 `2>/dev/null`
3. **heredoc（`<<'PY'`）**：PowerShell 不支持 heredoc。解决方案：
   - 将内嵌 Python 代码保存为独立 `.py` 文件
   - 或用 `@" "@` here-string 包裹字符串，写入临时文件后执行
4. **`stat -c%s\|stat -f%z`**：PowerShell 使用 `(Get-Item $path).Length`
