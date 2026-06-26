"""
build_index.py — 构建 awesome-gpt-image-2-API-and-Prompts 仓库的 Prompt 轻量索引

产出 catalog.json（元数据索引），供 Agent 快速检索：
- case_id / 标题 / 类别 / 作者
- 难度标签 / 有无 {argument} 参数
- 对应 .md 文件路径 + 行号范围 + 语言
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

CATEGORIES = {
    "poster": "海报与插画",
    "character": "角色设计",
    "portrait": "人像与摄影",
    "ui": "UI 与社交媒体",
    "ecommerce": "电商",
    "ad-creative": "广告创意",
    "comparison": "对比与社区示例",
}

LANG_MAP = {
    "_zh-CN": "zh-CN",
    "_zh-TW": "zh-TW",
    "_de": "de",
    "_es": "es",
    "_fr": "fr",
    "_ja": "ja",
    "_ko": "ko",
    "_pt": "pt",
    "_ru": "ru",
    "_tr": "tr",
}


def detect_language(filename: str) -> str:
    stem = Path(filename).stem
    for suffix, lang in LANG_MAP.items():
        if stem.endswith(suffix):
            return lang
    return "en"


def has_argument_syntax(text: str) -> bool:
    return "{argument" in text


def parse_case_id(title_line: str, category: str) -> str:
    m = re.search(r"Case\s*(\d+)", title_line)
    if m:
        return f"{category}_case{m.group(1)}"
    return None


def parse_title(title_line: str) -> str:
    m = re.search(r"Case\s*\d+:\s*\[(.+?)\]", title_line)
    return m.group(1).strip() if m else title_line.strip()


def parse_author(title_line: str) -> str:
    m = re.search(r"by\s+\[(@?\w+)\]", title_line)
    return m.group(1) if m else ""


def parse_source_url(title_line: str) -> str:
    m = re.search(r"\]\((.+?)\)", title_line)
    return m.group(1) if m else ""


def build_index(repo_path: Path) -> dict:
    cases_dir = repo_path / "cases"
    if not cases_dir.exists():
        print(f"[ERR] 未找到 cases 目录: {cases_dir}", file=sys.stderr)
        sys.exit(1)

    catalog = {cat: [] for cat in CATEGORIES}
    stats = {"total_cases": 0, "with_arguments": 0, "by_category": {}, "by_language": {}}

    for fpath in sorted(cases_dir.glob("*.md")):
        category = None
        for cat_key in CATEGORIES:
            stem = fpath.stem
            base_stem = stem.split("_")[0]
            if base_stem == cat_key or stem.startswith(cat_key + "_"):
                category = cat_key
                break
        if category is None:
            continue

        lang = detect_language(fpath.name)
        content = fpath.read_text(encoding="utf-8")
        lines = content.split("\n")

        for i, line in enumerate(lines):
            if not re.match(r"^###\s+Case\s+\d+:", line):
                continue

            case_id = parse_case_id(line, category)
            if not case_id:
                continue

            title = parse_title(line)
            source_url = parse_source_url(line)
            author = parse_author(line)

            prompt_start = -1
            prompt_end = -1
            found_prompt_label = False
            for j in range(i + 1, min(i + 100, len(lines))):
                stripped = lines[j].strip()
                if stripped == "**Prompt:**" or stripped == "**Prompt:**":
                    found_prompt_label = True
                    continue
                if found_prompt_label and stripped == "":
                    continue
                if found_prompt_label and stripped.startswith("```"):
                    prompt_start = j + 1
                    for k in range(j + 1, min(j + 200, len(lines))):
                        if lines[k].strip().startswith("```"):
                            prompt_end = k
                            break
                    break

            if prompt_start == -1 or prompt_end == -1:
                continue

            prompt_text = "\n".join(lines[prompt_start:prompt_end])
            has_args = has_argument_syntax(prompt_text)
            entry = {
                "case_id": case_id,
                "title": title,
                "author": author,
                "source_url": source_url,
                "has_arguments": has_args,
                "lang": lang,
                "file": fpath.name,
                "line_range": [i + 1, prompt_end + 1],
            }
            catalog[category].append(entry)
            stats["total_cases"] += 1
            if has_args:
                stats["with_arguments"] += 1
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            stats["by_language"][lang] = stats["by_language"].get(lang, 0) + 1

    return {"catalog": catalog, "stats": stats}


def load_catalog(catalog_path: Path) -> dict:
    if not catalog_path.exists():
        print(f"[ERR] 索引文件不存在: {catalog_path}", file=sys.stderr)
        print("   请先运行 build_index.py --repo-path <path> 构建索引", file=sys.stderr)
        sys.exit(1)
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def cmd_search(data: dict, keyword: str, category: str, lang: str):
    keyword_lower = keyword.lower()
    results = []
    cats = [category] if category else data["catalog"].keys()
    for cat in cats:
        for entry in data["catalog"].get(cat, []):
            if lang and entry["lang"] != lang:
                continue
            if keyword_lower in entry["title"].lower():
                results.append(entry)
    if not results:
        print(f"  未找到匹配: keyword={keyword}, category={category}, lang={lang}")
        return
    print(f"  找到 {len(results)} 个匹配:")
    for r in results:
        args_tag = " [有参数]" if r["has_arguments"] else ""
        print(f"    {r['case_id']}: {r['title']}{args_tag}")


def cmd_list_category(data: dict, category: str, lang: str):
    entries = data["catalog"].get(category, [])
    if lang:
        entries = [e for e in entries if e["lang"] == lang]
    if not entries:
        print(f"  类别 '{category}' 无数据 (lang={lang})")
        return
    print(f"  类别 {category} ({lang}): {len(entries)} 个案例")
    for e in entries:
        args_tag = " [有参数]" if e["has_arguments"] else ""
        print(f"    {e['case_id']}: {e['title']}{args_tag}")


def cmd_stats(data: dict):
    s = data["stats"]
    print(f"  总计: {s['total_cases']} 个案例")
    print(f"  含参数模板: {s['with_arguments']} 个")
    print(f"  按类别: {s['by_category']}")
    print(f"  按语言: {s['by_language']}")
    print()
    print("  各类别 EN 案例数:")
    for cat, entries in data["catalog"].items():
        en_count = sum(1 for e in entries if e["lang"] == "en")
        all_count = len(entries)
        arg_count = sum(1 for e in entries if e["has_arguments"] and e["lang"] == "en")
        print(f"    {cat}: EN={en_count}, 总计={all_count}, 含参数={arg_count}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GPT Image 2 Prompt 索引工具")
    parser.add_argument("--repo-path", type=str, help="仓库本地路径（构建索引时必填）")
    parser.add_argument("--catalog", type=str, default=None, help="catalog.json 路径（查询时默认自动查找）")
    parser.add_argument("--output", type=str, default="catalog.json", help="索引输出路径（构建时）")
    parser.add_argument("--search", type=str, default=None, help="按关键词搜索标题")
    parser.add_argument("--category", type=str, default=None, help="搜索/列表时按类别过滤")
    parser.add_argument("--list-category", type=str, default=None, help="列出某类别的所有案例（同 --category）")
    parser.add_argument("--lang", type=str, default=None, help="过滤语言代码")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")

    args = parser.parse_args()

    # 查询模式：需要 catalog.json 路径
    is_query = args.search or args.list_category or args.stats
    if is_query:
        catalog_path = None
        if args.catalog:
            catalog_path = Path(args.catalog)
        elif args.repo_path:
            # 查找 skill 目录下的 references/catalog.json
            catalog_path = Path(__file__).resolve().parents[1] / "references" / "catalog.json"
        else:
            catalog_path = Path(__file__).resolve().parents[1] / "references" / "catalog.json"

        if not catalog_path or not catalog_path.exists():
            print(f"[ERR] 无法定位 catalog.json", file=sys.stderr)
            print("   请指定 --catalog 路径或先构建索引", file=sys.stderr)
            sys.exit(1)

        data = load_catalog(catalog_path)

        category_filter = args.category or args.list_category

        if args.stats:
            cmd_stats(data)
        elif args.search:
            cmd_search(data, args.search, category_filter, args.lang or "en")
        elif category_filter:
            cmd_list_category(data, category_filter, args.lang or "en")
        return

    # 构建模式
    if not args.repo_path:
        parser.print_help()
        sys.exit(1)

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"[ERR] 仓库路径不存在: {repo_path}", file=sys.stderr)
        sys.exit(1)

    data = build_index(repo_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] 索引已构建: {output_path}")
    print(f"   总计 {data['stats']['total_cases']} 个案例")
    print(f"   含参数模板 {data['stats']['with_arguments']} 个")
    print(f"   类别分布: {data['stats']['by_category']}")
    print(f"   语言分布: {data['stats']['by_language']}")


if __name__ == "__main__":
    main()
