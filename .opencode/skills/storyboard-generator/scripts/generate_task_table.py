#!/usr/bin/env python3
"""分镜图生图任务表生成器 — 纯机械转换

输入：独立组 JSON 文件目录（05_groups/，每组含通用设定）
输出：符合 .opencode/schemas/image-generation.json 的分镜图_任务表.json

支持三种输入模式：
  1. --groups-dir: 从 05_groups/ 目录读取独立组 JSON 文件（推荐，新版）
  2. --storyboard: 从单个分镜 JSON 文件读取（兼容旧版扁平结构）
  3. --take-from-pipeline + --pipeline-dir: 自动检测 05_groups/ 或 04_validated.json

用法:
  python generate_task_table.py ^
    --groups-dir .pipeline/05_groups/ ^
    --output-dir project/{项目}/{剧集号}/分镜/
"""

import json
import os
import re
import sys
from pathlib import Path

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1K"
DEFAULT_ASPECT = "16:9"


def determine_layout(shot_count):
    if shot_count <= 1:
        return "1x1"
    elif shot_count == 2:
        return "2x1"
    elif shot_count <= 4:
        return "2x2"
    elif shot_count <= 6:
        return "3x2"
    elif shot_count <= 9:
        return "3x3"
    elif shot_count <= 12:
        return "4x3"
    else:
        return "4x4"


def build_prompt(group, shot_count, layout, image_refs=None):
    group_no = group.get("组号", "?")
    overview = group.get("组叙事概述", "")
    total_time = group.get("组时长", "?")
    transition = group.get("组转场", "")
    common = group.get("通用设定", {})

    parts = []
    header = f"【第{group_no}组】"
    if image_refs:
        ref_labels = [f"{label}参考图片{i+1}" for i, label in enumerate(image_refs)]
        header += "，".join(ref_labels) + "。"
    header += overview
    parts.append(header)
    parts.append(f"网格布局：{layout}，共{shot_count}镜，总时长{total_time}s")
    if transition:
        parts.append(f"转场方式：{transition}")
    if common and isinstance(common, dict):
        parts.append(f"通用设定：{json.dumps(common, ensure_ascii=False)}")
    parts.append("")

    parts.append(json.dumps(group, ensure_ascii=False, indent=2))

    return "\n".join(parts)


def load_groups_from_dir(groups_dir):
    groups = []
    if not os.path.isdir(groups_dir):
        return groups

    pattern = re.compile(r'^组(\d+)\.json$')
    files = []
    for fn in os.listdir(groups_dir):
        m = pattern.match(fn)
        if m:
            files.append((int(m.group(1)), fn))

    files.sort(key=lambda x: x[0])

    for _, fn in files:
        filepath = os.path.join(groups_dir, fn)
        with open(filepath, "r", encoding="utf-8-sig") as f:
            group = json.load(f)
            groups.append(group)

    return groups


def load_groups_from_file(storyboard_path):
    with open(storyboard_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    first = data[0] if data else {}
    if isinstance(first, dict) and "组列表" in first:
        groups = []
        for scene in data:
            scene_common = scene.get("通用设定", {})
            for group in scene.get("组列表", []):
                group_out = dict(group)
                if "通用设定" not in group_out:
                    group_out["通用设定"] = dict(scene_common)
                groups.append(group_out)
        return groups
    else:
        return data


def generate_task_table(groups, output_dir, output_name, image_refs=None,
                        ref_images=None,
                        model=DEFAULT_MODEL, image_size=DEFAULT_SIZE,
                        aspect_ratio=DEFAULT_ASPECT):
    if not groups:
        print("警告: 输入中没有组数据", file=sys.stderr)
        return

    tasks = []
    for group in groups:
        shots = group.get("镜头列表", [])
        shot_count = len(shots)
        layout = determine_layout(shot_count)
        prompt = build_prompt(group, shot_count, layout, image_refs)
        group_no = group.get("组号", "?")

        task = {
            "prompt": prompt,
            "model": model,
            "imageSize": image_size,
            "aspectRatio": aspect_ratio,
            "filename": f"组{group_no}_{layout}.png",
            "images": ref_images or [],
        }

        tasks.append(task)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_name)
    result = {
        "tasks": tasks,
        "model": model,
        "output_path": output_dir,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  {len(tasks)} tasks -> {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="分镜图生图任务表生成器")
    parser.add_argument("--storyboard", help="分镜 JSON 路径（兼容旧版）")
    parser.add_argument("--groups-dir", help="独立组 JSON 目录路径（新版，如 05_groups/）")
    parser.add_argument("--output-dir", default="./", help="输出目录")
    parser.add_argument("--output-name", default="分镜图_任务表.json", help="输出文件名")
    parser.add_argument("--take-from-pipeline", action="store_true")
    parser.add_argument("--pipeline-dir")
    parser.add_argument("--image-refs", nargs="*", default=None,
                        help="参考图标注列表，如 --image-refs 校长角色 食堂场景 风格")
    parser.add_argument("--ref-images", nargs="*", default=None,
                        help="参考图路径列表（URL 或本地路径），写入 task 的 images 字段。"
                             "顺序与 --image-refs 对应，作为生图模型的参考输入")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"模型（默认 {DEFAULT_MODEL}，视频推荐 doubao-seedance-2-0-fast-260128）")
    parser.add_argument("--image-size", default=DEFAULT_SIZE,
                        help=f"分辨率（默认 {DEFAULT_SIZE}，视频推荐 480p/720p）")
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT,
                        help=f"画面比例（默认 {DEFAULT_ASPECT}，视频推荐 16:9/9:16/1:1）")
    args = parser.parse_args()

    groups = []

    if args.pipeline_dir and args.take_from_pipeline:
        pd = Path(args.pipeline_dir)
        groups_dir = pd / "05_groups"
        if groups_dir.is_dir() and any(groups_dir.iterdir()):
            print(f"从 {groups_dir}/ 读取独立组 JSON")
            groups = load_groups_from_dir(str(groups_dir))
        else:
            for candidate in ["04_validated.json"]:
                p = pd / candidate
                if p.exists():
                    print(f"从 .pipeline/{candidate} 读取（自动检测）")
                    groups = load_groups_from_file(str(p))
                    break
        if args.output_dir == "./":
            args.output_dir = str(pd / ".." / "分镜")

    elif args.groups_dir:
        print(f"从 {args.groups_dir} 读取独立组 JSON")
        groups = load_groups_from_dir(args.groups_dir)

    elif args.storyboard:
        print(f"从 {args.storyboard} 读取")
        groups = load_groups_from_file(args.storyboard)

    if not groups:
        print("错误: 未找到有效的组数据", file=sys.stderr)
        sys.exit(1)

    print(f"  共 {len(groups)} 组")

    generate_task_table(
        groups=groups,
        output_dir=args.output_dir,
        output_name=args.output_name,
        image_refs=args.image_refs,
        ref_images=args.ref_images,
        model=args.model,
        image_size=args.image_size,
        aspect_ratio=args.aspect_ratio,
    )


if __name__ == "__main__":
    main()