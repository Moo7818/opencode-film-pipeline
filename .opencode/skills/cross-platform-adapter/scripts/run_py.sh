#!/usr/bin/env bash
# run_py.sh — Cross-platform Python launcher for Bash.
#
# Automatically detects the correct Python command (python3 on Unix, python on
# Windows Git Bash) and invokes it with the given script and arguments.
#
# Usage:
#   source run_py.sh            # sources the function
#   run_py script.py [arg ...]  # calls Python with the script
#
# Returns the exit code from the Python process.

set -euo pipefail

run_py() {
    local script="$1"
    shift

    # Try python3 first, fall back to python
    local python_cmd
    if command -v python3 >/dev/null 2>&1; then
        python_cmd="python3"
    elif command -v python >/dev/null 2>&1; then
        python_cmd="python"
    else
        echo "[ERROR] 找不到 Python 解释器。请安装 Python 3.8+ 并加入 PATH。" >&2
        return 1
    fi

    # Resolve script path
    if [[ ! -f "$script" ]]; then
        echo "[ERROR] 找不到脚本: $script" >&2
        return 1
    fi

    "$python_cmd" "$script" "$@"
    return $?
}
