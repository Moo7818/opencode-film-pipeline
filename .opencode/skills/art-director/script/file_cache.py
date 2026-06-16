#!/usr/bin/env python3
# DEPRECATED: 此文件已被 .opencode/mcp-servers/grsai-server/ 中的对应模块替代。
# 图像生成 API → grsai_client.py
# COS 上传 → cos_client.py
# 凭证管理 → config.py
# 批量生成 → grsai_batch_generate MCP tool
# 将在后续版本删除。
"""文件映射缓存模块

提供本地文件与 COS 存储桶 URL 的智能映射缓存，避免相同素材重复上传。
使用 SHA256 哈希进行文件去重。
"""

import hashlib
import json
import os
import time

from cos_uploader import upload_to_cos

FILE_MAP_FILE = "_file_map.json"
FILE_MAP_VERSION = "1.0"


def load_file_map(logs_dir):
    """加载文件映射表，不存在则创建空映射"""
    map_path = os.path.join(logs_dir, FILE_MAP_FILE)
    if os.path.exists(map_path):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "version": FILE_MAP_VERSION,
        "updated_at": None,
        "files": {}
    }


def save_file_map(logs_dir, file_map):
    """保存文件映射表"""
    map_path = os.path.join(logs_dir, FILE_MAP_FILE)
    file_map["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(file_map, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def compute_file_hash(local_path):
    """计算本地文件的 SHA256 哈希值"""
    sha256 = hashlib.sha256()
    try:
        with open(local_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except OSError:
        return None


def query_file_map(file_map, local_path):
    """查询文件映射表，命中缓存则返回远程 URL"""
    file_hash = compute_file_hash(local_path)
    if not file_hash:
        return None

    if file_hash in file_map.get("files", {}):
        entry = file_map["files"][file_hash]
        if entry.get("local_path") == local_path:
            return entry["remote_url"]

    return None


def update_file_map(file_map, local_path, remote_url, cos_path):
    """更新文件映射表，添加新的映射关系"""
    file_hash = compute_file_hash(local_path)
    if not file_hash:
        return False

    if "files" not in file_map:
        file_map["files"] = {}

    file_map["files"][file_hash] = {
        "local_path": local_path,
        "remote_url": remote_url,
        "cos_path": cos_path,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_hash": file_hash,
    }
    return True


def is_local_file(path):
    """判断路径是否为本地文件"""
    return os.path.exists(path) and os.path.isfile(path)


def process_urls(urls, cos_config=None, timestamp=None, file_map=None, logs_dir=None):
    """处理 URL 列表，将本地文件路径替换为公开 URL

    使用文件映射缓存避免重复上传，相同文件（SHA256 相同）只上传一次。
    """
    if not urls:
        return urls, []

    result = []
    uploaded_refs = []

    if file_map is None and logs_dir:
        file_map = load_file_map(logs_dir)

    for url in urls:
        if is_local_file(url):
            if not cos_config:
                raise ValueError(
                    "检测到本地文件路径但未配置腾讯云 COS。"
                    "请在 ~/.trae-cn/media_gen_config.json 或环境变量中配置："
                    "TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY, "
                    "TENCENT_COS_BUCKET, TENCENT_COS_REGION"
                )

            cached_url = None
            if file_map:
                cached_url = query_file_map(file_map, url)

            if cached_url:
                result.append(cached_url)
                uploaded_refs.append({
                    "local": url,
                    "remote": cached_url,
                    "cached": True
                })
            else:
                public_url = upload_to_cos(
                    url,
                    timestamp=timestamp,
                    secret_id=cos_config['secret_id'],
                    secret_key=cos_config['secret_key'],
                    bucket=cos_config['bucket'],
                    region=cos_config['region'],
                )
                result.append(public_url)
                uploaded_refs.append({
                    "local": url,
                    "remote": public_url,
                    "cached": False
                })

                if file_map and logs_dir:
                    cos_path = f"/{timestamp}_{os.path.basename(url)}" if timestamp else f"/{os.path.basename(url)}"
                    if update_file_map(file_map, url, public_url, cos_path):
                        save_file_map(logs_dir, file_map)
        else:
            result.append(url)

    return result, uploaded_refs