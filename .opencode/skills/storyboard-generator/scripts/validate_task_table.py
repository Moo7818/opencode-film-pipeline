#!/usr/bin/env python3
"""分镜图任务表校验器 — 校验分镜图_任务表.json 的引用一致性

校验项：
1. JSON 语法正确性
2. 模型必须为 nano-banana-pro
3. 分辨率必须为 4K
4. 画面比例必须为 16:9 或 9:16
5. images 数组不得为空
6. images 路径必须为具体文件（非目录）
7. prompt 中 Image N: 映射块数量与 images 数组一致
8. Image N: 编号必须从 1 开始连续递增
9. 参考图优先级：角色 → 场景 → 道具 → 风格
10. 角色和场景参考图必须在前五个参考中
11. prompt 包含必需的七段标题
12. 每个 FRAME 包含 Purpose 字段
13. 禁止焦距参数（35mm/50mm/85mm）

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

REQUIRED_MODEL = "nano-banana-pro"

REQUIRED_IMAGE_SIZE = "4K"

VALID_ASPECT_RATIOS = {"16:9", "9:16"}

REF_PRIORITY = {
    "角色": 0,
    "场景": 1,
    "道具": 2,
    "风格": 3,
}

REQUIRED_SECTIONS = [
    "SCENE CONTINUITY:",
    "REFERENCE IMAGE MAPPING:",
    "STORYBOARD SEQUENCE:",
    "TEXT POLICY:",
    "CINEMATIC QUALITY:",
    "AVOID:",
]

FOCAL_LENGTH_PATTERN = re.compile(r"\b(?:35|50|85)mm\b", re.IGNORECASE)


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


def _extract_reference_section(prompt: str) -> str:
    """提取 REFERENCE IMAGE MAPPING 段落（从 REFERENCE IMAGE MAPPING: 到下一个段标题）"""
    start = prompt.find("REFERENCE IMAGE MAPPING:")
    if start < 0:
        return ""
    end_markers = ["STORYBOARD SEQUENCE:", "TEXT POLICY:", "CINEMATIC QUALITY:"]
    end = len(prompt)
    for marker in end_markers:
        pos = prompt.find(marker, start)
        if pos > 0:
            end = min(end, pos)
    return prompt[start:end]


def _extract_image_refs(prompt: str) -> list[int]:
    """提取 REFERENCE IMAGES 段中的 Image {N}: 编号列表

    返回按出现顺序的编号列表，如 [1, 2, 3]。
    匹配模式：Image 1: / Image 2: / ...
    """
    section = _extract_reference_section(prompt)
    if not section:
        return []
    matches = re.findall(r"Image\s+(\d+)\s*:", section, re.IGNORECASE)
    return [int(m) for m in matches]


def _check_required_sections(prompt: str) -> list[str]:
    """检查 prompt 是否包含所有必需的段落标题"""
    missing = []
    for section in REQUIRED_SECTIONS:
        if section not in prompt:
            missing.append(section)
    return missing


def _check_frame_purposes(prompt: str) -> list[str]:
    """检查每个 FRAME 块是否包含 Purpose 字段"""
    errors = []
    frame_pattern = re.compile(r"FRAME\s+\d+\s*—", re.IGNORECASE)
    frame_matches = list(frame_pattern.finditer(prompt))

    for i, match in enumerate(frame_matches):
        frame_label = match.group(0).strip()
        start = match.end()
        next_frame = frame_pattern.search(prompt, start)
        end = next_frame.start() if next_frame else len(prompt)
        frame_block = prompt[start:end]

        if not re.search(r"^Purpose\s*:", frame_block, re.MULTILINE | re.IGNORECASE):
            errors.append(f"{frame_label} 缺少 Purpose 字段")

    return errors


def _check_focal_length(prompt: str) -> list[str]:
    """检查 prompt 中是否包含禁止的焦距参数"""
    matches = FOCAL_LENGTH_PATTERN.findall(prompt)
    if matches:
        return [f"发现焦距参数 {matches}，禁止使用 35mm/50mm/85mm"]
    return []


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
        image_size = task.get("imageSize", "")

        # 1. 模型校验
        if model != REQUIRED_MODEL:
            errors.append(f"{group_label} ({filename}): 模型 [{model}] 必须为 {REQUIRED_MODEL}")

        # 2. 分辨率校验
        if image_size != REQUIRED_IMAGE_SIZE:
            errors.append(f"{group_label} ({filename}): 分辨率 [{image_size}] 必须为 {REQUIRED_IMAGE_SIZE}")

        # 3. 画面比例校验
        aspect = task.get("aspectRatio", "")
        if aspect not in VALID_ASPECT_RATIOS:
            errors.append(
                f"{group_label} ({filename}): 画面比例 [{aspect}] 无效，"
                f"仅支持 {' 或 '.join(sorted(VALID_ASPECT_RATIOS))}"
            )

        # 4. images 路径校验
        if len(images) == 0:
            errors.append(
                f"{group_label} ({filename}): images 数组为空——分镜图必须引用角色/场景参考图。"
                f"请在任务表 JSON 中为每个 task 填写具体的参考图文件路径"
            )
        else:
            for j, img_path in enumerate(images):
                if not _is_file_path(img_path):
                    errors.append(f"{group_label} ({filename}): images[{j+1}] [{img_path}] 是目录路径，必须为具体文件")

        # 5. 引用一致性校验 — Image N: 编号
        image_refs = _extract_image_refs(prompt)
        if len(image_refs) != len(images):
            errors.append(
                f"{group_label} ({filename}): 提示词含 {len(image_refs)} 个 Image N: 映射块，"
                f"但 images 数组有 {len(images)} 个，不一致"
            )
        elif image_refs:
            expected = list(range(1, len(images) + 1))
            if image_refs != expected:
                errors.append(
                    f"{group_label} ({filename}): Image N: 编号不连续或顺序错乱，"
                    f"期望 {expected}，实际 {image_refs}"
                )

        # 6. 必需段落校验
        missing_sections = _check_required_sections(prompt)
        if missing_sections:
            errors.append(
                f"{group_label} ({filename}): 缺少必需段落: {', '.join(missing_sections)}"
            )

        # 7. FRAME Purpose 校验
        purpose_errors = _check_frame_purposes(prompt)
        for pe in purpose_errors:
            errors.append(f"{group_label} ({filename}): {pe}")

        # 8. 焦距参数校验
        focal_errors = _check_focal_length(prompt)
        for fe in focal_errors:
            errors.append(f"{group_label} ({filename}): {fe}")

        # 9. 优先级排序校验
        type_indices = {}
        for j, img_path in enumerate(images):
            ref_type = _classify_ref(img_path)
            if ref_type not in type_indices:
                type_indices[ref_type] = []
            type_indices[ref_type].append(j)

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

        # 10. 角色和场景在前五个参考中
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
        tasks = data.get("tasks", [])
        print(f"\n任务总数: {len(tasks)}")
        for i, task in enumerate(tasks):
            filename = task.get("filename", "?")
            model = task.get("model", "")
            image_size = task.get("imageSize", "")
            images = task.get("images", [])
            prompt = task.get("prompt", "")
            ref_count = _extract_image_refs(prompt)
            missing = _check_required_sections(prompt)
            purpose_errors = _check_frame_purposes(prompt)
            focal_errors = _check_focal_length(prompt)
            print(f"\n--- 组{i+1} ({filename}) ---")
            print(f"  模型: {model}")
            print(f"  分辨率: {image_size}")
            print(f"  images 数量: {len(images)}")
            print(f"  Image N: 映射块: {ref_count}")
            for j, img in enumerate(images):
                ref_type = _classify_ref(img)
                print(f"    [{j+1}] ({ref_type}) {os.path.basename(img)}")
            if missing:
                print(f"  ⚠️  缺少段落: {', '.join(missing)}")
            if purpose_errors:
                print(f"  ⚠️  Purpose 缺失: {', '.join(purpose_errors)}")
            if focal_errors:
                print(f"  ⚠️  焦距参数: {', '.join(focal_errors)}")
        print()

    print(format_report(errors, args.verbose))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
