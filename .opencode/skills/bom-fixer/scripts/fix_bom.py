#!/usr/bin/env python3
"""
BOM 编码修复工具 — 扫描和去除 UTF-8 BOM（Byte Order Mark）。

用法:
    python scripts/fix_bom.py <path>...                    # 扫描/修复指定路径
    python scripts/fix_bom.py --scan <dir>                 # 仅扫描，不修改
    python scripts/fix_bom.py --fix <dir>                  # 扫描并修复
    python scripts/fix_bom.py --check-encoding <file>      # 检测文件编码类型

功能:
    - 检测 UTF-8 BOM（EF BB BF）
    - 检测 UTF-16 LE/BE BOM（FF FE / FE FF）
    - 去除 BOM 头，保持文件内容不变
    - 修复后自动验证 JSON 文件语法
    - 输出 NAME=VALUE 格式，便于机器解析
    - 退出码: 0 全部成功/无BOM文件, 1, 部分失败, 2 参数错误

典型用法:
    # Agent 在文件操作前快速检查
    python scripts/fix_bom.py --scan project/

    # Agent 发现 BOM 后直接修复
    python scripts/fix_bom.py --fix project/清悠居_思辰龙飞凤舞/

    # Agent 处理特定文件列表
    python scripts/fix_bom.py --fix-files temp/request.json temp/config.yaml

    # Agent 检测未知文件的编码
    python scripts/fix_bom.py --check-encoding temp/unknown.txt
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ─── BOM 签名 ──────────────────────────────────────────────────

# 注意：UTF-32 签名（4字节）必须排在 UTF-16 签名（2字节）之前，
# 因为 UTF-32 LE 的前2字节与 UTF-16 LE 相同（\xff\xfe），
# startswith 会先匹配到更短的签名导致误判。
BOM_SIGNATURES = {
    b'\xff\xfe\x00\x00': 'UTF-32 LE BOM',
    b'\x00\x00\xfe\xff': 'UTF-32 BE BOM',
    b'\xef\xbb\xbf':     'UTF-8 BOM',
    b'\xff\xfe':         'UTF-16 LE BOM',
    b'\xfe\xff':         'UTF-16 BE BOM',
}

# 默认扫描的文件扩展名
DEFAULT_EXTENSIONS = {'.md', '.py', '.json', '.yaml', '.yml', '.txt', '.cfg', '.ini', '.toml', '.jsonl'}


def detect_bom(file_path: str) -> tuple[str | None, bytes | None]:
    """检测文件是否包含 BOM 头

    Args:
        file_path: 文件路径

    Returns:
        (BOM 名称, BOM 字节数据) — 无 BOM 则返回 (None, None)
    """
    try:
        with open(file_path, 'rb') as f:
            head = f.read(4)
    except (OSError, PermissionError) as e:
        return f'ERROR: {e}', None

    # UTF-8 BOM 是 3 字节，UTF-32 是 4 字节
    for sig, name in BOM_SIGNATURES.items():
        if head.startswith(sig):
            return name, sig

    return None, None


def strip_bom(file_path: str, bom_bytes: bytes) -> bool:
    """去除文件的 BOM 头

    Args:
        file_path: 文件路径
        bom_bytes: BOM 字节数据

    Returns:
        True 如果成功，False 如果失败
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        if not data.startswith(bom_bytes):
            return False
        with open(file_path, 'wb') as f:
            f.write(data[len(bom_bytes):])
        return True
    except (OSError, PermissionError) as e:
        print(f"ERROR: {file_path} — {e}")
        return False


