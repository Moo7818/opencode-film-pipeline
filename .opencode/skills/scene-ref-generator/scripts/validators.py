import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, format_report

FIXED_IMAGE_SIZE = "1K"
FIXED_ASPECT_RATIO = "2:1"
FIXED_MODEL = "gpt-image-2"

DUAL_VIEW_IMAGE_SIZE = "4K"
DUAL_VIEW_ASPECT_RATIO = "16:9"
DUAL_VIEW_MODEL = "gpt-image-2-vip"


def validate_tasks(tasks):
    return _validate(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)


def validate_tasks_dual_view(tasks):
    return _validate(tasks, aspect_ratio=DUAL_VIEW_ASPECT_RATIO, image_size=DUAL_VIEW_IMAGE_SIZE, model=DUAL_VIEW_MODEL)
