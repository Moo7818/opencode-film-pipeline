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

DEFAULT_MODEL = "nano-banana-pro"
DEFAULT_SIZE = "4K"
DEFAULT_ASPECT = "16:9"


def determine_layout(shot_count, aspect_ratio="16:9"):
    """根据镜头数和成片画幅比例推断网格布局。

    竖屏(9:16 等)偏好横向排列(列>=行)，使合成图变宽；
    横屏(16:9 等)偏好纵向排列(行>=列)，使合成图变高；
    方形(1:1)或未知比例无方向偏好，使用原逻辑。
    """
    is_vertical = aspect_ratio in ("9:16", "9:18", "3:4", "2:3")
    is_horizontal = aspect_ratio in ("16:9", "18:9", "4:3", "3:2", "21:9")

    if is_vertical:
        if shot_count <= 1:
            return "1x1"
        elif shot_count == 2:
            return "2x1"
        elif shot_count == 3:
            return "3x1"
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
    elif is_horizontal:
        if shot_count <= 1:
            return "1x1"
        elif shot_count == 2:
            return "1x2"
        elif shot_count == 3:
            return "1x3"
        elif shot_count <= 4:
            return "2x2"
        elif shot_count <= 6:
            return "2x3"
        elif shot_count <= 9:
            return "3x3"
        elif shot_count <= 12:
            return "3x4"
        else:
            return "4x4"
    else:
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


def compute_composite_ratio(layout, aspect_ratio):
    """根据网格布局和单镜画幅比例计算合成图方向，输出 16:9 或 9:16。

    生图模型仅支持 16:9 和 9:16 两种画面比例。本函数根据网格行列数
    和单镜画幅计算合成图实际横纵比，判断方向后输出对应比例：
    - 合成图更宽（横向）→ 16:9
    - 合成图更高（纵向）→ 9:16
    - 正方形 → 与成片画幅方向一致

    layout: "CxR" 格式，如 "3x1"（列x行）
    aspect_ratio: "W:H" 格式，如 "9:16"（成片画幅）
    返回: "16:9" 或 "9:16"
    """
    try:
        cols_str, rows_str = layout.split("x")
        cols, rows = int(cols_str), int(rows_str)
        parts = aspect_ratio.split(":")
        w, h = int(parts[0]), int(parts[1])
    except (ValueError, AttributeError, IndexError):
        return aspect_ratio

    composite_w = cols * w
    composite_h = rows * h

    if composite_w > composite_h:
        return "16:9"
    elif composite_h > composite_w:
        return "9:16"
    else:
        # 正方形：与成片画幅方向一致
        return "16:9" if w >= h else "9:16"


# 参考图类型优先级（数值越小优先级越高）
REF_PRIORITY = {
    "角色": 0,
    "场景": 1,
    "道具": 2,
    "风格": 3,
}


def sort_refs(image_refs, ref_images):
    """按优先级排序参考图：角色 → 场景 → 道具 → 风格。

    确保主要角色参考图排首位，场景参考图排第二，
    角色和场景参考图始终位于前五个参考中。
    """
    if not image_refs or not ref_images:
        return image_refs, ref_images

    paired = list(zip(image_refs, ref_images))
    paired.sort(key=lambda x: REF_PRIORITY.get(x[0], 99))
    if paired:
        sorted_refs, sorted_images = zip(*paired)
        return list(sorted_refs), list(sorted_images)
    return [], []


def build_prompt(group, shot_count, layout, image_refs=None):
    group_no = group.get("组号", "?")
    overview = group.get("组叙事概述", "")
    total_time = group.get("组时长", "?")
    transition = group.get("组转场", "")
    common = group.get("通用设定", {})

    anchor_map = {
        "角色": "Character Identity Anchor",
        "场景": "Environment Anchor",
        "道具": "Prop Detail Anchor",
        "风格": "Visual Style Anchor",
    }

    parts = []
    header = f"【第{group_no}组】"
    if image_refs:
        ref_labels = [f"Image {i+1}: {anchor_map.get(label, label)}" for i, label in enumerate(image_refs)]
        header += "，".join(ref_labels) + "。"
    header += overview
    parts.append(header)
    parts.append(f"网格布局：{layout}，共{shot_count}镜，总时长{total_time}s，每格分镜的左上角标注镜头序号，分镜画面中无字幕")
    if transition:
        parts.append(f"转场方式：{transition}")
    if common and isinstance(common, dict):
        parts.append(f"通用设定：{json.dumps(common, ensure_ascii=False)}")
    parts.append("")

    # 精简模式：有分镜描述时直接使用文本，无则回退到完整 JSON
    narrative = group.get("分镜描述")
    if narrative:
        parts.append(narrative)
    else:
        parts.append(json.dumps(group, ensure_ascii=False, indent=2))

    return "\n".join(parts)


