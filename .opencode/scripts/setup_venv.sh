#!/bin/bash
# 虚拟环境初始化脚本
# 自动检测平台并配置 opencode.json 中的 Python 路径
#
# 用法：./scripts/setup_venv.sh

set -e

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== 虚拟环境初始化 ==="

# 检查 uv 是否可用
if ! command -v uv &> /dev/null; then
    echo "错误：未找到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✓ 找到 uv: $(uv --version)"

# 检查虚拟环境是否存在
if [ -d ".venv" ]; then
    echo "✓ 虚拟环境已存在"
else
    echo "→ 创建虚拟环境..."
    uv sync
    echo "✓ 虚拟环境创建完成"
fi

# 检测 Python 路径
if [ -f ".venv/bin/python3" ]; then
    PYTHON_PATH=".venv/bin/python3"
elif [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON_PATH=".venv/Scripts/python.exe"
else
    echo "错误：虚拟环境 Python 不存在"
    exit 1
fi

echo "✓ Python 路径: $PYTHON_PATH"

# 生成 .env 文件供 opencode.json 使用
cat > .env << EOF
# 自动生成 - 请勿手动编辑
# 运行 ./scripts/setup_venv.sh 重新生成
VENV_PYTHON=$PROJECT_ROOT/$PYTHON_PATH
EOF

echo "✓ 已生成 .env 文件"

# 检查 opencode.json 中的 MCP Python 路径是否需要更新
if ! grep -q "$PROJECT_ROOT/.venv/bin/python3" opencode.json 2>/dev/null; then
    echo ""
    echo "⚠️  opencode.json 中的 MCP Python 路径可能未更新"
    echo "   建议更新为: $PROJECT_ROOT/.venv/bin/python3"
    echo "   （注意：{env:*} 在 config 解析时 .env 尚未加载，须使用绝对路径）"
    echo ""
fi

echo ""
echo "=== 初始化完成 ==="
echo ""
echo "下一步："
echo "  1. 确保 .env 文件中的路径正确"
echo "  2. 重启 opencode 使配置生效"
