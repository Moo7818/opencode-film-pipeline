"""events.jsonl 迁移脚本 — 将现有 events 格式归一到 {timestamp, type, actor, data} 规范

功能:
  1. 修补格式不一：将 {event, project_id, data} 结构映射到 {timestamp, type, actor, data}
  2. 修复编码：修复 Unicode 转义和问号乱码
  3. 方式：原地修改 + 先备份

用法:
    python scripts/migrate_events.py <events.jsonl 路径>...

示例:
    python scripts/migrate_events.py .meta/projects/*/events.jsonl
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path


def fix_encoding(text: str) -> str:
    """修复因 PowerShell 管道导致的编码损坏"""
    if not text:
        return text
    if "?" in text and len(text) > 3:
        text = text.replace("?", "")
    text = text.strip()
    return text


def normalize_event(line: str, line_num: int) -> tuple[str | None, list[str]]:
    """将单行事件归一为标准格式
    
    Returns:
        (normalized_json_line, [warnings])
    """
    warnings = []
    stripped = line.strip()
    if not stripped:
        return None, warnings

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        warnings.append(f"  line {line_num}: JSON 解析失败，保留原行")
        return line, warnings

    if not isinstance(obj, dict):
        warnings.append(f"  line {line_num}: 非对象结构，保留原行")
        return line, warnings

    new_obj = {}

    timestamp = obj.get("timestamp") or obj.get("time") or obj.get("created_at")
    if not timestamp:
        warnings.append(f"  line {line_num}: 缺少 timestamp 字段，保留原行")
        return line, warnings
    new_obj["timestamp"] = timestamp

    event_type = obj.get("type") or obj.get("event") or obj.get("event_type")
    if not event_type:
        warnings.append(f"  line {line_num}: 缺少 type/event 字段，标记为 unknown")
        new_obj["type"] = "unknown"
    else:
        new_obj["type"] = event_type

    actor = obj.get("actor") or obj.get("initiator")
    if not actor:
        data = obj.get("data", {})
        if isinstance(data, dict):
            actor = data.get("actor")
        if not actor:
            actor = "auto"
    new_obj["actor"] = actor

    raw_data = obj.get("data", obj.get("payload", {}))
    if isinstance(raw_data, dict):
        description = raw_data.pop("description", obj.get("description", ""))
        if description:
            fixed_desc = fix_encoding(description)
            if fixed_desc:
                raw_data["description"] = fixed_desc
        raw_data.pop("from_stage", None)
        raw_data.pop("to_stage", None)
        from_val = obj.get("from") or obj.get("from_stage")
        to_val = obj.get("to") or obj.get("to_stage")
        if from_val and to_val:
            raw_data["from"] = from_val
            raw_data["to"] = to_val
        new_obj["data"] = raw_data
    else:
        if obj.get("from") and obj.get("to"):
            new_obj["data"] = {"from": obj["from"], "to": obj["to"]}
        else:
            new_obj["data"] = {}

    if obj.get("project_id"):
        new_obj["project_id"] = obj["project_id"]

    if obj.get("batch_id"):
        new_obj["batch_id"] = obj["batch_id"]

    try:
        result = json.dumps(new_obj, ensure_ascii=False, separators=(",", ":"))
        return result, warnings
    except Exception as e:
        warnings.append(f"  line {line_num}: 序列化失败 — {e}，保留原行")
        return line, warnings


def migrate_file(file_path: str) -> bool:
    """迁移单个 events.jsonl 文件"""
    path = Path(file_path)
    if not path.exists():
        print(f"  [SKIP] 文件不存在: {path}")
        return False

    backup_path = path.with_suffix(path.suffix + ".bak")
    if not backup_path.exists():
        shutil.copy2(str(path), str(backup_path))
        print(f"  [BACKUP] {backup_path.name}")

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    total_warnings = 0
    fixed_count = 0

    for i, line in enumerate(lines, 1):
        result, warnings = normalize_event(line, i)
        for w in warnings:
            print(f"  {w}")
            total_warnings += 1
        if result is not None:
            if result.rstrip("\n") != line.rstrip("\n"):
                fixed_count += 1
            new_lines.append(result + "\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"  [DONE] {path.name} — {len(lines)} rows scanned, {fixed_count} fixed, {total_warnings} warnings")
    return True


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("用法: python scripts/migrate_events.py <events.jsonl 路径>...")
        print("示例: python scripts/migrate_events.py .meta/projects/*/events.jsonl")
        return 1

    has_error = False
    for arg in args:
        path = Path(arg)
        if path.is_file():
            if not migrate_file(str(path)):
                has_error = True
        else:
            for p in sorted(path.parent.glob(path.name)):
                if p.is_file() and p.suffix == ".jsonl":
                    if not migrate_file(str(p)):
                        has_error = True

    print(f"\n迁移完成。")
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())