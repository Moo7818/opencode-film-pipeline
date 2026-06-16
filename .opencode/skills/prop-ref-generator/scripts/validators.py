import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, format_report

FIXED_IMAGE_SIZE = "1K"
FIXED_ASPECT_RATIO = "16:9"
FIXED_MODEL = "gpt-image-2"


def validate_tasks(tasks, mode=None):
    return _validate(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)
