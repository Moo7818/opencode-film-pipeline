#!/usr/bin/env python3
"""分镜图任务表校验器 — 校验分镜图_任务表.json 的引用一致性

校验项：
1. JSON 语法正确性
2. 模型必须为 gpt-image-2-vip
3. 画面比例必须为 16:9 或 9:16（生图模型仅支持这两种）
4. images 数组不得为空
5. images 路径必须为具体文件（非目录）
6. 提示词中参考图标签数量与 images 数组一致
7. 参考图优先级：角色 → 场景 → 道具 → 风格
8. 角色和场景参考图必须在前五个参考中

CLI:
  python validate_task_table.py --check "project/{项目名}/{剧集号}/分镜/分镜图_任务表.json"
  python validate_task_table.py --check "分镜图_任务表.json" --verbose
"""

import json
import os
import re
import sys
from pathlib import Path


# ─── 校验规则 ─────────────────────────────────────────────

REQUIRED_MODEL = "gpt-image-2-vip"

VALID_ASPECT_RATIOS = {"16:9", "9:16"}

REF_PRIORITY = {
    "角色": 0,
    "场景": 1,
    "道具": 2,
    "风格": 3,
}


# ─── 校验逻辑 ─────────────────────────────────────────────

def _classify_ref(path: str) -> str:
    """根据路径判断参考图类型"""
    if "角色参考图" in path or "角色设定" in path:
        return "角色"
    if "场景参考图" in path or "场景设定" in path:
        return "场景"
    if "道具参考图" in path or "道具设定" in path:
        return "道具"
    if "风格" in path:
        return "风格"
    return "未知"


def _is_file_path(path: str) -> bool:
    """判断路径是否为文件路径（而非目录路径）"""
    if path.endswith("\\") or path.endswith("/"):
        return False
    basename = os.path.basename(path)
    if "." not in basename:
        return False
    return True


def _extract_header(prompt: str) -> str:
    """提取提示词头部（第一个句号之前的内容）"""
    end = prompt.find("。")
    return prompt[:end] if end > 0 else prompt[:200]


def _count_image_refs(header: str) -> int:
    """统计头部中参考图引用数量（匹配"第X张图片"格式）"""
    return len(re.findall(r"第[一二三四五六七八九十百]+张图片", header))


def validate_task_table(data: dict, verbose=True) -> list[str]:
    """校验分镜图任务表，返回错误列表"""
    errors = []

    if not isinstance(data, dict):
        return ["顶层结构不是对象"]

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        return ["缺少 tasks 数组或为空"]

    for i, task in enumerate(tasks):
        group_label = f"组{i+1}"
        filename = task.get("filename", "?")
        prompt = task.get("prompt", "")
        images = task.get("images", [])
        model = task.get("model", "")

        # 1. 模型校验
        if model != REQUIRED_MODEL:
            errors.append(f"{group_label} ({filename}): 模型 [{model}] 必须为 {REQUIRED_MODEL}")

        # 1.5 画面比例校验
        aspect = task.get("aspectRatio", "")
        if aspect not in VALID_ASPECT_RATIOS:
            errors.append(
                f"{group_label} ({filename}): 画面比例 [{aspect}] 无效，"
                f"仅支持 {' 或 '.join(sorted(VALID_ASPECT_RATIOS))}"
            )

        # 2. images 路径校验
        if len(images) == 0:
            errors.append(
                f"{group_label} ({filename}): images 数组为空——分镜图必须引用角色/场景参考图。"
                f"请在任务表 JSON 中为每个 task 填写具体的参考图文件路径"
            )
        else:
            for j, img_path in enumerate(images):
                if not _is_file_path(img_path):
                    errors.append(f"{group_label} ({filename}): images[{j+1}] [{img_path}] 是目录路径，必须为具体文件")

        # 3. 引用一致性校验
        header = _extract_header(prompt)
        ref_count = _count_image_refs(header)
        if ref_count != len(images):
            errors.append(
                f"{group_label} ({filename}): 提示词引用 {ref_count} 个参考图标签，"
                f"但 images 数组有 {len(images)} 个，不一致"
            )

        # 4. 优先级排序校验
        type_indices = {}
        for j, img_path in enumerate(images):
            ref_type = _classify_ref(img_path)
            if ref_type not in type_indices:
                type_indices[ref_type] = []
            type_indices[ref_type].append(j)

        # 检查排序顺序
        priority_order = ["角色", "场景", "道具", "风格"]
        last_max_idx = -1
        for ref_type in priority_order:
            if ref_type in type_indices:
                min_idx = min(type_indices[ref_type])
                if min_idx <= last_max_idx:
                    errors.append(
                        f"{group_label} ({filename}): {ref_type}参考图出现在前序类型之前，"
                        f"优先级排序错误（{ref_type}最早位置 {min_idx} <= 前序最晚位置 {last_max_idx}）"
                    )
                last_max_idx = max(last_max_idx, max(type_indices[ref_type]))

        # 5. 角色和场景在前五个参考中
        first5 = images[:5]
        first5_types = [_classify_ref(p) for p in first5]
        if "角色" not in first5_types:
            errors.append(f"{group_label} ({filename}): 角色参考图不在前五个参考中")
        if "场景" not in first5_types:
            errors.append(f"{group_label} ({filename}): 场景参考图不在前五个参考中")

    return errors


def format_report(errors, verbose=True):
    """格式化校验报告"""
    if not errors:
        return "✅ 分镜图任务表校验通过"
    lines = [f"❌ 发现 {len(errors)} 个问题："]
    for e in errors:
        lines.append(f"  · {e}")
    return "\n".join(lines)


# ─── CLI 入口 ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="分镜图任务表校验器")
    parser.add_argument("--check", metavar="task_table.json", required=True,
                        help="校验分镜图任务表 JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    check_path = Path(args.check)
    if not check_path.exists():
        print(f"❌ 文件不存在: {check_path}", file=sys.stderr)
        sys.exit(1)

    with open(check_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    errors = validate_task_table(data, verbose=args.verbose)

    if args.verbose:
        # 详细模式：打印每组信息
        tasks = data.get("tasks", [])
        print(f"\n任务总数: {len(tasks)}")
        for i, task in enumerate(tasks):
            filename = task.get("filename", "?")
            images = task.get("images", [])
            model = task.get("model", "")
            header = _extract_header(task.get("prompt", ""))
            print(f"\n--- 组{i+1} ({filename}) ---")
            print(f"  模型: {model}")
            print(f"  images 数量: {len(images)}")
            for j, img in enumerate(images):
                ref_type = _classify_ref(img)
                print(f"    [{j+1}] ({ref_type}) {os.path.basename(img)}")
            print(f"  提示词头部: {header}")
        print()

    print(format_report(errors, args.verbose))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
