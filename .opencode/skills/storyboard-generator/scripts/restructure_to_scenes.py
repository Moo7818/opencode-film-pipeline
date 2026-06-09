#!/usr/bin/env python3
"""旧版分镜数据迁移：扁平组→场级结构

将旧版 [{组...}, {组...}] 格式转换为新版 [{场...组列表...}] 格式。
基于场景名称 + 全局色彩调性聚类自动分场。

用法:
  python restructure_to_scenes.py ^
    --input 旧版分镜.json ^
    --output 新版分镜.json
"""

import json
import os
import sys
from collections import OrderedDict


def cluster_groups_to_scenes(groups):
    """将组按场景名称 + 色彩调性聚类为场"""
    scene_map = OrderedDict()

    for group in groups:
        common = group.get("通用设定", {})
        if not isinstance(common, dict):
            continue

        scene_name = common.get("场景名称", "") or common.get("场景", "")
        tone = common.get("全局色彩调性", "")

        key = (scene_name.strip(), tone.strip())

        if key not in scene_map:
            scene_map[key] = {
                "场景名称": scene_name.strip(),
                "全局色彩调性": tone.strip(),
                "通用设定": {},
                "groups": [],
            }

        scene_map[key]["groups"].append(group)

        # 合并通用设定（取第一个组的完整设定）
        if not scene_map[key]["通用设定"]:
            clean = {k: v for k, v in common.items()
                     if k not in ("人物", "关键道具", "images")}
            scene_map[key]["通用设定"] = clean

    scenes = []
    scene_no = 1
    global_group_no = 0

    for key, scene_data in scene_map.items():
        scene_groups = scene_data["groups"]
        total_duration = 0
        for g in scene_groups:
            global_group_no += 1
            g["组号"] = global_group_no

            shots = g.get("镜头列表", [])
            for i, shot in enumerate(shots):
                shot["镜号"] = i + 1

            dur = g.get("组时长", "0")
            try:
                total_duration += float(dur)
            except (ValueError, TypeError):
                pass

        # 推断场名称
        scene_name = scene_data["场景名称"] or f"场{scene_no}"

        scene = {
            "场号": scene_no,
            "场名称": scene_name,
            "场叙事概述": "",
            "场转场": scene_groups[-1].get("组转场", "") if scene_groups else "",
            "场总时长": str(int(total_duration)),
            "通用设定": scene_data["通用设定"],
            "组列表": scene_groups,
        }
        scenes.append(scene)
        scene_no += 1

    return scenes


def main():
    import argparse
    parser = argparse.ArgumentParser(description="旧版分镜数据迁移工具")
    parser.add_argument("--input", required=True, help="旧版分镜 JSON（扁平组结构）")
    parser.add_argument("--output", required=True, help="输出路径（场级结构）")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ 输入不是数组", file=sys.stderr)
        sys.exit(1)

    first = data[0] if data else {}
    if isinstance(first, dict) and "组列表" in first:
        print("⚠ 输入已经是场级结构，无需迁移", file=sys.stderr)
        sys.exit(0)

    scenes = cluster_groups_to_scenes(data)

    total_groups = sum(len(s["组列表"]) for s in scenes)
    total_shots = sum(
        len(g.get("镜头列表", [])) for s in scenes for g in s["组列表"]
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    print(f"✅ 迁移完成: {len(data)} 组 → {len(scenes)} 场 ({total_groups} 组, {total_shots} 镜)")
    for s in scenes:
        sn = s["场号"]
        sn_name = s["场名称"]
        gn = len(s["组列表"])
        print(f"  场{sn}: {sn_name} ({gn} 组)")

    print(f"\n  输出: {args.output}")
    print(f"  提示: 迁移后请手动检查'场叙事概述'等字段是否需要调整")


if __name__ == "__main__":
    main()