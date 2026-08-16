# 部署流程

clone / 拷贝项目目录后，按本文完成环境安装。所有 Python 依赖落在**项目内 venv**，不要求全局 `pip install`。

---

## 架构说明

| 环境 | 路径 | 管理方式 | 用途 |
|------|------|----------|------|
| 根项目 | `.venv/` | 根目录 `pyproject.toml` + `uv.lock` | skill 脚本、通用工具 |
| GRSAI MCP | `.opencode/mcp-servers/grsai-server/.venv/` | 子项目 `pyproject.toml` + `uv.lock` | opencode 中的 `grsai-mcp` |

两者**相互隔离**。MCP 由 `opencode.json` 通过跨平台命令启动：

```json
"command": [
  "uv", "run", "--no-sync",
  "--directory", ".opencode/mcp-servers/grsai-server",
  "-m", "grsai_server"
]
```

- 需要系统 PATH 中有 `uv`（不依赖 sh/bat 包装脚本）
- `--no-sync`：启动不自动装包，须先完成下方 bootstrap / `uv sync`

---

## 前置条件

| 项 | 要求 |
|----|------|
| OS | macOS（Intel x86_64 / Apple Silicon arm64）、Linux、Windows 10+ |
| uv | 最新稳定版（会自动拉取 CPython 3.13） |
| 网络 | 可访问 PyPI，或配置镜像/代理（见下文） |
| 凭证 | `.opencode/credentials/media_gen_config.json`（见 credential-management.md） |

不必预先安装系统 Python；`uv` 会按需下载 CPython 3.13 到用户 uv 缓存，项目 venv 仍在仓库目录内。

---

## 一键部署（推荐）

### macOS / Linux

```bash
# 1. 安装 uv（若尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 重新打开终端或 source 安装提示的 env

# 2. 进入仓库根目录
cd /path/to/repo

# 3. 一键同步根项目 + grsai-server，并做导入/--help 验证
./.opencode/scripts/bootstrap_mcp.sh

# 4. 放入凭证（若尚未有）
# 确保 .opencode/credentials/media_gen_config.json 存在

# 5. 启动 opencode
opencode
```

### Windows（PowerShell 5.1+ / 7+）

```powershell
# 1. 安装 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# 重新打开终端

# 2. 进入仓库根目录
cd C:\path\to\repo

# 3. 一键同步
.\.opencode\scripts\bootstrap_mcp.ps1

# 4. 凭证就位后启动 opencode
opencode
```

仅同步 MCP、跳过根项目：

```bash
./.opencode/scripts/bootstrap_mcp.sh --skip-root
```

```powershell
.\.opencode\scripts\bootstrap_mcp.ps1 -SkipRoot
```

---

## 分步部署（等价手动）

```bash
# 根项目
uv sync

# GRSAI MCP（必须在其子目录或使用 --directory）
cd .opencode/mcp-servers/grsai-server
uv sync
cd ../../..
```

Windows 相同，在对应目录执行 `uv sync` 即可。

---

## 验证

```bash
# 根环境
.venv/bin/python3 --version          # Unix → 3.13.x
# Windows: .venv\Scripts\python.exe --version

# grsai-server 导入 + cryptography pin
uv run --no-sync --directory .opencode/mcp-servers/grsai-server \
  python -c "import grsai_server, cryptography, mcp, httpx; print('OK', cryptography.__version__)"
# 期望 cryptography 为 48.0.0

# CLI
uv run --no-sync --directory .opencode/mcp-servers/grsai-server \
  python -m grsai_server --help

# opencode 内：调用工具 grsai_health_check
```

---

## 网络：镜像与代理（可选）

PyPI 直连慢或超时时，在运行 `uv sync` / bootstrap **之前**设置：

```bash
# 镜像（示例：清华）
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 或 HTTP(S) 代理
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
```

PowerShell：

```powershell
$env:UV_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
# 或
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
$env:HTTP_PROXY  = "http://127.0.0.1:7890"
```

代理持久化不是部署必选项；按机器网络自行配置即可。

---

## 常见问题

### 1. Intel Mac：`cryptography` 构建失败

**原因**：`cryptography` 49.x 无 macOS x86_64 wheel，uv 会尝试源码编译并依赖 OpenSSL。

**处理**：

- grsai-server 已钉死 `cryptography==48.0.0`（含 `macosx_10_9_universal2`）
- 根项目亦 pin 同版本，避免 `uv sync` 拉到 49.x
- 若本地曾装过错误版本：

```bash
rm -rf .opencode/mcp-servers/grsai-server/.venv
cd .opencode/mcp-servers/grsai-server && uv sync
```

**不要**执行 `pip install -U cryptography` 或去掉版本钉死。

### 2. `uv run --no-sync` 提示缺包 / 无 `.venv`

先跑 bootstrap 或在对应目录 `uv sync`。`--no-sync` 是有意设计，避免 MCP 冷启动时联网。

### 3. Windows 找不到 `uv` / `python3`

- `uv` 安装后需**新开**终端
- 无需系统 `python3`；一律通过 `uv run` 或各 `.venv` 内解释器

### 4. MCP 启动但 health_check 失败

多为凭证问题，不是依赖问题。检查：

- `.opencode/credentials/media_gen_config.json` 是否存在
- 是否含 `GRSAI_API_KEY` 等字段  
见 [credential-management.md](./credential-management.md)。

### 5. 更新依赖后如何保持多平台

1. 在 `grsai-server/pyproject.toml` 修改并**优先选带 wheel 的版本**
2. `cd .opencode/mcp-servers/grsai-server && uv lock && uv sync`
3. 确认 `uv.lock` 中该包含 macosx（universal2 或 x86_64+arm64）、manylinux、win 的 wheel 条目
4. 提交 `pyproject.toml` + `uv.lock`
5. 本机跑 bootstrap 验证

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `.opencode/scripts/bootstrap_mcp.sh` | Unix 一键部署 |
| `.opencode/scripts/bootstrap_mcp.ps1` | Windows 一键部署 |
| `.opencode/scripts/setup_venv.sh` | 兼容旧入口，转调 bootstrap |
| `.opencode/mcp-servers/grsai-server/README.md` | MCP 子项目说明 |
| `opencode.json` → `mcp.grsai-mcp` | MCP 启动命令 |
| [credential-management.md](./credential-management.md) | 凭证 |
