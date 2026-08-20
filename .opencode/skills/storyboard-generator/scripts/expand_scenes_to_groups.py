#!/usr/bin/env python3
"""场级结构展开器 — 合并场文件并展开为独立的组 JSON 文件

支持两种输入（--input）：
  1. 目录（推荐，对应 phase-b-detailed.md 场文件直写流程）：目录下每场一个
     `场{N}.json`（内容为单个场对象，或仅含该场的单元素数组）。脚本按场号
     排序合并 → 逐文件校验（损坏当场指名报错）→ 组时间归零 → 写出合并后的
     分镜脚本.json（--output，默认存到输入目录的上级）→ 拆分为组文件。
  2. 单个 JSON 文件（向后兼容）：场级结构（场→组→镜）或旧扁平组级结构。

每个组 JSON 自动注入场级通用设定，作为独立的视频生成提示词；全局镜号跨场连续重排。

时间归零（默认开启，--no-normalize-time 关闭）：检测某组首镜 开始/结束时间
非 0 起始（如写成了全片绝对时间 "8-10"）时，整组平移为首镜 0 起始；平移后
校验区间跨度与 时长 字段一致，不一致输出告警。仅改写数字，保留原格式装饰。

用法:
  # 目录模式（场文件直写流程）：合并 + 归零 + 拆分一步完成
  python expand_scenes_to_groups.py --input 场文件/ --output-dir 分组/
  #   可选 --output 分镜脚本.json 显式指定合并产物路径

  # 单文件模式（向后兼容）
  python expand_scenes_to_groups.py --input 分镜脚本.json --output-dir 分组/
"""

import json
import os
import re
import sys
from pathlib import Path


# ─── 场文件目录加载（逐文件校验，损坏指名报错） ──────────────

def _scene_sort_key(path: Path):
    """按文件名中的数字元组排序（场2 < 场10）"""
    return tuple(int(n) for n in re.findall(r"\d+", path.stem))


def load_scenes_from_dir(dir_path: Path) -> list:
    files = sorted(
        [p for p in dir_path.glob("*.json")],
        key=_scene_sort_key,
    )
    if not files:
        print(f"[ERROR] 目录下没有任何 .json 场文件: {dir_path}", file=sys.stderr)
        sys.exit(1)

    scenes = []
    for p in files:
        raw = p.read_text(encoding="utf-8-sig")
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as e:
            # 早失败 + 准定位：损坏的场文件当场指名，不带病前进
            print(
                f"[ERROR] 场文件损坏: {p.name} — 第 {e.lineno} 行第 {e.colno} 列: {e.msg}",
                file=sys.stderr,
            )
            sys.exit(1)
        if isinstance(item, dict):
            item = [item]
        if not (isinstance(item, list) and item and all(isinstance(s, dict) for s in item)):
            print(f"[ERROR] 场文件内容须为场对象或场对象数组: {p.name}", file=sys.stderr)
            sys.exit(1)
        scenes.extend(item)

    # 按场号去重校验 + 排序（文件顺序与场号不一致时以场号为准）
    numbered = []
    for s in scenes:
        try:
            no = int(s.get("场号"))
        except (TypeError, ValueError):
            print(f"[ERROR] 场对象缺少有效 场号 字段: {s.get('场名称', '?')}", file=sys.stderr)
            sys.exit(1)
        numbered.append((no, s))
    seen = set()
    for no, _ in numbered:
        if no in seen:
            print(f"[ERROR] 场号重复: 场{no}（检查是否有两个文件写了同一场）", file=sys.stderr)
            sys.exit(1)
        seen.add(no)
    numbered.sort(key=lambda t: t[0])
    return [s for _, s in numbered]


# ─── 组时间归零（仅机械平移，不创作内容） ────────────────────

_TIME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:s|秒)?\s*[-–—~]\s*(\d+(?:\.\d+)?)"
)


def _fmt_num(x: float) -> str:
    """8.0 -> '8'，8.5 -> '8.5'（保持无多余小数）"""
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _normalize_group_times(scene_no, group_no, group) -> list:
    """组内首镜非 0 起始时整组平移归零；返回告警列表。"""
    warnings = []
    shots = group.get("镜头列表", [])
    if not shots:
        return warnings

    parsed = []
    for shot in shots:
        m = _TIME_RE.search(str(shot.get("开始/结束时间", "")))
        parsed.append((m.group(0), float(m.group(1)), float(m.group(2))) if m else None)

    valid = [p for p in parsed if p]
    if not valid:
        warnings.append(f"场{scene_no}·组{group_no}: 所有镜头的 开始/结束时间 均无法解析，跳过时间归零")
        return warnings

    offset = valid[0][1]
    if offset == 0:
        shift_needed = False
    else:
        shift_needed = True

    for shot, p in zip(shots, parsed):
        if not p:
            warnings.append(
                f"场{scene_no}·组{group_no}·镜{shot.get('镜号', '?')}: "
                f"开始/结束时间 [{shot.get('开始/结束时间')}] 无法解析，原样保留"
            )
            continue
        orig, start, end = p
        if shift_needed:
            start -= offset
            end -= offset
            # 仅替换数字，保留原分隔/单位装饰
            new_span = re.sub(
                r"\d+(?:\.\d+)?",
                lambda m2: _fmt_num(start) if float(m2.group(0)) == p[1] else _fmt_num(end),
                orig,
                count=2,
            )
            shot["开始/结束时间"] = new_span
        # 跨度 vs 时长 一致性校验
        try:
            duration = float(shot.get("时长"))
        except (TypeError, ValueError):
            duration = None
        if duration is not None and abs((end - start) - duration) > 0.05:
            warnings.append(
                f"场{scene_no}·组{group_no}·镜{shot.get('镜号', '?')}: "
                f"时间跨度 {end - start:g}s 与 时长字段 {duration:g}s 不一致"
            )

    if shift_needed:
        warnings.append(
            f"场{scene_no}·组{group_no}: 首镜非 0 起始，整组已平移 -{_fmt_num(offset)}s 归零"
        )
    return warnings


