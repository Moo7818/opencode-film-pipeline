---
name: cross-platform-adapter
description: |
  Cross-platform compatibility adapter for the .trae system. Provides utility
  scripts and guidelines for running Python, handling paths, and managing
  temporary files across Windows and Unix environments. Triggers when:
  (1) A script fails with "python3: command not found" on Windows,
  (2) Hard-coded Unix paths like "/tmp/" appear in code being written or reviewed,
  (3) Shell scripts (.sh) need to run on Windows or PowerShell scripts (.ps1)
  need to run on Unix,
  (4) File path separators (backslash vs forward slash) cause issues,
  (5) Any cross-platform compatibility concern is raised.
  Agents must load this skill whenever they need to write or execute scripts
  that should work on both Windows and Unix.
---

# Cross-Platform Adapter

## 核心原则

`.trae` 系统目前是 **Windows-first** 架构，但部分 Skill（`heygen-skills`）包含 Unix-only 的 Bash 脚本。
本 Skill 提供一套工具和规范，让 Agent 在编写/执行脚本时自动处理平台差异。

## 快速参考：平台检测

| 判断方式 | PowerShell | Bash | Python |
|---------|-----------|------|--------|
| 检测操作系统 | `$env:OS` 或 `[Environment]::OSVersion` | `uname -s` | `sys.platform` / `os.name` |
| Windows? | `$IsWindows` (pwsh) 或检查 `$env:OS` | `[[ "$(uname -s)" == *NT* ]]` | `sys.platform == "win32"` |
| 临时目录 | `$env:TEMP` | `$TMPDIR` 或 `/tmp` | `tempfile.gettempdir()` |

## 脚本清单

| 脚本 | 平台 | 用途 | 对应原始脚本 |
|------|------|------|-------------|
| `scripts/run_py.ps1` | Windows | Python 启动器（自动检测 `python`/`python3`） | — |
| `scripts/run_py.sh` | Unix | Python 启动器 | — |
| `scripts/cross_path.py` | 跨平台 | 路径工具（临时目录、工具检测） | — |
| `scripts/render_diff.ps1` | Windows | 视频 SSIM 差异计算 | `heygen-skills/.../render_diff.sh` |
| `scripts/frame_strip.ps1` | Windows | 视频帧对比条生成 | `heygen-skills/.../frame_strip.sh` |
| `scripts/smoke.ps1` | Windows | 冒烟测试 | `heygen-skills/.../tests/smoke.sh` |

### Python 启动器

`scripts/run_py.ps1` 和 `scripts/run_py.sh` 自动检测 `python3` vs `python` 命令：

**PowerShell 用法：**
```powershell
& "$PSScriptRoot/scripts/run_py.ps1" script.py arg1 arg2
```

**Bash 用法：**
```bash
source "$SKILL_DIR/scripts/run_py.sh"
run_py script.py arg1 arg2
```

### 跨平台路径工具

```python
# cross_path.py 提供的核心函数
from scripts.cross_path import (
    ensure_dir,       # mkdir -p 的跨平台版
    temp_dir,         # 创建临时目录
    normalize_path,   # 规范化路径分隔符
    to_forward_slash, # 转正斜杠（用于URL/显示）
    require_tool,     # 检查工具存在，带平台提示
    is_windows,       # 判断当前平台
    python_command,   # 返回正确的 python 命令名
)
```

### PowerShell 等价脚本

以下脚本是 `heygen-skills` 中 Bash 脚本的 PowerShell 等价版，语法完全对应：

- **`render_diff.ps1`** — 计算两个视频间的帧级 SSIM，输出 `summary.json`
- **`frame_strip.ps1`** — 从两个视频中采样帧，生成对比条 `strip.png`
- **`smoke.ps1`** — 对上述两个脚本进行冒烟测试

详细语法对照见 `references/pwsh_equivalents.md`。

### 临时文件/目录

**Python（推荐）：**
```python
import tempfile
from pathlib import Path

# 临时目录
tmp = Path(tempfile.gettempdir()) / "my_skill_work"
tmp.mkdir(parents=True, exist_ok=True)

# 临时文件
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    f.write(data)
```

**PowerShell：**
```powershell
$tmp = Join-Path $env:TEMP "my_skill_work"
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
```

**Bash：**
```bash
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
```

## 路径编写规范

### 铁律

