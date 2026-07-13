#!/usr/bin/env python3
"""写文件 + 自动校验脚本 — 写入文件后调用 validate.py 校验语法

用法:
    python write_validate.py --path <file_path> --value <content> [--encoding utf-8] [--pass-thru]

功能:
    - 将内容写入指定文件
    - 自动调用同目录 validate.py 校验语法
    - 输出 [WRITE] / [VALIDATE] 标签信息
    - 退出码: 0 成功, 1 失败
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="写文件 + 自动校验")
    parser.add_argument("--path", required=True, help="目标文件路径")
    parser.add_argument("--value", required=True, help="写入内容")
    parser.add_argument(
        "--encoding", default="utf-8", help="文件编码，默认 utf-8"
    )
    parser.add_argument(
        "--pass-thru",
        action="store_true",
        help="返回校验结果 JSON",
    )
    args = parser.parse_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # 写入文件
    try:
        with open(args.path, "w", encoding=args.encoding) as f:
            f.write(args.value)
    except OSError as e:
        print(f"[ERROR] 写入失败: {args.path}")
        print(f"  {e}")
        return 1

    print(f"[WRITE] {args.path}")

    # 调用 validate.py 校验
    validate_script = os.path.join(scripts_dir, "validate.py")
    result = subprocess.run(
        [sys.executable, validate_script, args.path],
        capture_output=True,
        text=True,
    )
    validate_exit_code = result.returncode

    if validate_exit_code == 0:
        print(f"[VALIDATE] {args.path} — 通过")
    else:
        print(f"[VALIDATE] {args.path} — 失败")
        output = result.stdout + result.stderr
        for line in output.splitlines():
            print(line)

    if args.pass_thru:
        import json

        passthrough = {
            "validate": validate_exit_code == 0,
            "output": (result.stdout + result.stderr).strip(),
        }
        print(json.dumps(passthrough, ensure_ascii=False))

    return validate_exit_code


if __name__ == "__main__":
    sys.exit(main())