def load_groups_from_dir(groups_dir):
    groups = []
    if not os.path.isdir(groups_dir):
        return groups

    # 同时匹配 .json 和 .md 文件
    pattern = re.compile(r'^组(\d+)\.(json|md)$')
    files = []
    for fn in os.listdir(groups_dir):
        m = pattern.match(fn)
        if m:
            files.append((int(m.group(1)), fn))

    files.sort(key=lambda x: x[0])

    for _, fn in files:
        filepath = os.path.join(groups_dir, fn)
        if fn.endswith(".md"):
            group = load_group_from_md(filepath)
        else:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                group = json.load(f)
        if group:
            groups.append(group)

    return groups


def load_group_from_md(filepath):
    """从精简模式的 组{N}.md 文件加载组信息。

    文件格式（新结构化通用设定）：
        组时长：7s
        转场：切
        镜头数：3

        通用设定：
        风格质感：xxx
        场景：xxx
        光线：xxx
        色调：xxx
        氛围：xxx

        {组叙事概述}

        {分镜叙事段落}

    也兼容旧单行通用设定格式：
        通用设定：风格：xxx。场景：xxx。光线：xxx。色彩：xxx。氛围：xxx。
    """
    with open(filepath, "r", encoding="utf-8-sig") as f:
        text = f.read()

    lines = text.strip().split("\n")

    group = {
        "组号": None,
        "组时长": "0",
        "组叙事概述": "",
        "组转场": "",
        "通用设定": {},
        "分镜描述": "",
        "镜头数": None,
    }

    # 解析头部键值对
    content_start = 0
    skip_until = 0  # 跳过多行通用设定块的内部行
    for i, line in enumerate(lines):
        if i < skip_until:
            continue
        stripped = line.strip()
        if not stripped:
            content_start = i + 1
            continue

        # 键值行：组时长：7s / 转场：切 / 镜头数：3
        kv_match = re.match(r'^(组时长|转场|镜头数)[：:]\s*(.+)', stripped)
        if kv_match:
            key = kv_match.group(1)
            val = kv_match.group(2).strip()
            if key == "组时长":
                # 提取数字部分
                num_match = re.match(r'(\d+)', val)
                group["组时长"] = num_match.group(1) if num_match else val
            elif key == "转场":
                group["组转场"] = val
            elif key == "镜头数":
                num_match = re.match(r'(\d+)', val)
                group["镜头数"] = int(num_match.group(1)) if num_match else None
            content_start = i + 1
            continue

        # 通用设定行（支持单行和多行结构化两种格式）
        setting_match = re.match(r'^通用设定[：:]\s*(.*)', stripped)
        if setting_match:
            setting_text = setting_match.group(1).strip()
            if setting_text:
                # 旧格式：单行通用设定（通用设定：风格：xxx。场景：xxx。...）
                group["通用设定"] = parse_md_setting(setting_text)
                content_start = i + 1
            else:
                # 新格式：多行结构化通用设定
                # 通用设定： 后跟多行 "字段：值" 对，空行结束
                setting_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    field_match = re.match(r'^([^：:]+)[：:]\s*(.+)', next_line)
                    if field_match:
                        setting_lines.append(next_line)
                        j += 1
                    else:
                        break
                group["通用设定"] = parse_md_setting("\n".join(setting_lines))
                content_start = j
                skip_until = j
            continue

        # 非键值行 = 内容开始
        content_start = i
        break

    # 剩余内容为分镜叙事
    content_lines = lines[content_start:]
    content = "\n".join(content_lines).strip()

    # 第一段（空行分隔）为组叙事概述，其余为分镜描述
    if content:
        parts = content.split("\n\n", 1)
        group["组叙事概述"] = parts[0].strip()
        if len(parts) > 1:
            group["分镜描述"] = parts[1].strip()

    # 从文件名提取组号
    basename = os.path.basename(filepath)
    num_match = re.match(r'组(\d+)', basename)
    if num_match:
        group["组号"] = int(num_match.group(1))

    # 镜头数：优先从头部字段获取，无则从分镜描述段落数推断
    if not group["镜头数"]:
        group["镜头数"] = _count_shots_from_narrative(group["分镜描述"])

    return group


