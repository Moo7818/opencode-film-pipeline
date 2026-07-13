#!/usr/bin/env python3
"""产物注册脚本 — 注册产物到 manifest.json 并追加事件到 events.jsonl，两步均校验

用法:
    python register_artifact.py --manifest-path <path> --events-path <path> \
        --type <type> --name <name> --artifact-path <path> --stage <stage> \
        [--actor project-coordinator] [--artifact-id <id>] [--tags tag1 tag2] \
        [--project-id <id>] [--pass-thru]

功能:
    1. 检查产物文件存在
    2. 调用同目录 hash.py --fast 计算哈希和大小（解析 HASH= 和 SIZE= 行）
    3. 读取 manifest.json（不存在则创建空的）
    4. 自动生成 artifact_id（art_001 格式，查找现有最大编号+1）
    5. 如果已有相同 path 的条目，标记为 deprecated
    6. 追加新产物条目
    7. 写回 manifest.json
    8. 调用 validate.py 校验 manifest.json
    9. 构建 artifact.created 事件，追加到 events.jsonl
    10. 调用 validate.py 校验 events.jsonl
    11. 输出完成信息

退出码: 0 成功, 1 失败
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime


def run_validate(scripts_dir: str, file_path: str) -> tuple[int, str]:
    """调用 validate.py 校验指定文件，返回 (退出码, 输出文本)"""
    validate_script = os.path.join(scripts_dir, "validate.py")
    result = subprocess.run(
        [sys.executable, validate_script, file_path],
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def main() -> int:
    parser = argparse.ArgumentParser(description="注册产物到 manifest.json + 追加事件 + 全链校验")
    parser.add_argument("--manifest-path", required=True, help="manifest.json 路径")
    parser.add_argument("--events-path", required=True, help="events.jsonl 路径")
    parser.add_argument("--type", required=True, help="产物类型")
    parser.add_argument("--name", required=True, help="产物名称")
    parser.add_argument("--artifact-path", required=True, help="产物文件路径")
    parser.add_argument("--stage", required=True, help="所属阶段")
    parser.add_argument("--actor", default="project-coordinator", help="触发者，默认 project-coordinator（必须是 opencode.json 中定义的 skill name）")
    parser.add_argument("--artifact-id", default=None, help="产物 ID，不提供则自动生成")
    parser.add_argument("--tags", nargs="*", default=None, help="标签列表")
    parser.add_argument("--project-id", default=None, help="关联项目 UUID")
    parser.add_argument(
        "--pass-thru",
        action="store_true",
        help="返回产物注册结果 JSON",
    )
    args = parser.parse_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().astimezone().isoformat()

    # 1. 检查产物文件存在
    if not os.path.exists(args.artifact_path):
        print(f"[ERROR] 产物文件不存在: {args.artifact_path}")
        return 1

    # 2. 调用 hash.py --fast 计算哈希和大小
    hash_script = os.path.join(scripts_dir, "hash.py")
    hash_result = subprocess.run(
        [sys.executable, hash_script, "--fast", args.artifact_path],
        capture_output=True,
        text=True,
    )
    if hash_result.returncode != 0:
        print(f"[ERROR] 哈希计算失败: {args.artifact_path}")
        output = hash_result.stdout + hash_result.stderr
        for line in output.splitlines():
            print(line)
        return 1

    hash_value = ""
    size_value = 0
    for line in (hash_result.stdout + hash_result.stderr).splitlines():
        if line.startswith("HASH="):
            hash_value = line[len("HASH="):]
        elif line.startswith("SIZE="):
            try:
                size_value = int(line[len("SIZE="):])
            except ValueError:
                pass

    if not hash_value:
        print("[ERROR] 无法解析哈希结果")
        return 1

    print(f"[HASH] {args.artifact_path} → {hash_value} ({size_value} bytes)")

    # 3. 读取 manifest.json（不存在则创建空的）
    if not os.path.exists(args.manifest_path):
        manifest: dict = {"_version": 1, "artifacts": []}
    else:
        try:
            with open(args.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ERROR] 无法读取 manifest.json: {e}")
            return 1
        if "artifacts" not in manifest or manifest["artifacts"] is None:
            manifest["artifacts"] = []

    # 4. 自动生成 artifact_id（art_001 格式）
    artifact_id = args.artifact_id
    if not artifact_id:
        max_num = 0
        for art in manifest["artifacts"]:
            aid = art.get("id", "")
            m = re.match(r"^art_(\d+)$", aid)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
        artifact_id = f"art_{max_num + 1:03d}"

    # 5. 如果已有相同 path 的条目，标记为 deprecated
    for i, art in enumerate(manifest["artifacts"]):
        if art.get("path") == args.artifact_path:
            old_id = art.get("id", "")
            manifest["artifacts"][i]["status"] = "deprecated"
            print(f"[DEPRECATE] {old_id} — 旧条目标记为 deprecated")
            break

    # 6. 追加新产物条目
    artifact: dict = {
        "id": artifact_id,
        "type": args.type,
        "name": args.name,
        "path": args.artifact_path,
        "stage": args.stage,
        "status": "final",
        "created_at": timestamp,
        "updated_at": timestamp,
        "hash": hash_value,
        "size": size_value,
    }
    if args.tags and len(args.tags) > 0:
        artifact["tags"] = args.tags
    manifest["artifacts"].append(artifact)

    # 7. 写回 manifest.json
    try:
        with open(args.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[ERROR] manifest.json 写入失败: {args.manifest_path}")
        print(f"  {e}")
        return 1

    print(f"[MANIFEST] {args.manifest_path} ← {artifact_id} ({args.type})")

    # 8. 调用 validate.py 校验 manifest.json
    vc, vout = run_validate(scripts_dir, args.manifest_path)
    if vc != 0:
        print("[VALIDATE] manifest.json — 失败")
        for line in vout.splitlines():
            print(line)
        return 1
    print("[VALIDATE] manifest.json — 通过")

    # 9. 构建 artifact.created 事件，追加到 events.jsonl
    event_data = {
        "artifact_id": artifact_id,
        "type": args.type,
        "path": args.artifact_path,
        "hash": hash_value,
        "size": size_value,
    }
    event: dict = {
        "timestamp": timestamp,
        "type": "artifact.created",
        "actor": args.actor,
        "data": event_data,
    }
    if args.project_id:
        event["project_id"] = args.project_id

    event_json = json.dumps(event, ensure_ascii=False, separators=(",", ":"))

    try:
        with open(args.events_path, "a", encoding="utf-8") as f:
            f.write(event_json + "\n")
    except OSError as e:
        print(f"[ERROR] 事件写入失败: {args.events_path}")
        print(f"  {e}")
        return 1

    print(f"[EVENT] {args.events_path} ← artifact.created ({artifact_id})")

    # 10. 调用 validate.py 校验 events.jsonl
    vc2, vout2 = run_validate(scripts_dir, args.events_path)
    if vc2 != 0:
        print("[VALIDATE] events.jsonl — 失败")
        for line in vout2.splitlines():
            print(line)
        return 1
    print("[VALIDATE] events.jsonl — 通过")

    # 11. 输出完成信息
    print(f"[DONE] 产物注册完成: {args.name} → {args.artifact_path}")

    if args.pass_thru:
        result_obj = {
            "artifact_id": artifact_id,
            "hash": hash_value,
            "size": size_value,
        }
        print(json.dumps(result_obj, ensure_ascii=False, separators=(",", ":")))

    return 0


if __name__ == "__main__":
    sys.exit(main())
