#!/usr/bin/env python3
"""共享图像任务校验器

从 roles/prop/scene-ref-generator 的 validators.py 合并而来。
参数化 aspect_ratio、image_size、model，消除重复代码。
"""

import re

# 占位符残留检测：匹配 {string0}, {{Image 1}}, {style_desc} 等
_PLACEHOLDER_PATTERN = re.compile(r"\{\{?\w+\}?\}")

# prompt 最小长度（字符数）
MIN_PROMPT_LENGTH = 50


def validate_tasks(tasks, aspect_ratio="16:9", image_size="1K", model="gpt-image-2"):
    """校验图像生成任务列表

    Args:
        tasks: 任务列表
        aspect_ratio: 期望的 aspectRatio 值
        image_size: 期望的 imageSize 值
        model: 期望的 model 值

    Returns:
        错误信息列表，空列表表示校验通过
    """
    errors = []

    if not isinstance(tasks, list):
        return ["tasks must be a list"]
    if not tasks:
        return ["tasks is empty"]

    required_fields = ["prompt", "model", "imageSize", "aspectRatio", "filename", "images"]

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"[task {i}] task must be a dict, got {type(task).__name__}")
            continue

        # 基础字段检查
        for f in required_fields:
            if f not in task:
                errors.append(f"[task {i}] missing field: {f}")

        # model 非空检查
        model_val = task.get("model", "")
        if not model_val or not str(model_val).strip():
            errors.append(f"[task {i}] model is empty")

        # imageSize 检查
        image_size_val = task.get("imageSize")
        if image_size_val != image_size:
            errors.append(f"[task {i}] imageSize must be {image_size}, got {image_size_val}")

        # aspectRatio 检查
        aspect = task.get("aspectRatio", "")
        if aspect != aspect_ratio:
            errors.append(f"[task {i}] aspectRatio must be {aspect_ratio}, got {aspect}")

        # prompt 非空检查
        prompt = task.get("prompt", "")
        if not prompt or not prompt.strip():
            errors.append(f"[task {i}] prompt is empty")
        else:
            # prompt 占位符残留检测
            placeholders = _PLACEHOLDER_PATTERN.findall(prompt)
            if placeholders:
                errors.append(f"[task {i}] prompt contains unresolved placeholders: {placeholders[:5]}")

            # prompt 最小长度检查
            if len(prompt.strip()) < MIN_PROMPT_LENGTH:
                errors.append(f"[task {i}] prompt too short: {len(prompt.strip())} chars (min {MIN_PROMPT_LENGTH})")

        # images 字段校验
        images_val = task.get("images")
        if images_val is not None:
            if not isinstance(images_val, list):
                errors.append(f"[task {i}] images must be a list, got {type(images_val).__name__}")
            # images 可以为空列表（无参考图输入），非空时检查元素为字符串
            elif images_val:
                for j, img in enumerate(images_val):
                    if not isinstance(img, str) or not img.strip():
                        errors.append(f"[task {i}] images[{j}] must be a non-empty string")

        # filename 格式检查
        filename_val = task.get("filename", "")
        if filename_val and not filename_val.lower().endswith(".png"):
            errors.append(f"[task {i}] filename should end with .png, got: {filename_val}")

    return errors


def validate_top_level(data, model="gpt-image-2"):
    """校验任务列表 JSON 的顶层字段

    检查 items：
    - data 必须是 dict
    - tasks 字段必须存在且为非空 list（委托给 validate_tasks 做详细校验）
    - model（可选）：若存在则必须是非空字符串
    - output_path（可选）：若存在则必须是非空字符串
    - oss_id / oss_path（可选）：若存在则必须是非空字符串
    - 禁止额外顶层字段（additionalProperties=false）

    Args:
        data: 待校验的 JSON 对象（已解析为 dict）
        model: 期望的默认模型名称（仅做格式参考，不强制匹配）

    Returns:
        错误信息列表，空列表表示校验通过
    """
    errors = []

    if not isinstance(data, dict):
        return ["top-level must be a JSON object"]

    # tasks 是唯一必填顶层字段
    if "tasks" not in data:
        errors.append("missing top-level field: tasks")
    elif not isinstance(data["tasks"], list):
        errors.append("top-level 'tasks' must be a list")
    elif not data["tasks"]:
        errors.append("top-level 'tasks' is empty")

    # 可选字段类型检查
    optional_string_fields = ["model", "output_path", "oss_id", "oss_path"]
    for field in optional_string_fields:
        if field in data:
            val = data[field]
            if not isinstance(val, str) or not val.strip():
                errors.append(f"top-level '{field}' must be a non-empty string")

    # additionalProperties=false：只允许 tasks + 可选字段
    allowed_top_keys = {"tasks", "model", "output_path", "oss_id", "oss_path"}
    extra_keys = set(data.keys()) - allowed_top_keys
    if extra_keys:
        errors.append(f"unexpected top-level fields: {sorted(extra_keys)}")

    return errors


def format_report(errors):
    """格式化校验报告"""
    if not errors:
        return "✅ 全部校验通过"
    lines = [f"❌ 发现 {len(errors)} 个问题："]
    for e in errors:
        lines.append(f"  · {e}")
    return "\n".join(lines)
