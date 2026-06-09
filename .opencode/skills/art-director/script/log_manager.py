#!/usr/bin/env python3
"""日志管理模块

管理批次日志的索引表（_index.json）和全量文档（batch_*.json）。
支持自动更新、手动重建索引。
"""

import json
import os
import time
from pathlib import Path

INDEX_FILE = "_index.json"
INDEX_VERSION = "1.0"


def resolve_logs_dir(logs_dir):
    """解析日志目录，未传入时尝试使用默认路径"""
    if logs_dir is not None:
        return logs_dir
    try:
        default_logs = Path(__file__).parent.parent / "logs"
        if default_logs.exists():
            return str(default_logs)
    except Exception:
        pass
    return None


def load_index(logs_dir):
    """加载索引表，不存在则创建空索引"""
    index_path = os.path.join(logs_dir, INDEX_FILE)
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "version": INDEX_VERSION,
        "updated_at": None,
        "total_batches": 0,
        "batches": []
    }


def save_index(logs_dir, index):
    """保存索引表"""
    index_path = os.path.join(logs_dir, INDEX_FILE)
    index["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def update_index(logs_dir, batch_summary):
    """更新索引表，添加或更新批次摘要"""
    index = load_index(logs_dir)

    batch_id = batch_summary.get("batch_id")
    existing_ids = [b.get("batch_id") for b in index["batches"]]

    if batch_id in existing_ids:
        idx = existing_ids.index(batch_id)
        index["batches"][idx] = batch_summary
    else:
        index["batches"].append(batch_summary)

    index["batches"].sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    index["total_batches"] = len(index["batches"])

    return save_index(logs_dir, index)


def rebuild_index(logs_dir):
    """从全量文档重建索引表"""
    if not os.path.exists(logs_dir):
        return None

    index = {
        "version": INDEX_VERSION,
        "updated_at": None,
        "total_batches": 0,
        "batches": []
    }

    for filename in os.listdir(logs_dir):
        if not filename.startswith("batch_") or not filename.endswith(".json"):
            continue
        if filename == INDEX_FILE:
            continue

        filepath = os.path.join(logs_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            summary = {
                "batch_id": data.get("batch_id"),
                "submitted_at": data.get("submitted_at"),
                "completed_at": data.get("completed_at"),
                "total": data.get("total", 0),
                "succeeded": data.get("succeeded", 0),
                "failed": data.get("failed", 0),
                "model": data.get("model"),
                "log_file": filename
            }
            if data.get("type"):
                summary["type"] = data.get("type")
            if data.get("output_dir"):
                summary["output_dir"] = data.get("output_dir")
            if data.get("project_id"):
                summary["project_id"] = data.get("project_id")
            index["batches"].append(summary)
        except (json.JSONDecodeError, OSError):
            continue

    index["batches"].sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    index["total_batches"] = len(index["batches"])

    if save_index(logs_dir, index):
        return index
    return None