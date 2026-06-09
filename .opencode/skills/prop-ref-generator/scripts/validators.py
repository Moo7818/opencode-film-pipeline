FIXED_IMAGE_SIZE = "1K"
REQUIRED_FIELDS = ["prompt", "imageSize", "aspectRatio", "filename", "images"]
FIXED_ASPECT_RATIO = "16:9"
FIXED_MODEL = "gpt-image-2"


def validate_tasks(tasks, mode):
    errors = []

    if not isinstance(tasks, list):
        return ["tasks must be a list"]

    if not tasks:
        return ["tasks is empty"]

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"[task {i}] task must be a dict, got {type(task).__name__}")
            continue

        for f in REQUIRED_FIELDS:
            if f not in task:
                errors.append(f"[task {i}] missing field: {f}")

        image_size = task.get("imageSize")
        if image_size != FIXED_IMAGE_SIZE:
            errors.append(f"[task {i}] imageSize must be {FIXED_IMAGE_SIZE}, got {image_size}")

        aspect = task.get("aspectRatio", "")
        if aspect != FIXED_ASPECT_RATIO:
            errors.append(f"[task {i}] aspectRatio must be {FIXED_ASPECT_RATIO}, got {aspect}")

        images = task.get("images", [])

        if mode == "global":
            if not isinstance(images, list) or len(images) < 1:
                errors.append(f"[task {i}] global mode requires at least 1 reference image")

        elif mode == "episode":
            if not isinstance(images, list) or len(images) < 2:
                errors.append(f"[task {i}] episode mode requires at least 2 reference images")

        else:
            errors.append(f"[task {i}] unknown mode: {mode}")

        prompt = task.get("prompt", "")

        if not isinstance(prompt, str):
            errors.append(f"[task {i}] prompt must be a string")
        else:
            if "string" in prompt.lower() and any(f"string{n}" in prompt for n in range(12)):
                errors.append(f"[task {i}] prompt not fully rendered (contains template placeholders)")

            if len(prompt.strip()) < 50:
                errors.append(f"[task {i}] prompt too short")

            if not ("六视图" in prompt or "上4下2" in prompt):
                errors.append(f"[task {i}] prompt must describe a 6-view layout (missing '六视图' or '上4下2')")

            if "场景" in prompt or "全景" in prompt:
                errors.append(f"[task {i}] prompt appears to describe a scene, not a prop")

        filename = task.get("filename", "")
        if not isinstance(filename, str) or not filename.endswith(".png"):
            errors.append(f"[task {i}] filename must end with .png")

    return errors


def validate_top_level(data):
    errors = []

    if not isinstance(data, dict):
        return ["top-level data must be a dict"]

    if "tasks" not in data:
        errors.append("missing top-level field: tasks")

    model = data.get("model")
    if model != FIXED_MODEL:
        errors.append(f"model must be {FIXED_MODEL}, got {model}")

    output_path = data.get("output_path")
    if output_path is not None and (not isinstance(output_path, str) or not output_path.strip()):
        errors.append("output_path must be a non-empty string if provided")

    return errors