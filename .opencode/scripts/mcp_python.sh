#!/bin/bash
# 跨平台 Python 启动脚本
# 用于 opencode MCP 服务器配置，自动检测 .venv 中的 Python
#
# 用法：./scripts/mcp_python.sh <script_path> [args...]
# 示例：./scripts/mcp_python.sh .opencode/mcp-servers/grsai-server/server.py

set -e

# 获取项目根目录（脚本所在目录的上两级：scripts -> .opencode -> 项目根）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 虚拟环境路径
VENV_DIR="$PROJECT_ROOT/.venv"

# 检测 Python 路径
if [ -d "$VENV_DIR/bin" ]; then
    # Unix (macOS/Linux)
    PYTHON="$VENV_DIR/bin/python3"
elif [ -d "$VENV_DIR/Scripts" ]; then
    # Windows (Git Bash/WSL)
    PYTHON="$VENV_DIR/Scripts/python.exe"
else
    echo "错误：未找到虚拟环境，请先运行: uv sync" >&2
    exit 1
fi

# 检查 Python 是否存在
if [ ! -f "$PYTHON" ]; then
    echo "错误：Python 不存在于 $PYTHON" >&2
    echo "请先运行: uv sync" >&2
    exit 1
fi

# 执行目标脚本
exec "$PYTHON" "$@"
