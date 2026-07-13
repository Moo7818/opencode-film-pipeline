#!/usr/bin/env python3
"""追加事件脚本 — 向 events.jsonl 追加一条事件并自动校验

用法:
    python append_event.py --events-path <path> --timestamp <iso> --type <type> \
        --actor <actor> --data '<json>' [--project-id <id>] [--batch-id <id>] [--pass-thru]

功能:
    - 构建事件 dict（data 为 JSON 字符串，会被解析为对象）
    - 序列化为单行紧凑 JSON 追加到 events.jsonl
    - 自动调用同目录 validate.py 校验语法
    - 输出 [EVENT] / [VALIDATE] 标签信息
    - 退出码: 0 成功, 1 失败
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="追加事件到 events.jsonl + 自动校验")
    parser.add_argument("--events-path", required=True, help="events.jsonl 路径")
    parser.add_argument("--timestamp", required=True, help="ISO 8601 时间戳")
    parser.add_argument("--type", required=True, help="事件类型")
    parser.add_argument("--actor", required=True, help="触发者")
    parser.add_argument("--data", required=True, help="事件详情 JSON 字符串")
    parser.add_argument("--project-id", default=None, help="关联项目 UUID")
    parser.add_argument("--batch-id", default=None, help="关联批次 ID")
    parser.add_argument(
        "--pass-thru",
        action="store_true",
        help="返回事件 JSON",
    )
    args = parser.parse_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # 解析 data JSON 字符串
    try:
        data_obj = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"[ERROR] --data 不是有效的 JSON: {e}")
        return 1

    # 构建事件 dict
    event: dict = {
        "timestamp": args.timestamp,
        "type": args.type,
        "actor": args.actor,
        "data": data_obj,
    }
    if args.project_id:
        event["project_id"] = args.project_id
    if args.batch_id:
        event["batch_id"] = args.batch_id

    # 序列化为单行紧凑 JSON
    json_line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))

    # 追加到 events.jsonl
    try:
        with open(args.events_path, "a", encoding="utf-8") as f:
            f.write(json_line + "\n")
    except OSError as e:
        print(f"[ERROR] 写入事件失败: {args.events_path}")
        print(f"  {e}")
        return 1

    print(f"[EVENT] {args.events_path} ← {args.type} ({args.actor})")

    # 调用 validate.py 校验
    validate_script = os.path.join(scripts_dir, "validate.py")
    result = subprocess.run(
        [sys.executable, validate_script, args.events_path],
        capture_output=True,
        text=True,
    )
    validate_exit_code = result.returncode

    if validate_exit_code == 0:
        print(f"[VALIDATE] {args.events_path} — 通过")
    else:
        print(f"[VALIDATE] {args.events_path} — 失败")
        output = result.stdout + result.stderr
        for line in output.splitlines():
            print(line)

    if args.pass_thru:
        passthrough = {
            "event": event,
            "validate": validate_exit_code == 0,
        }
        print(json.dumps(passthrough, ensure_ascii=False, separators=(",", ":")))

    return validate_exit_code


if __name__ == "__main__":
    sys.exit(main())
