"""文件与目录指纹。只读二进制流与 stat 元信息，不解析内容。

前缀约定（数据库 CHECK 依赖）：
- sha256-{hex}
- fast-{mtime_ns}-{size}（图片）
- dir-fast-{文件数}-{总字节}-{最大mtime_ns}（目录）
"""

import hashlib
from pathlib import Path

from .templates import IMAGE_EXTS

_CHUNK = 1 << 16


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return f"sha256-{digest.hexdigest()}"


def fast_fingerprint(path) -> str:
    p = Path(path)
    if p.suffix.lower() in IMAGE_EXTS:
        st = p.stat()
        return f"fast-{st.st_mtime_ns}-{st.st_size}"
    return file_sha256(p)


def dir_stats(path) -> tuple[int, int, int]:
    files = 0
    total = 0
    max_ns = 0
    for entry in Path(path).rglob("*"):
        if entry.is_file():
            st = entry.stat()
            files += 1
            total += st.st_size
            if st.st_mtime_ns > max_ns:
                max_ns = st.st_mtime_ns
    return files, total, max_ns


def dir_fingerprint(path, stats=None) -> str:
    files, total, max_ns = stats if stats is not None else dir_stats(path)
    return f"dir-fast-{files}-{total}-{max_ns}"