# ─── 展开（合并后的场列表 → 组文件） ─────────────────────────

def expand_scenes_to_groups(input_path, output_dir, output_merged=None, normalize_time=True):
    input_path = Path(input_path)
    is_dir = input_path.is_dir()

    merged_path = None
    if is_dir:
        data = load_scenes_from_dir(input_path)
        # 合并产物默认写到输入目录的上级（分镜/场文件/ → 分镜/分镜脚本.json）
        merged_path = Path(output_merged) if output_merged else input_path.parent / "分镜脚本.json"
    else:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print("[ERROR] 输入不是数组，无法展开", file=sys.stderr)
            sys.exit(1)

    if not (data and isinstance(data[0], dict) and "组列表" in data[0]):
        print(
            "[ERROR] 输入不是场→组→镜三级结构（首个元素缺少 组列表 字段）。"
            "旧版扁平组级结构已废弃。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 时间归零（机械平移，默认开启）
    all_warnings = []
    if normalize_time:
        for scene in data:
            scene_no = scene.get("场号", "?")
            for group in scene.get("组列表", []):
                all_warnings.extend(
                    _normalize_group_times(scene_no, group.get("组号", "?"), group)
                )

    # 写出合并后的 分镜脚本.json（目录模式）
    if merged_path is not None:
        with open(merged_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 展开为组文件
    os.makedirs(output_dir, exist_ok=True)

    global_group_no = 0
    global_shot_offset = 0
    all_group_files = []
    summary_lines = []

    for idx, scene in enumerate(data, start=1):
        try:
            resolved_scene_no = int(scene.get("场号", idx))
        except (TypeError, ValueError):
            resolved_scene_no = idx
        scene_common = scene.get("通用设定", {})
        scene_name = scene.get("场名称", scene.get("场名", f"场{resolved_scene_no}"))
        physical_space = scene_common.get("场景名称", "")
        groups = scene.get("组列表", [])
        shots_in_scene = 0

        for group in groups:
            global_group_no += 1
            shots = group.get("镜头列表", [])

            group_out = {
                "场号": resolved_scene_no,
                "场名称": scene_name,
                "物理空间": physical_space,
                "组号": global_group_no,
                "镜号起始": global_shot_offset + 1,
                "组时长": group.get("组时长", "0"),
                "组叙事概述": group.get("组叙事概述", ""),
                "组转场": group.get("组转场", ""),
                "通用设定": dict(scene_common),
            }

            if shots:
                group_out["镜头列表"] = []
                for i, shot in enumerate(shots):
                    shot_out = dict(shot)
                    shot_out["镜号"] = global_shot_offset + i + 1
                    group_out["镜头列表"].append(shot_out)
                global_shot_offset += len(shots)
                shots_in_scene += len(shots)
            else:
                # 精简模式场文件（有 分镜描述）
                group_out["镜头数"] = group.get("镜头数", 1)
                group_out["分镜描述"] = group.get("分镜描述", "")
                global_shot_offset += group_out["镜头数"]
                shots_in_scene += group_out["镜头数"]

            filename = f"组{global_group_no}.json"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                json.dump(group_out, f, ensure_ascii=False, indent=2)
            all_group_files.append(filename)

        summary_lines.append(
            f"  场{resolved_scene_no} {scene_name} | {len(groups)}组 | {shots_in_scene}镜"
        )

    if merged_path is not None:
        print(f"[OK] 已合并 {len(data)} 个场文件 → {merged_path}")
    print(f"[OK] {len(data)} 场 → {global_group_no} 组 → {output_dir}")
    for line in summary_lines:
        print(line)
    if all_warnings:
        print(f"[WARN] {len(all_warnings)} 条时间归零告警：")
        for w in all_warnings:
            print(f"  - {w}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="场级结构展开器（支持场文件目录合并）")
    parser.add_argument("--input", required=True,
                        help="场文件目录（推荐）或单个分镜脚本 JSON")
    parser.add_argument("--output-dir", required=True, help="组文件输出目录")
    parser.add_argument("--output", default=None, metavar="分镜脚本.json",
                        help="（目录模式）合并产物路径，默认为输入目录上级的 分镜脚本.json")
    parser.add_argument("--no-normalize-time", action="store_true",
                        help="关闭组时间归零（默认：首镜非 0 的组整组平移归零）")
    args = parser.parse_args()

    # Windows GBK 控制台守卫
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    expand_scenes_to_groups(
        args.input, args.output_dir,
        output_merged=args.output,
        normalize_time=not args.no_normalize_time,
    )


if __name__ == "__main__":
    main()
