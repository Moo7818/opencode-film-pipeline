# GRSAI MCP Server

GRSAI 图像生成 MCP 服务器（FastMCP / stdio）。依赖与虚拟环境完全隔离在本目录，不依赖用户全局 Python 包。

## 目录结构

```
grsai-server/
├── pyproject.toml      # 依赖声明（含 cryptography 多平台 pin）
├── uv.lock             # 锁定版本（提交到 git，保证复刻一致）
├── .python-version     # Python 3.13
├── .venv/              # 本地虚拟环境（gitignore，不提交）
├── src/grsai_server/   # 源码包
│   ├── server.py       # MCP tools 入口
│   ├── grsai_client.py
│   ├── cos_client.py
│   └── config.py       # 凭证加载
└── README.md
```

## 与根目录 `.venv` 的关系

| 环境 | 路径 | 用途 |
|------|------|------|
| 根项目 | `<repo>/.venv/` | 管线脚本、skill 工具、通用依赖 |
| 本服务 | `<repo>/.opencode/mcp-servers/grsai-server/.venv/` | **仅** GRSAI MCP 运行时 |

两者独立。`opencode.json` 通过 `uv run --directory ...` 启动本服务，不会混用根 `.venv`。

## 快速部署

在仓库根目录：

```bash
# macOS / Linux
./.opencode/scripts/bootstrap_mcp.sh

# Windows PowerShell
.\.opencode\scripts\bootstrap_mcp.ps1
```

或仅同步本服务：

```bash
cd .opencode/mcp-servers/grsai-server
uv sync
uv run --no-sync python -c "import grsai_server, cryptography; print(cryptography.__version__)"
uv run --no-sync python -m grsai_server --help
```

## 启动方式（opencode）

`opencode.json` 已配置（跨平台，无需 sh/bat 包装）：

```json
"command": [
  "uv", "run", "--no-sync",
  "--directory", ".opencode/mcp-servers/grsai-server",
  "-m", "grsai_server"
]
```

- `--no-sync`：启动快，要求事先 `uv sync`（bootstrap 已做）
- `uv` 需在 PATH 中（安装见部署文档）

## 凭证

优先环境变量，否则读项目内：

`.opencode/credentials/media_gen_config.json`

详见 `.opencode/rules/credential-management.md`。

## 依赖策略（稳定优先）

- **不追最新**：选有全平台预编译 wheel 的版本
- **cryptography==48.0.0**：含 `macosx_10_9_universal2`（Intel + Apple Silicon）、manylinux、win_amd64
- **禁止**在无 wheel 的平台上升到 49.x（会触发 OpenSSL 源码编译失败）
- 变更依赖后必须：`uv lock` → 提交 `uv.lock` → 多平台或至少本机 `uv sync` 验证

## 网络 / 镜像（可选）

PyPI 慢时可临时：

```bash
# 清华镜像示例
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 或 HTTP 代理
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890

uv sync
```

## 验证清单

```bash
# 1. 解释器与包
uv run --no-sync --directory .opencode/mcp-servers/grsai-server \
  python -c "import mcp, httpx, cryptography, grsai_server; print('OK', cryptography.__version__)"

# 2. CLI
uv run --no-sync --directory .opencode/mcp-servers/grsai-server \
  python -m grsai_server --help

# 3. 在 opencode 中调用 grsai_health_check
```

## 常见问题

### Intel Mac：cryptography 编译失败

症状：`Building cryptography==49.x` / 找不到 OpenSSL。

处理：保持本目录 `cryptography==48.0.0`，删除 `.venv` 后重新 `uv sync`。勿手动 `pip install -U cryptography`。

### `uv run --no-sync` 报缺少模块

先执行 bootstrap 或本目录 `uv sync`。

### Windows 找不到 `uv`

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# 新开终端，确认
uv --version
```

### 凭证缺失

`grsai_health_check` 返回 `unhealthy` / `api_key_configured: false`。按 credential-management 放入 `media_gen_config.json`。