def _is_dialogue_only(text):
    """判断段落是否为纯台词行（非镜头描述）。

    讲戏式叙事中，台词通常融入镜头段落。但偶尔台词单独成段，
    此类段落短且以 "角色名：台词" 格式开头，不应计入镜头数。
    """
    text = text.strip()
    if len(text) > 80:
        return False
    if re.match(r'^.{1,12}[：:]', text) and ('"' in text or '"' in text or '"' in text):
        return True
    if re.match(r'^旁白[：:]', text):
        return True
    return False


def _count_shots_from_narrative(narrative):
    """从分镜描述文本中推断镜头数（一段一镜，过滤纯台词行）。"""
    if not narrative:
        return 1
    paragraphs = [p.strip() for p in narrative.split("\n\n") if p.strip()]
    shot_paragraphs = [p for p in paragraphs if not _is_dialogue_only(p)]
    return max(len(shot_paragraphs), 1)


def parse_md_setting(text):
    """将通用设定文本解析为结构化字典。

    支持两种格式：
    1. 旧单行格式：风格：xxx。场景：xxx。光线：xxx。色彩：xxx。氛围：xxx。
    2. 新多行结构化格式（每行一个 "字段：值" 对）：
       风格质感：xxx
       场景：xxx
       光线：xxx
       色调：xxx
       氛围：xxx

    输出：{"风格": "xxx", "场景名称": "xxx", "全局光线基调": "xxx", ...}
    """
    # 字段名映射：MD 标签名 → 内部标准化字段名
    # 同时支持新旧两套标签名
    field_map = {
        "风格": "风格",
        "风格质感": "风格",
        "场景": "场景名称",
        "光线": "全局光线基调",
        "色彩": "全局色彩调性",
        "色调": "全局色彩调性",
        "氛围": "全局氛围基调",
    }

    result = {}

    # 检测多行格式（包含换行符）
    if "\n" in text:
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            kv_match = re.match(r'^([^：:]+)[：:]\s*(.*)$', line)
            if kv_match:
                key = kv_match.group(1).strip()
                val = kv_match.group(2).strip()
                if key in field_map:
                    result[field_map[key]] = val
                else:
                    # 保留未映射的字段
                    result[key] = val
    else:
        # 旧单行格式：按"键：" 分割
        # 注意：风格质感 需在 风格 之前匹配，色调 需在 色彩 之前无冲突，但仍按长度降序排列
        parts = re.split(r'(风格质感|风格|场景|光线|色调|色彩|氛围)[：:]', text)
        for i in range(1, len(parts) - 1, 2):
            key = parts[i]
            val = parts[i + 1].rstrip('。').strip()
            if key in field_map:
                result[field_map[key]] = val

    return result


