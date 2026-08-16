#!/usr/bin/env bash
# bootstrap_mcp.sh — 一键部署根项目 + grsai-server MCP 依赖（macOS / Linux）
#
# 用法（在仓库任意位置均可，推荐仓库根）：
#   ./.opencode/scripts/bootstrap_mcp.sh
#   ./.opencode/scripts/bootstrap_mcp.sh --skip-root
#   UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ./.opencode/scripts/bootstrap_mcp.sh
#
# 所有依赖安装到项目内 .venv，不写用户全局 site-packages。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GRSAI_DIR="$PROJECT_ROOT/.opencode/mcp-servers/grsai-server"
META_DIR="$PROJECT_ROOT/.opencode/mcp-servers/meta-server"
SKIP_ROOT=0

for arg in "$@"; do
  case "$arg" in
    --skip-root) SKIP_ROOT=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
  esac
done

cd "$PROJECT_ROOT"

echo "=== MCP / 项目环境 Bootstrap ==="
echo "项目根: $PROJECT_ROOT"
echo "平台:   $(uname -s) $(uname -m)"

# --- 前置：uv ---
if ! command -v uv >/dev/null 2>&1; then
  echo "错误: 未找到 uv。"
  echo "  安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  然后重新打开终端，再运行本脚本。"
  exit 1
fi
echo "uv: $(uv --version)"

if [ -n "${UV_INDEX_URL:-}" ]; then
  echo "镜像: UV_INDEX_URL=$UV_INDEX_URL"
fi
if [ -n "${HTTPS_PROXY:-}${HTTP_PROXY:-}${ALL_PROXY:-}" ]; then
  echo "代理: HTTPS_PROXY=${HTTPS_PROXY:-} HTTP_PROXY=${HTTP_PROXY:-} ALL_PROXY=${ALL_PROXY:-}"
fi

# --- 根项目 .venv ---
if [ "$SKIP_ROOT" -eq 0 ]; then
  echo ""
  echo "→ [1/2] 同步根项目依赖 → .venv/"
  uv sync
  if [ -x "$PROJECT_ROOT/.venv/bin/python3" ]; then
    ROOT_PY="$PROJECT_ROOT/.venv/bin/python3"
  elif [ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]; then
    ROOT_PY="$PROJECT_ROOT/.venv/Scripts/python.exe"
  else
    echo "错误: 根 .venv 中未找到 Python"
    exit 1
  fi
  echo "  Python: $("$ROOT_PY" --version 2>&1)"
else
  echo ""
  echo "→ [1/2] 跳过根项目 (--skip-root)"
fi

# --- grsai-server ---
echo ""
echo "→ [2/2] 同步 grsai-server → .opencode/mcp-servers/grsai-server/.venv/"
if [ ! -f "$GRSAI_DIR/pyproject.toml" ]; then
  echo "错误: 找不到 $GRSAI_DIR/pyproject.toml"
  exit 1
fi
(
  cd "$GRSAI_DIR"
  uv sync
)

# --- meta-server ---
echo ""
echo "→ 同步 meta-server → .opencode/mcp-servers/meta-server/.venv/"
if [ ! -f "$META_DIR/pyproject.toml" ]; then
  echo "错误: 找不到 $META_DIR/pyproject.toml"
  exit 1
fi
(
  cd "$META_DIR"
  uv sync
)

echo ""
echo "→ 验证 grsai-server 导入与 CLI"
uv run --no-sync --directory "$GRSAI_DIR" python -c "
import sys
import cryptography
import httpx
import mcp
import grsai_server
from grsai_server import server as _s
assert cryptography.__version__.startswith('48.'), cryptography.__version__
print('  python     :', sys.version.split()[0], sys.platform)
print('  cryptography:', cryptography.__version__)
print('  httpx      :', httpx.__version__)
print('  mcp        : OK')
print('  grsai_server: OK')
"

uv run --no-sync --directory "$GRSAI_DIR" python -m grsai_server --help >/dev/null
echo "  --help      : OK"

# --- 凭证提示 ---
CRED="$PROJECT_ROOT/.opencode/credentials/media_gen_config.json"
echo ""
if [ -f "$CRED" ]; then
  echo "凭证: 已找到 $CRED"
else
  echo "警告: 未找到凭证文件:"
  echo "  $CRED"
  echo "  见 .opencode/rules/credential-management.md"
fi

# --- 汇总：MCP server venv 状态 ---
echo ""
echo "→ MCP server venv 状态汇总"
for d in "$GRSAI_DIR" "$META_DIR"; do
  if [ -x "$d/.venv/bin/python3" ] || [ -x "$d/.venv/Scripts/python.exe" ]; then
    echo "  就绪: $d/.venv"
  else
    echo "  缺失: $d/.venv"
  fi
done

echo ""
echo "=== Bootstrap 完成 ==="
echo "下一步:"
echo "  1. 确认 media_gen_config.json 已就位"
echo "  2. 重启 opencode（MCP 命令见 opencode.json → grsai-mcp）"
echo ""
echo "手动验证:"
echo "  uv run --no-sync --directory .opencode/mcp-servers/grsai-server -m grsai_server --help"
