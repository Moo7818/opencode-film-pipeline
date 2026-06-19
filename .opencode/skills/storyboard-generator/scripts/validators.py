#!/usr/bin/env python3
"""分镜脚本校验器 — JSON 提取、修复、校验一体化

支持 场(Scene)→组(Group)→镜(Shot) 三级结构校验。

CLI 模式:
  # 从 LLM 响应中提取 JSON 并修复（取代 fix_json.py）
  python validators.py --repair response.json --output clean.json

  # 校验清洗后的分镜 JSON（取代 validate_storyboard.py）
  python validators.py --check storyboard_clean.json

  # 两步合一：提取 + 校验（取代多个脚本顺序调用）
  python validators.py --repair response.json --check

导入模式:
  from validators import extract_json, validate_storyboard
"""

import json
import os
import re
import sys


# ─── 公共字段定义 ─────────────────────────────────────────────

# 场级必需字段
REQUIRED_SCENE_FIELDS = [
    "场号", "场名称", "场叙事概述", "场转场", "场总时长",
    "通用设定", "组列表",
]

# 场级通用设定必需子字段
REQUIRED_SCENE_COMMON_FIELDS = [
    "风格", "场景名称", "全局光线基调", "全局色彩调性", "全局氛围基调",
]

# 场级通用设定禁止字段（由 Agent 独立处理，LLM 不得输出）
FORBIDDEN_SCENE_COMMON_FIELDS = ["人物", "关键道具", "images"]

# 组级必需字段
REQUIRED_GROUP_FIELDS = ["组号", "组时长", "组叙事概述", "组转场", "镜头列表"]

# 组级禁止字段
FORBIDDEN_GROUP_FIELDS = ["通用设定", "images"]

# 镜头必需字段
REQUIRED_SHOT_FIELDS = [
    "镜号", "开始/结束时间", "时长", "场景描述", "站位/调度", "人物心理活动",
    "表演/微表情", "景别", "摄影机角度", "摄影机运动", "焦距景深",
    "光线", "氛围", "台词", "音效", "剪辑转场", "后期特效",
]
MIN_WORD_COUNT_FIELDS = {"光线": 35, "氛围": 40, "表演/微表情": 40, "站位/调度": 60, "人物心理活动": 30}
MAX_SHOTS_PER_GROUP = 9
MAX_GROUP_DURATION = 15


# ─── 修复层 ──────────────────────────────────────────────────

