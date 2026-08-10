#!/usr/bin/env python3
"""全局 COS 资源映射缓存

跨项目共享的文件→COS URL 映射，避免同一文件重复上传。

缓存文件：~/.config/grsai/cos_cache.json

两级查找策略（兼顾命中率和效率）：
  Level 1（快速路径）：path → {hash, mtime, size}
    命中条件：路径存在且 mtime + size 匹配 → 跳过 hash 计算，直接取 URL
  Level 2（可靠兜底）：hash → {url, filename, size, uploaded_at}
    命中条件：文件内容 hash 匹配 → 捕获移动/重命名的文件
  未命中：上传 COS，写入两级索引
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime


CACHE_DIR = Path.home() / ".config" / "grsai"
CACHE_FILE = CACHE_DIR / "cos_cache.json"

MAX_ENTRIES = 5000


def _empty_cache():
    return {"version": "1.0", "updated_at": "", "entries": {}, "path_index": {}}


_cache = None
_dirty = False


def _load():
    global _cache, _dirty
    if _cache is not None:
        return _cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            if "entries" not in _cache or "path_index" not in _cache:
                _cache = _empty_cache()
        except (json.JSONDecodeError, OSError):
            _cache = _empty_cache()
    else:
        _cache = _empty_cache()
    _dirty = False
    return _cache


def _save():
    global _dirty
    if not _dirty:
        return
    cache = _load()
    cache["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(CACHE_DIR), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(CACHE_FILE))
        _dirty = False
    except Exception as e:
        os.unlink(tmp_path)
        print(f"COS cache save failed: {e}", file=sys.stderr)


def _compute_hash(local_path):
    sha256 = hashlib.sha256()
    with open(local_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _evict_if_needed():
    cache = _load()
    entries = cache["entries"]
    if len(entries) <= MAX_ENTRIES:
        return
    sorted_keys = sorted(entries.keys(), key=lambda k: entries[k].get("uploaded_at", ""))
    to_remove = sorted_keys[: len(entries) - MAX_ENTRIES]
    for key in to_remove:
        del entries[key]
    cache["path_index"] = {
        path: v for path, v in cache["path_index"].items()
        if v.get("hash") not in to_remove
    }


def lookup(local_path):
    """查找本地文件的缓存 URL。

    返回 (url, hash) 或 (None, hash)：
      - url 为 None 表示缓存未命中（hash 仍可能非 None，供 record 使用）
      - url 非 None 表示缓存命中，直接复用
    """
    cache = _load()
    abspath = os.path.abspath(local_path)

    try:
        stat = os.stat(abspath)
        mtime = stat.st_mtime
        size = stat.st_size
    except OSError:
        return None, None

    path_entry = cache["path_index"].get(abspath)
    if path_entry:
        if path_entry.get("mtime") == mtime and path_entry.get("size") == size:
            file_hash = path_entry.get("hash")
            entry = cache["entries"].get(file_hash)
            if entry:
                return entry.get("url"), file_hash
        else:
            del cache["path_index"][abspath]
            global _dirty
            _dirty = True

    file_hash = _compute_hash(abspath)
    entry = cache["entries"].get(file_hash)
    if entry:
        cache["path_index"][abspath] = {"hash": file_hash, "mtime": mtime, "size": size}
        _dirty = True
        return entry.get("url"), file_hash

    return None, file_hash


def record(local_path, url, file_hash=None):
    """记录上传成功的文件到缓存。"""
    global _dirty
    cache = _load()
    abspath = os.path.abspath(local_path)

    if file_hash is None:
        file_hash = _compute_hash(abspath)

    try:
        stat = os.stat(abspath)
        mtime = stat.st_mtime
        size = stat.st_size
    except OSError:
        return

    cache["entries"][file_hash] = {
        "url": url,
        "filename": os.path.basename(local_path),
        "size": size,
        "uploaded_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    cache["path_index"][abspath] = {"hash": file_hash, "mtime": mtime, "size": size}
    _dirty = True
    _evict_if_needed()
