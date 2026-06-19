#!/usr/bin/env python3
"""跨平台 MCP Python 启动器

自动检测 .venv 中的 Python 解释器并执行目标脚本。
opencode.json 中配置：
  "command": [".opencode/scripts/mcp_python.py", ".opencode/mcp-servers/grsai-server/server.py"]
"""

import os
import sys
import subprocess
from pathlib import Path

def find_python():
    """查找 .venv 中的 Python 解释器"""
    # 从脚本位置向上查找：scripts -> .opencode -> project_root
    script_dir = Path(__file__).resolve().parent
    # .opencode/scripts 的上两级是项目根目录
    project_root = script_dir.parent.parent
    venv = project_root / ".venv"

    # Windows
    win_python = venv / "Scripts" / "python.exe"
    if win_python.exists():
        return str(win_python)

    # Unix
    unix_python = venv / "bin" / "python3"
    if unix_python.exists():
        return str(unix_python)

    print("错误：未找到虚拟环境，请先运行: uv sync", file=sys.stderr)
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("用法：mcp_python.py <script_path> [args...]", file=sys.stderr)
        sys.exit(1)

    python = find_python()
    script = sys.argv[1]
    args = sys.argv[2:]

    # 将脚本路径转换为绝对路径（如果是相对路径，基于脚本所在目录）
    if not os.path.isabs(script):
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent.parent
        script = str(project_root / script)

    result = subprocess.run([python, script] + args)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
