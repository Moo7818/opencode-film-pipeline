#!/usr/bin/env bash
# 虚拟环境初始化（兼容旧入口）
# 实际逻辑已合并至 bootstrap_mcp.sh（根 .venv + grsai-server .venv）
#
# 用法：./.opencode/scripts/setup_venv.sh
# 等价：./.opencode/scripts/bootstrap_mcp.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/bootstrap_mcp.sh" "$@"