def extract_json(text: str) -> str:
    """从 LLM 响应文本中提取 JSON 字符串，移除 markdown 包裹和常见污染"""
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n```\s*$', '', text)
    text = text.strip()

    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        text = text[start:end + 1]

    return text


def repair_json(text: str) -> str:
    """修复常见 JSON 格式问题"""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    text = re.sub(r',\s*(\}|\])', r'\1', text)
    return text


def safe_parse(text: str):
    """安全解析 JSON，含自动修复。成功返回 (data, True)，失败返回 (错误信息, False)"""
    try:
        return json.loads(text), True
    except json.JSONDecodeError:
        pass

    repaired = repair_json(text)
    try:
        return json.loads(repaired), True
    except json.JSONDecodeError as e:
        return e, False


# ─── 校验层 ──────────────────────────────────────────────────

def validate_storyboard(data, verbose=True):
    """校验分镜 JSON 数据（支持场→组→镜三级或旧扁平组→镜两级），返回错误列表"""
    errors = []

    if not isinstance(data, list):
        return ["顶层不是数组"]
    if len(data) == 0:
        return ["空数组"]

    # 检测结构类型：第一个元素有 "组列表" 则是场级结构
    first = data[0]
    is_scene_structure = isinstance(first, dict) and "组列表" in first

    if is_scene_structure:
        errors.extend(_validate_scene_structure(data))
    else:
        errors.extend(_validate_flat_groups(data))

    return _dedupe(errors)


def _validate_scene_structure(scenes):
    """校验场→组→镜三级结构"""
    errors = []
    global_shot_no = 0

    for i, scene in enumerate(scenes):
        scene_no = scene.get("场号", i + 1)

        # 场级必需字段
        for field in REQUIRED_SCENE_FIELDS:
            if field not in scene:
                errors.append(f"场{scene_no}: 缺少必需字段 [{field}]")

        # 通用设定校验
        common = scene.get("通用设定", {})
        if not isinstance(common, dict):
            errors.append(f"场{scene_no}: 通用设定 必须是对象类型")
        else:
            for field in REQUIRED_SCENE_COMMON_FIELDS:
                if field not in common:
                    errors.append(f"场{scene_no}·通用设定: 缺少子字段 [{field}]")
            for field in FORBIDDEN_SCENE_COMMON_FIELDS:
                if field in common:
                    errors.append(f"场{scene_no}·通用设定: 禁止出现字段 [{field}]（由Agent独立处理）")

        # 组列表校验
        groups = scene.get("组列表", [])
        if not isinstance(groups, list):
            errors.append(f"场{scene_no}: 组列表 必须是数组类型")
            continue

        for j, group in enumerate(groups):
            grp_no = group.get("组号", j + 1)

            # 组级必需字段
            for field in REQUIRED_GROUP_FIELDS:
                if field not in group:
                    errors.append(f"场{scene_no}·组{grp_no}: 缺少必需字段 [{field}]")

            # 组级禁止字段
            for field in FORBIDDEN_GROUP_FIELDS:
                if field in group:
                    errors.append(f"场{scene_no}·组{grp_no}: 禁止出现字段 [{field}]（应由Agent/脚本注入）")

            shots = group.get("镜头列表", [])

            # 镜头数上限
            if len(shots) > MAX_SHOTS_PER_GROUP:
                errors.append(f"场{scene_no}·组{grp_no}: 镜头数 {len(shots)} > {MAX_SHOTS_PER_GROUP}")

            # 组时长
            dur_raw = group.get("组时长", "0")
            try:
                dur_val = float(dur_raw)
                if dur_val > MAX_GROUP_DURATION:
                    errors.append(f"场{scene_no}·组{grp_no}: 时长 {dur_val}s > {MAX_GROUP_DURATION}s")
            except (ValueError, TypeError):
                errors.append(f"场{scene_no}·组{grp_no}: 组时长格式异常 [{dur_raw}]")

            # 逐镜头检查
            for k, shot in enumerate(shots):
                shot_no = shot.get("镜号", k + 1)
                for field in REQUIRED_SHOT_FIELDS:
                    if field not in shot:
                        errors.append(f"场{scene_no}·组{grp_no}·镜{shot_no}: 缺少字段 [{field}]")

                for field, min_len in MIN_WORD_COUNT_FIELDS.items():
                    val = shot.get(field, "")
                    if len(val) < min_len:
                        errors.append(f"场{scene_no}·组{grp_no}·镜{shot_no}: {field} 字数 {len(val)} < {min_len}")

            # 时间连续性（首镜从 0 开始）
            if shots:
                first_start = shots[0].get("开始/结束时间", "")
                if not first_start.startswith("0"):
                    errors.append(f"场{scene_no}·组{grp_no}: 首镜开始时间不是 0s [{first_start}]")

    return errors


def _validate_flat_groups(groups):
    """校验旧版扁平组→镜结构（向后兼容）"""
    errors = []

    for i, group in enumerate(groups):
        grp_no = group.get("组号", i + 1)

        for field in REQUIRED_GROUP_FIELDS:
            if field not in group:
                errors.append(f"组{grp_no}: 缺少必需字段 [{field}]")

        shots = group.get("镜头列表", [])

        if len(shots) > MAX_SHOTS_PER_GROUP:
            errors.append(f"组{grp_no}: 镜头数 {len(shots)} > {MAX_SHOTS_PER_GROUP}")

        dur_raw = group.get("组时长", "0")
        try:
            dur_val = float(dur_raw)
            if dur_val > MAX_GROUP_DURATION:
                errors.append(f"组{grp_no}: 时长 {dur_val}s > {MAX_GROUP_DURATION}s")
        except (ValueError, TypeError):
            errors.append(f"组{grp_no}: 组时长格式异常 [{dur_raw}]")

        for j, shot in enumerate(shots):
            shot_no = shot.get("镜号", j + 1)
            for field in REQUIRED_SHOT_FIELDS:
                if field not in shot:
                    errors.append(f"组{grp_no}·镜{shot_no}: 缺少字段 [{field}]")

            for field, min_len in MIN_WORD_COUNT_FIELDS.items():
                val = shot.get(field, "")
                if len(val) < min_len:
                    errors.append(f"组{grp_no}·镜{shot_no}: {field} 字数 {len(val)} < {min_len}")

        if shots:
            first_start = shots[0].get("开始/结束时间", "")
            if not first_start.startswith("0"):
                errors.append(f"组{grp_no}: 首镜开始时间不是 0s [{first_start}]")

    return errors


def _dedupe(errors):
    seen = set()
    unique = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def format_report(errors):
    """格式化校验报告"""
    if not errors:
        return "✅ 全部校验通过"
    lines = [f"❌ 发现 {len(errors)} 个问题："]
    for e in errors:
        lines.append(f"  · {e}")
    return "\n".join(lines)


# ─── CLI 入口 ────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="分镜脚本校验器")
    parser.add_argument("--repair", metavar="input.json", help="从 LLM 响应文件提取并修复 JSON")
    parser.add_argument("--check", nargs="?", const=None, metavar="input.json", help="校验分镜 JSON")
    parser.add_argument("--output", "-o", metavar="output.json", help="修复结果输出路径")
    args = parser.parse_args()

    if args.repair:
        with open(args.repair, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        content = raw.get("content", raw) if isinstance(raw, dict) else raw
        if isinstance(content, dict):
            content = content.get("content", json.dumps(content))
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)

        extracted = extract_json(content)
        parsed, ok = safe_parse(extracted)
        if not ok:
            print(f"❌ JSON 修复失败: {parsed}", file=sys.stderr)
            debug_path = args.repair + ".extracted.json"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(extracted)
            print(f"  原始提取内容已写入 {debug_path}", file=sys.stderr)
            sys.exit(1)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)

            total_groups = 0
            total_shots = 0
            if isinstance(parsed, list) and len(parsed) > 0:
                first = parsed[0]
                if isinstance(first, dict) and "组列表" in first:
                    for scene in parsed:
                        groups = scene.get("组列表", [])
                        total_groups += len(groups)
                        for g in groups:
                            total_shots += len(g.get("镜头列表", []))
                    print(f"✅ 修复完成 → {args.output}  ({len(parsed)} 场, {total_groups} 组, {total_shots} 镜)")
                else:
                    for g in parsed:
                        total_shots += len(g.get("镜头列表", []))
                    print(f"✅ 修复完成 → {args.output}  ({len(parsed)} 个镜头组, {total_shots} 镜)")

        if args.check is not None:
            errors = validate_storyboard(parsed)
            print(format_report(errors))
            if errors:
                sys.exit(1)
        return

    if args.check is not None:
        target = args.check or args.output
        if not target:
            parser.error("--check 需要指定文件路径")
        with open(target, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        errors = validate_storyboard(data)
        print(format_report(errors))
        if errors:
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()