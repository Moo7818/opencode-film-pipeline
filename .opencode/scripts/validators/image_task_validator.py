#!/usr/bin/env python3
"""共享图像任务校验器

从 roles/prop/scene-ref-generator 的 validators.py 合并而来。
参数化 aspect_ratio、image_size、model，消除重复代码。
"""


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

    required_fields = ["prompt", "imageSize", "aspectRatio", "filename", "images"]

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"[task {i}] task must be a dict, got {type(task).__name__}")
            continue

        # 基础字段检查
        for f in required_fields:
            if f not in task:
                errors.append(f"[task {i}] missing field: {f}")

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

    return errors


def format_report(errors):
    """格式化校验报告"""
    if not errors:
        return "✅ 全部校验通过"
    lines = [f"❌ 发现 {len(errors)} 个问题："]
    for e in errors:
        lines.append(f"  · {e}")
    return "\n".join(lines)