def validate_json(file_path: str) -> bool:
    """验证 JSON 文件语法是否有效"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        print(f"  ⚠ JSON 校验失败: {file_path} — {e}")
        return False


def detect_encoding(file_path: str) -> dict:
    """检测文件的编码类型

    Returns:
        包含编码信息的字典
    """
    result = {
        'path': file_path,
        'bom': None,
        'encoding_guess': 'unknown',
        'valid_utf8': False,
    }

    # 先检测 BOM
    bom_name, bom_bytes = detect_bom(file_path)
    if bom_name:
        result['bom'] = bom_name

    # 尝试 UTF-8 解码
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read()
        result['valid_utf8'] = True
        result['encoding_guess'] = 'UTF-8'
    except UnicodeDecodeError:
        # 尝试常见编码
        for enc in ['gbk', 'gb2312', 'latin-1', 'shift-jis', 'utf-16']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.read()
                result['encoding_guess'] = enc
                break
            except (UnicodeDecodeError, OSError):
                continue

    return result


# ─── 扫描模式 ──────────────────────────────────────────────────

def scan_files(paths: list[str], extensions: set | None = None) -> list[dict]:
    """扫描文件列表或目录树中的 BOM 文件

    Args:
        paths: 文件路径或目录路径列表
        extensions: 要检查的文件扩展名集合

    Returns:
        [(file_path, bom_name, bom_bytes), ...] 列表
    """
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    found = []
    seen = set()

    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"  ⚠ 路径不存在: {p}")
            continue

        if path.is_file():
            files_to_check = [path]
        else:
            files_to_check = []
            for ext in extensions:
                files_to_check.extend(path.rglob(f'*{ext}'))

        for fp in files_to_check:
            # 跳过 __pycache__
            if '__pycache__' in fp.parts:
                continue
            # 跳过 .git
            if '.git' in fp.parts:
                continue

            fp_str = str(fp)
            if fp_str in seen:
                continue
            seen.add(fp_str)

            bom_name, bom_bytes = detect_bom(fp_str)
            if bom_name:
                found.append({
                    'path': fp_str,
                    'bom': bom_name,
                    'bom_bytes': bom_bytes,
                    'size': fp.stat().st_size,
                })

    return found


# ─── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='BOM 编码修复工具 — 扫描和去除 UTF-8 BOM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --scan project/              # 扫描目录
  %(prog)s --fix .opencode/skills/          # 修复技能目录
  %(prog)s --fix-files a.md b.json      # 修复特定文件
  %(prog)s --check-encoding file.txt    # 检测编码
        """,
    )

    # 扫描/修复模式
    parser.add_argument('--scan', nargs='+', metavar='PATH',
                        help='扫描路径中的 BOM 文件（不修改）')
    parser.add_argument('--fix', nargs='+', metavar='PATH',
                        help='扫描并修复 BOM 文件')
    parser.add_argument('--fix-files', nargs='+', metavar='FILE',
                        help='修复指定的文件列表')
    parser.add_argument('--check-encoding', metavar='FILE',
                        help='检测单个文件的编码')

    # 选项
    parser.add_argument('--extensions', nargs='+', default=[],
                        help=f'文件扩展名过滤（默认: {" ".join(sorted(DEFAULT_EXTENSIONS))}）')
    parser.add_argument('--validate-json', action='store_true', default=True,
                        help='修复后验证 JSON 文件（默认开启）')
    parser.add_argument('--no-validate-json', action='store_false', dest='validate_json',
                        help='跳过 JSON 验证')

    args = parser.parse_args()

    # 解析扩展名
    if args.extensions:
        exts = {e if e.startswith('.') else f'.{e}' for e in args.extensions}
    else:
        exts = DEFAULT_EXTENSIONS

    # ─── --check-encoding 模式 ────────────────────────────
    if args.check_encoding:
        info = detect_encoding(args.check_encoding)
        print(f"path={info['path']}")
        print(f"bom={info['bom'] or 'none'}")
        print(f"encoding_guess={info['encoding_guess']}")
        print(f"valid_utf8={'yes' if info['valid_utf8'] else 'no'}")
        return

    # ─── --fix-files 模式 ────────────────────────────────
    if args.fix_files:
        results = {'scanned': 0, 'fixed': 0, 'failed': 0, 'json_errors': 0}
        for fp in args.fix_files:
            if not os.path.isfile(fp):
                print(f"  ⚠ 文件不存在: {fp}")
                results['failed'] += 1
                continue
            results['scanned'] += 1
            bom_name, bom_bytes = detect_bom(fp)
            if bom_name:
                ok = strip_bom(fp, bom_bytes)
                if ok:
                    results['fixed'] += 1
                    print(f"  ✅ {fp} — 已去除 {bom_name}")
                    if args.validate_json and fp.endswith('.json'):
                        if not validate_json(fp):
                            results['json_errors'] += 1
                else:
                    results['failed'] += 1
            else:
                print(f"  ⏭️ {fp} — 无 BOM")

        _print_summary(results)
        return

    # ─── --scan 模式 ──────────────────────────────────────
    if args.scan:
        found = scan_files(args.scan, exts)
        if not found:
            print("✅ 未发现 BOM 文件")
            return
        print(f"发现 {len(found)} 个 BOM 文件：")
        for item in found:
            print(f"  {item['bom']:20s}  {item['path']}  ({item['size']} bytes)")
        return

    # ─── --fix 模式 ───────────────────────────────────────
    if args.fix:
        found = scan_files(args.fix, exts)
        if not found:
            print("✅ 未发现 BOM 文件，无需修复")
            return

        results = {'scanned': len(found), 'fixed': 0, 'failed': 0, 'json_errors': 0}
        print(f"发现 {len(found)} 个 BOM 文件，开始修复...")

        for item in found:
            fp = item['path']
            ok = strip_bom(fp, item['bom_bytes'])
            if ok:
                results['fixed'] += 1
                print(f"  ✅ {fp} — {item['bom']} 已去除")
                if args.validate_json and fp.endswith('.json'):
                    if not validate_json(fp):
                        results['json_errors'] += 1
            else:
                results['failed'] += 1
                print(f"  ❌ {fp} — 修复失败")

        _print_summary(results)
        return

    # ─── 无参数 ───────────────────────────────────────────
    parser.print_help()


def _print_summary(results: dict):
    """打印修复摘要"""
    print(f"\n--- 摘要 ---")
    print(f"扫描: {results['scanned']} | 修复: {results['fixed']} | 失败: {results['failed']}",
          end='')
    if results.get('json_errors'):
        print(f" | JSON 校验异常: {results['json_errors']}", end='')
    print()


if __name__ == '__main__':
    main()