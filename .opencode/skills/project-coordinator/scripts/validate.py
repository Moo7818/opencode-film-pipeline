"""JSON/JSONL 校验脚本 — 在写入前检测语法错误

用法:
    python validate.py <file_path>...

功能:
    - 校验 .json 文件语法
    - 校验 .jsonl 文件每行语法
    - 报告精确到行号的错误信息
    - 退出码: 0 全部通过, 1 存在错误

此脚本应内嵌在统筹 agent 的操作流程中，每次写 JSON 后自动调用。
"""

import json
import sys
from pathlib import Path


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.decode("utf-8")


def validate_json(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = _read_text(path)
        if not text.strip():
            errors.append(f"  [ERROR] 文件为空: {path}")
            return errors
        json.loads(text)
    except json.JSONDecodeError as e:
        lineno = e.lineno
        colno = e.colno
        msg = e.msg
        context_lines = text.splitlines()
        errors.append(f"  [ERROR] {path.name}:{lineno}:{colno} — {msg}")
        for i in range(max(0, lineno - 2), min(len(context_lines), lineno + 1)):
            marker = ">>>" if i + 1 == lineno else "   "
            errors.append(f"    {marker} {i+1:>4}: {context_lines[i]}")
        if lineno > 0 and colno > 0:
            errors.append(f"          {' ' * (colno + 9)}^")
    except Exception as e:
        errors.append(f"  [ERROR] {path.name}: {e}")
    return errors


def validate_jsonl(path: Path) -> list[str]:
    errors: list[str] = []
    text = _read_text(path)
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError as e:
            errors.append(f"  [ERROR] {path.name}:{i}:{e.colno} — {e.msg}")
            errors.append(f"    >>> {i:>4}: {stripped[:120]}")
    if not errors and not lines:
        errors.append(f"  [WARN] 文件为空: {path}")
    return errors


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("用法: python validate.py <file_path>...")
        return 1

    total_errors = 0
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"  [ERROR] 文件不存在: {path}")
            total_errors += 1
            continue

        suffix = path.suffix.lower()
        if suffix == ".json":
            errors = validate_json(path)
        elif suffix == ".jsonl":
            errors = validate_jsonl(path)
        else:
            print(f"  [SKIP] 不支持的文件类型: {path}")
            continue

        if errors:
            print(f"\n{'='*60}")
            print(f"  [FAIL] {path.name}")
            print(f"{'='*60}")
            for err in errors:
                print(err)
            total_errors += len([e for e in errors if e.startswith("  [ERROR]")])
        else:
            print(f"  [OK] {path.name}")

    if total_errors > 0:
        print(f"\n共检测到 {total_errors} 个错误。")
        return 1
    else:
        print(f"\n所有文件校验通过。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
