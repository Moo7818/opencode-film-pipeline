"""
parse_prompt.py — 按需从 .md 文件读取完整 Prompt + 参数替换

用法：
  python parse_prompt.py --repo-path <path> --case poster_case42 --lang zh-CN
  python parse_prompt.py --repo-path <path> --case portrait_case12 --lang en --set "hair=dark brown" "skin=porcelain"
  python parse_prompt.py --repo-path <path> --case character_case5 --lang ja --interactive
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"


LANG_SUFFIX = {
    "en": "",
    "de": "_de",
    "es": "_es",
    "fr": "_fr",
    "ja": "_ja",
    "ko": "_ko",
    "pt": "_pt",
    "ru": "_ru",
    "tr": "_tr",
    "zh-CN": "_zh-CN",
    "zh-TW": "_zh-TW",
}


def resolve_case_file(cases_dir: Path, category: str, lang: str) -> Path:
    suffix = LANG_SUFFIX.get(lang, "")
    candidates = [
        cases_dir / f"{category}{suffix}.md",
        cases_dir / f"{category}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def extract_prompt(content: str, case_id: str) -> str:
    """
    从 Markdown 内容中提取指定 case_id 的 Prompt。
    定位逻辑：### Case N: → **Prompt:** → ``` ... ```
    """
    lines = content.split("\n")
    case_num = case_id.split("_case")[-1] if "_case" in case_id else None
    if not case_num:
        return None

    pattern = re.compile(r"^###\s+Case\s*" + re.escape(case_num) + r"\s*:")

    for i, line in enumerate(lines):
        if not pattern.match(line):
            continue
        for j in range(i + 1, min(i + 100, len(lines))):
            stripped = lines[j].strip()
            if stripped in ("**Prompt:**", "**Prompt:**"):
                found_label = True
                for k in range(j + 1, min(j + 100, len(lines))):
                    s = lines[k].strip()
                    if s == "" and k == j + 1:
                        continue
                    if s.startswith("```"):
                        prompt_start = k + 1
                        for m in range(k + 1, min(k + 300, len(lines))):
                            if lines[m].strip().startswith("```"):
                                prompt_end = m
                                return "\n".join(lines[prompt_start:prompt_end])
    return None


ARG_PATTERN = re.compile(r"\{argument\s+name=\"([^\"]+)\"\s+default=\"([^\"]*)\"\}")


def extract_arguments(prompt: str) -> list[dict]:
    """从 Prompt 中提取所有 {argument} 参数定义"""
    args = []
    for m in ARG_PATTERN.finditer(prompt):
        args.append({"name": m.group(1), "default": m.group(2)})
    return args


def substitute_arguments(prompt: str, values: dict[str, str]) -> str:
    """将 Prompt 中的 {argument} 替换为实际值，未提供的用默认值"""

    def replacer(m):
        name = m.group(1)
        default = m.group(2)
        return values.get(name, default)

    return ARG_PATTERN.sub(replacer, prompt)


def interactive_substitute(prompt: str) -> str:
    """交互式参数替换"""
    args = extract_arguments(prompt)
    if not args:
        print("  此模板无参数，直接输出")
        return prompt

    print(f"\n  发现 {len(args)} 个参数，请输入替换值（留空用默认值）：")
    values = {}
    for arg in args:
        val = input(f"    {arg['name']} (默认: \"{arg['default']}\"): ").strip()
        values[arg['name']] = val if val else arg['default']
    return substitute_arguments(prompt, values)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="读取并替换 Prompt 模板")
    parser.add_argument("--repo-path", type=str, required=True, help="仓库本地路径")
    parser.add_argument("--case", type=str, required=True, help="Case ID，如 poster_case42")
    parser.add_argument("--lang", type=str, default="en", help="语言代码，默认 en")
    parser.add_argument("--set", type=str, nargs="*", default=[], help="参数值 key=value 对")
    parser.add_argument("--interactive", action="store_true", help="交互式参数填充")
    parser.add_argument("--output", type=str, default=None, help="输出到文件")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    cases_dir = repo_path / "cases"

    if "_case" not in args.case:
        print(f"[ERR] 无效的 case_id: {args.case}（格式: category_caseN）", file=sys.stderr)
        sys.exit(1)

    category = args.case.split("_case")[0]

    case_file = resolve_case_file(cases_dir, category, args.lang)
    if not case_file:
        print(f"[ERR] 未找到对应 .md 文件: {category} ({args.lang})", file=sys.stderr)
        sys.exit(1)

    content = case_file.read_text(encoding="utf-8")
    prompt = extract_prompt(content, args.case)

    if prompt is None:
        print(f"[ERR] 未找到 case: {args.case} 在 {case_file.name}", file=sys.stderr)
        sys.exit(1)

    if args.interactive:
        prompt = interactive_substitute(prompt)
    elif args.set:
        values = {}
        for kv in args.set:
            if "=" in kv:
                k, v = kv.split("=", 1)
                values[k.strip()] = v.strip()
        prompt = substitute_arguments(prompt, values)

    result = json.dumps({"case_id": args.case, "lang": args.lang, "prompt": prompt}, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"[OK] 已写入 {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
