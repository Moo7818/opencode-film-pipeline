#!/usr/bin/env python3
"""场级结构展开器 — 将场→组→镜三级结构展开为独立的组 JSON 文件

每个组 JSON 自动注入场级通用设定，作为独立的视频生成提示词。
全局镜号跨场连续重排。

用法:
  python expand_scenes_to_groups.py ^
    --input 04_validated.json ^
    --output-dir 05_groups/
"""

import json
import os
import sys
from pathlib import Path


def expand_scenes_to_groups(input_path, output_dir):
    with open(input_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ 输入不是数组，无法展开", file=sys.stderr)
        sys.exit(1)

    # 检测是否已是组级结构（无场级包装）
    # 详细模式：有 镜头列表 ；精简模式：有 分镜描述
    first = data[0]
    is_flat = isinstance(first, dict) and "组列表" not in first and (
        "镜头列表" in first or "分镜描述" in first
    )

    os.makedirs(output_dir, exist_ok=True)

    global_group_no = 0
    global_shot_offset = 0
    all_group_files = []

    if is_flat:
        # 旧版扁平组→镜结构：直接逐组输出
        for group in data:
            global_group_no += 1
            shots = group.get("镜头列表", [])
            group_out = dict(group)
            group_out["组号"] = global_group_no
            group_out["镜号起始"] = global_shot_offset + 1

            if shots:
                # 详细模式：重排镜号
                for i, shot in enumerate(shots):
                    shot["镜号"] = global_shot_offset + i + 1
                global_shot_offset += len(shots)
            else:
                # 精简模式：用 镜头数 字段推进偏移
                global_shot_offset += group.get("镜头数", 1)

            filename = f"组{global_group_no}.json"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(group_out, f, ensure_ascii=False, indent=2)
            all_group_files.append(filename)
    else:
        # 场→组→镜 三级结构
        for scene in data:
            scene_common = scene.get("通用设定", {})
            groups = scene.get("组列表", [])

            for group in groups:
                global_group_no += 1
                shots = group.get("镜头列表", [])
                has_narrative = "分镜描述" in group

                group_out = {
                    "组号": global_group_no,
                    "镜号起始": global_shot_offset + 1,
                    "组时长": group.get("组时长", "0"),
                    "组叙事概述": group.get("组叙事概述", ""),
                    "组转场": group.get("组转场", ""),
                    "通用设定": dict(scene_common),
                }

                if has_narrative:
                    # 精简模式：保留分镜描述和镜头数
                    group_out["镜头数"] = group.get("镜头数", 1)
                    group_out["分镜描述"] = group.get("分镜描述", "")
                    global_shot_offset += group_out["镜头数"]
                else:
                    # 详细模式：保留镜头列表
                    group_out["镜头列表"] = []
                    for i, shot in enumerate(shots):
                        shot_out = dict(shot)
                        shot_out["镜号"] = global_shot_offset + i + 1
                        group_out["镜头列表"].append(shot_out)
                    global_shot_offset += len(shots)

                filename = f"组{global_group_no}.json"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(group_out, f, ensure_ascii=False, indent=2)
                all_group_files.append(filename)

    scene_count = "—" if is_flat else str(len(data))
    print(f"✅ {scene_count} 场 → {global_group_no} 组 → {output_dir}")
    for fn in all_group_files:
        print(f"  {fn}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="场级结构展开器")
    parser.add_argument("--input", required=True, help="输入 JSON（场级或组级）")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    args = parser.parse_args()

    expand_scenes_to_groups(args.input, args.output_dir)


if __name__ == "__main__":
    main()