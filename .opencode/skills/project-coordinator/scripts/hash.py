"""文件哈希计算脚本 — 计算 SHA-256 和文件大小

用法:
    python scripts/hash.py [--fast] <file_path>...

功能:
    - 计算 SHA-256 哈希（二进制流，不做内容解析）
    - 获取文件大小（字节数）
    - 支持多个文件批量计算
    - 输出 NAME=VALUE 格式，便于机器解析
    - 退出码: 0 全部成功, 1 存在错误

--fast 模式：
    对图片文件（.png/.jpg/.jpeg/.gif/.webp）跳过全量 SHA-256，改用 mtime+size
    快速指纹，避免读入多 MB 图片文件。文本文件始终使用完整 SHA-256。
    输出 HASH 格式: "fast-{mtime_ns}-{size}" 或 "sha256-{hex}"

与 validate.py 配合使用:
    1. hash.py   — 计算元数据（哈希 + 大小）
    2. validate.py — 校验 JSON/JSONL 语法
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys


BINARY_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


def is_image_file(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in BINARY_IMAGE_EXTENSIONS


def compute_file_hash(file_path: str, fast: bool = False) -> tuple:
    """计算文件的 SHA-256 哈希和大小

    fast=True 且文件为图片类型时，跳过 SHA-256，改用 mtime+size 快速指纹。
    只读二进制流，不做内容解析。

    Returns:
        (hash_value, file_size_bytes)
        - 完整 SHA-256: "sha256-{hex}"
        - 快速指纹: "fast-{mtime_ns}-{size}"

    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无读取权限
        OSError: 其他文件系统错误
    """
    stat_info = os.stat(file_path)
    file_size = stat_info.st_size

    if fast and is_image_file(file_path):
        mtime_ns = stat_info.st_mtime_ns
        return f"fast-{mtime_ns}-{file_size}", file_size

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
            file_size += len(chunk)
    return f"sha256-{sha256.hexdigest()}", file_size


def process_file(file_path: str, fast: bool = False) -> list:
    """处理单个文件，返回输出行列表"""
    lines = []

    if not os.path.exists(file_path):
        lines.append(f"NOT_FOUND={file_path}")
        return lines

    if not os.path.isfile(file_path):
        lines.append(f"NOT_FILE={file_path}")
        return lines

    try:
        hex_hash, file_size = compute_file_hash(file_path, fast=fast)
        lines.append(f"PATH={os.path.abspath(file_path)}")
        lines.append(f"HASH={hex_hash}")
        lines.append(f"SIZE={file_size}")
    except PermissionError:
        lines.append(f"PERMISSION_DENIED={file_path}")
    except OSError as e:
        lines.append(f"ERROR={file_path} — {e}")

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="文件哈希计算工具")
    parser.add_argument("files", nargs="+", help="文件路径列表")
    parser.add_argument("--fast", action="store_true", help="图片文件跳过全量哈希，使用 mtime+size 快速指纹")
    args = parser.parse_args()

    if not args.files:
        print("用法: python scripts/hash.py [--fast] <file_path>...")
        return 1

    has_error = False
    is_first = True

    for arg in args.files:
        lines = process_file(arg, fast=args.fast)

        if not is_first:
            print("---")

        for line in lines:
            if line.startswith("NOT_FOUND=") or line.startswith("NOT_FILE=") or line.startswith("PERMISSION_DENIED=") or line.startswith("ERROR="):
                has_error = True
            print(line)

        is_first = False

    print(flush=True)
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
