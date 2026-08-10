import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, validate_top_level, format_report

FIXED_IMAGE_SIZE = "4K"
# 竖版三视图（默认）= 9:16，横版七视图（备选）= 16:9
VALID_ASPECT_RATIOS = ["9:16", "16:9"]
FIXED_MODEL = "nano-banana-2"

# 支持的模式列表
VALID_MODES = ["global", "episode", "group"]


def validate_tasks(tasks, mode=None):
    if mode is not None and mode not in VALID_MODES:
        return [f"未知模式 '{mode}'，支持的模式：{VALID_MODES}"]
    return _validate(tasks, aspect_ratio=VALID_ASPECT_RATIOS, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)