1. **Python 代码**：始终使用 `pathlib.Path` 或 `os.path.join()`，绝不手写 `/` 或 `\`
2. **PowerShell 脚本**：使用 `Join-Path`，禁止字符串拼接路径
3. **Bash 脚本**：使用 `/` 分隔符（在 Git Bash/WSL 中透明转换）
4. **跨脚本传参**：使用 `--output-dir` 等参数传递路径，不假设分隔符

### Python 路径反模式与修正

| 反模式 | 修正 |
|--------|------|
| `path = "/tmp/my_work"` | `path = str(Path(tempfile.gettempdir()) / "my_work")` |
| `path = "output\\" + name` | `path = os.path.join("output", name)` |
| `path.replace("\\", "/")` 做目录遍历 | 使用 `pathlib.Path` 的 `.parts` 或 `.relative_to()` |

### Shell 脚本路径

在 `.trae` 系统中，Bash 脚本仅在 `heygen-skills` 中出现，且仅在 Unix 环境运行。
如果要让 Bash 脚本在 Windows 上也运行，有以下选项：

1. **Git Bash**（推荐）：安装 Git for Windows 后，`.sh` 脚本在 Git Bash 中可直接运行
2. **WSL**：在 WSL 中运行完整的 Linux 环境
3. **PowerShell 等价版**：为本项目核心 `.sh` 脚本编写 `.ps1` 版本（参见 `references/pwsh_equivalents.md`）

## 编码规范（跨平台）

| 规则 | Windows | Unix |
|------|---------|------|
| Python 文件读写 | `encoding="utf-8"` | `encoding="utf-8"` |
| PowerShell 文件读写 | `-Encoding UTF8` | N/A（用pwsh时同左） |
| Bash 文件读写 | N/A（用Git Bash时UTF-8原生） | UTF-8 原生（locale 可能影响） |
| JSON 写入 | `ensure_ascii=False` | `ensure_ascii=False` |

## 外部工具依赖处理

某些 Skill 依赖外部工具（ffmpeg、soffice、gcc）。在脚本中应优雅降级：

```python
import shutil
import sys

def require_tool(name: str) -> str:
    """查找可执行文件，找不到则给出平台特定的安装提示"""
    path = shutil.which(name)
    if path:
        return path
    hints = {
        "ffmpeg": {
            "win32": "请从 https://ffmpeg.org/download.html 下载并加入 PATH",
            "linux": "请运行: sudo apt install ffmpeg",
            "darwin": "请运行: brew install ffmpeg",
        },
        "soffice": {
            "win32": "请安装 LibreOffice: https://www.libreoffice.org/",
            "linux": "请运行: sudo apt install libreoffice",
            "darwin": "请运行: brew install --cask libreoffice",
        },
    }
    platform_hint = hints.get(name, {}).get(sys.platform, f"请安装 {name}")
    print(f"错误: 未找到 {name}。{platform_hint}", file=sys.stderr)
    sys.exit(1)
```

## PowerShell 等价脚本编写指南

当需要为 Bash 脚本编写 PowerShell 等价版时，参考以下对照表：

| Bash | PowerShell |
|------|-----------|
| `#!/usr/bin/env bash` | `# 不需要 shebang（或使用 #Requires -Version 5.1）` |
| `set -euo pipefail` | `$ErrorActionPreference = "Stop"` |
| `mktemp -d` | `[System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid().ToString()` |
| `trap 'rm -rf "$DIR"' EXIT` | `try { ... } finally { Remove-Item -Recurse -Force $dir }` |
| `command -v ffmpeg` | `Get-Command ffmpeg -ErrorAction SilentlyContinue` |
| `mkdir -p "$DIR"` | `New-Item -ItemType Directory -Path $dir -Force \| Out-Null` |
| `/dev/null` | `$null` |
| `cp src dst` | `Copy-Item src dst` |
| `rm -rf "$DIR"` | `Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue` |
| `$((command))` | `$(command)` 或 `& command` |
| `if [[ -f "$FILE" ]]` | `if (Test-Path $FILE -PathType Leaf)` |
| `python3 script.py` | `& python script.py`（Windows 上 `python3` 通常不存在） |
| `stat -c%s "$FILE"` | `(Get-Item $FILE).Length` |
| `dirname "$0"` / `BASH_SOURCE` | `$PSScriptRoot` / `Split-Path -Parent $PSCommandPath` |

详细对照表见 `references/pwsh_equivalents.md`。