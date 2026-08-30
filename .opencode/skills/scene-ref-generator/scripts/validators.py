import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, format_report

# 默认模式：双视图（内景 + 外景）
FIXED_IMAGE_SIZE = "4K"
FIXED_ASPECT_RATIO = "4:1"
FIXED_MODEL = "nano-banana-2"

# 备选模式：全景（左俯瞰 + 右二宫格）
PANORAMIC_IMAGE_SIZE = "1K"
PANORAMIC_ASPECT_RATIO = "2:1"
PANORAMIC_MODEL = "gpt-image-2"

# 兼容旧代码的别名
DUAL_VIEW_IMAGE_SIZE = FIXED_IMAGE_SIZE
DUAL_VIEW_ASPECT_RATIO = FIXED_ASPECT_RATIO
DUAL_VIEW_MODEL = FIXED_MODEL


def validate_tasks(tasks):
    """默认校验：双视图模式（nano-banana-2 / 4K / 4:1）"""
    return _validate(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)


def validate_tasks_panoramic(tasks):
    """备选校验：全景模式（gpt-image-2 / 1K / 2:1）"""
    return _validate(tasks, aspect_ratio=PANORAMIC_ASPECT_RATIO, image_size=PANORAMIC_IMAGE_SIZE, model=PANORAMIC_MODEL)


def validate_tasks_dual_view(tasks):
    """兼容别名：等同 validate_tasks()"""
    return _validate(tasks, aspect_ratio=DUAL_VIEW_ASPECT_RATIO, image_size=DUAL_VIEW_IMAGE_SIZE, model=DUAL_VIEW_MODEL)