def auto_detect_refs(project_dir, episode=None):
    """自动检测项目中的参考图目录。

    按标准路径扫描角色/场景/道具/风格参考图目录，返回 (image_refs, ref_images) 二元组。
    仅返回包含 .png/.jpg 文件的目录，跳过空目录。

    project_dir: 项目根目录，如 "project/荼荼茶叶"
    episode: 剧集号，如 "EP01"（用于定位剧集级参考图）
    """
    pd = Path(project_dir)
    refs = []      # ["角色", "场景", ...]
    ref_paths = [] # ["project/.../角色参考图/", ...]

    # 1. 角色参考图（全局）
    char_dir = pd / "全局依赖" / "角色设定" / "角色参考图"
    if char_dir.is_dir() and any(char_dir.glob("*.png")):
        refs.append("角色")
        ref_paths.append(str(char_dir) + os.sep)

    # 2. 场景参考图（剧集级优先，回退全局）
    scene_dir = None
    if episode:
        ep_scene = pd / episode / "场景参考图"
        if ep_scene.is_dir() and any(ep_scene.glob("*.png")):
            scene_dir = ep_scene
    if not scene_dir:
        global_scene = pd / "全局依赖" / "场景设定" / "场景参考图"
        if global_scene.is_dir() and any(global_scene.glob("*.png")):
            scene_dir = global_scene
    if scene_dir:
        refs.append("场景")
        ref_paths.append(str(scene_dir) + os.sep)

    # 3. 道具参考图（剧集级优先，回退全局）
    prop_dir = None
    if episode:
        ep_prop = pd / episode / "道具参考图"
        if ep_prop.is_dir() and any(ep_prop.glob("*.png")):
            prop_dir = ep_prop
    if not prop_dir:
        global_prop = pd / "全局依赖" / "道具设定" / "道具参考图"
        if global_prop.is_dir() and any(global_prop.glob("*.png")):
            prop_dir = global_prop
            # 全局基准文件名含出现场合：{道具名}_{出现场合}_基准.png
            # Agent 须读取具体设定中的出现场合字段，仅引用属于本集的道具基准图
            if episode:
                print(f"  提示: 道具参考图回退全局目录，请确认仅引用出现场合包含 {episode} 的道具基准图", file=sys.stderr)
    if prop_dir:
        refs.append("道具")
        ref_paths.append(str(prop_dir) + os.sep)

    # 4. 风格参考图（全局）
    style_dir = pd / "前期采样" / "风格"
    if style_dir.is_dir() and any(style_dir.glob("*.png")):
        refs.append("风格")
        ref_paths.append(str(style_dir) + os.sep)

    return refs, ref_paths


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

    # 参考图按优先级排序：角色 → 场景 → 道具 → 风格
    if image_refs and ref_images:
        image_refs, ref_images = sort_refs(image_refs, ref_images)
        print(f"  参考图排序: {image_refs}")
    else:
        print("\n" + "=" * 60, file=sys.stderr)
        print("⚠️  警告: 未提供参考图 (--ref-images)", file=sys.stderr)
        print("   分镜图将不引用任何角色/场景/道具/风格参考图", file=sys.stderr)
        print("   这会导致角色形象、场景风格在各组图中不一致", file=sys.stderr)
        print("   建议: 使用 --project-dir 和 --episode 自动检测参考图目录", file=sys.stderr)
        print("   或显式传入 --image-refs 和 --ref-images 参数", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)

    tasks = []
    for group in groups:
        shots = group.get("镜头列表", [])
        if shots:
            shot_count = len(shots)
        else:
            # 精简模式：无镜头列表，从 镜头数 字段获取
            shot_count = group.get("镜头数", 1)
        layout = determine_layout(shot_count, aspect_ratio)
        composite_ratio = compute_composite_ratio(layout, aspect_ratio)
        prompt = build_prompt(group, shot_count, layout, image_refs)
        group_no = group.get("组号", "?")

        print(f"  组{group_no}: {shot_count}镜 → 布局{layout} → 比例{composite_ratio}")

        task = {
            "prompt": prompt,
            "model": model,
            "imageSize": image_size,
            "aspectRatio": composite_ratio,
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
    parser.add_argument("--project-dir", default=None,
                        help="项目目录路径（如 project/荼荼茶叶），用于自动检测参考图目录。"
                             "当 --ref-images 未提供时，按标准路径扫描角色/场景/道具/风格参考图")
    parser.add_argument("--episode", default=None,
                        help="剧集号（如 EP01），用于定位剧集级参考图目录")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"模型（默认 {DEFAULT_MODEL}）")
    parser.add_argument("--image-size", default=DEFAULT_SIZE,
                        help=f"分辨率（默认 {DEFAULT_SIZE}）")
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT,
                        help=f"成片画幅比例（默认 {DEFAULT_ASPECT}），网格布局方向据此适配，合成图比例自动计算")
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

    # 自动检测参考图目录（当 --ref-images 未显式提供时）
    if args.ref_images is None and args.project_dir:
        detected_refs, detected_paths = auto_detect_refs(
            args.project_dir, args.episode
        )
        if detected_refs:
            args.image_refs = detected_refs
            args.ref_images = detected_paths
            print(f"  自动检测到参考图目录:")
            for ref_type, path in zip(detected_refs, detected_paths):
                print(f"    {ref_type}: {path}")
        else:
            print(f"  自动检测: {args.project_dir} 下未找到参考图目录", file=sys.stderr)

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