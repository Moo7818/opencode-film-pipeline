# Phase 4 Spec：Validators 整合

> 目标：合并三个 ref-generator 的重复 validators 为共享模块

## 输入上下文

读取以下文件：
- `.opencode/skills/roles-ref-generator/scripts/validators.py`（96 行）
- `.opencode/skills/prop-ref-generator/scripts/validators.py`（87 行）
- `.opencode/skills/scene-ref-generator/scripts/validators.py`（84 行）

三个文件的差异仅在：
- `FIXED_ASPECT_RATIO`：roles/prop = "16:9"，scene = "2:1"
- `validate_tasks()` 函数签名：roles/prop 有 `mode` 参数，scene 无

## 任务

### 1. 创建共享模块

创建 `.opencode/scripts/validators/image_task_validator.py`：

```python
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
```

### 2. 改造各 ref-generator 的 validators.py

**roles-ref-generator/scripts/validators.py**：

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, format_report

FIXED_IMAGE_SIZE = "1K"
FIXED_ASPECT_RATIO = "16:9"
FIXED_MODEL = "gpt-image-2"


def validate_tasks(tasks, mode=None):
    return _validate(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)
```

**prop-ref-generator/scripts/validators.py**：

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, format_report

FIXED_IMAGE_SIZE = "1K"
FIXED_ASPECT_RATIO = "16:9"
FIXED_MODEL = "gpt-image-2"


def validate_tasks(tasks, mode=None):
    return _validate(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)
```

**scene-ref-generator/scripts/validators.py**：

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
from image_task_validator import validate_tasks as _validate, format_report

FIXED_IMAGE_SIZE = "1K"
FIXED_ASPECT_RATIO = "2:1"
FIXED_MODEL = "gpt-image-2"


def validate_tasks(tasks):
    return _validate(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)
```

### 3. MCP server 轻量防御

在 `.opencode/mcp-servers/grsai-server/server.py` 的 `grsai_batch_generate` 处理中，在并发执行前增加检查：

```python
# 在 run_task 之前添加
for i, task in enumerate(tasks):
    if not task.get("prompt", "").strip():
        return [TextContent(type="text", text=json.dumps({
            "error": f"task {i}: prompt is empty"
        }))]
    if not task.get("model") and not default_model:
        return [TextContent(type="text", text=json.dumps({
            "error": f"task {i}: no model specified and no default model configured"
        }))]
```

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/scripts/validators/image_task_validator.py` | 新建 |
| `.opencode/skills/roles-ref-generator/scripts/validators.py` | 改写为调用共享模块 |
| `.opencode/skills/prop-ref-generator/scripts/validators.py` | 改写为调用共享模块 |
| `.opencode/skills/scene-ref-generator/scripts/validators.py` | 改写为调用共享模块 |
| `.opencode/mcp-servers/grsai-server/server.py` | 修改（添加轻量防御） |

## 验收

```bash
# 1. 共享 validator 语法正确
python -c "import ast; ast.parse(open('.opencode/scripts/validators/image_task_validator.py').read()); print('shared validator syntax OK')"

# 2. 各 ref-generator validators 可导入
for skill in roles-ref-generator prop-ref-generator scene-ref-generator; do
  python -c "
import sys; sys.path.insert(0, '.opencode/skills/$skill/scripts')
from validators import validate_tasks
print('$skill validators import OK')
"
done

# 3. 共享 validator 校验通过
python -c "
import sys; sys.path.insert(0, '.opencode/scripts/validators')
from image_task_validator import validate_tasks

tasks = [{'prompt': 'test', 'imageSize': '1K', 'aspectRatio': '16:9', 'filename': 'test.png', 'images': []}]
errors = validate_tasks(tasks, aspect_ratio='16:9')
assert errors == [], f'Unexpected errors: {errors}'

# aspectRatio 不匹配应报错
tasks_bad = [{'prompt': 'test', 'imageSize': '1K', 'aspectRatio': '2:1', 'filename': 'test.png', 'images': []}]
errors = validate_tasks(tasks_bad, aspect_ratio='16:9')
assert len(errors) > 0, 'Should have errors for wrong aspectRatio'

print('validation logic OK')
"

# 4. 空 prompt 检查
python -c "
import sys; sys.path.insert(0, '.opencode/scripts/validators')
from image_task_validator import validate_tasks
tasks = [{'prompt': '', 'imageSize': '1K', 'aspectRatio': '16:9', 'filename': 't.png', 'images': []}]
errors = validate_tasks(tasks, aspect_ratio='16:9')
assert any('empty' in e for e in errors), 'Should detect empty prompt'
print('empty prompt check OK')
"
```
