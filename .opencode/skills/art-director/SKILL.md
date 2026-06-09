---
name: art-director
description: 使用GRSAI平台模型生成AI图像。支持 JSON 任务列表，并发提交+自动轮询+本地下载+OSS持久化。当用户需要生成图像、角色参考图、分镜图、批量图像处理、AI绘画、图片素材生成时，务必调用此技能。适用于任何需要将文本提示词转换为图像文件的场景，包括但不限于：角色参考图生成、故事板/分镜图生成、批量商品图生成、创意素材制作。即使只是简单提到"生成图片""画图""出图"也应触发此技能。输入格式见 .opencode/schemas/image-generation.json（共享 Schema，所有 Agent 通用）。
---

# 新媒体内容生成

## 规则
1. 禁止创建新脚本，直接通过 CLI 调用
2. 禁止修改用户提示词，原样传递
3. 仅使用下方命令

## 详细参考

使用前请根据需要查阅以下规则文件：

- [API 接口与凭证配置](rules/api.md) — 接口说明、环境变量、凭证加载
- [模型参数与 aspectRatio 映射](rules/models.md) — 支持模型、像素映射表、比例格式
- [日志管理规范](rules/logging.md) — 索引表、全量文档、查询场景

## CLI 入口

`{baseDir}` 指本技能目录的绝对路径，脚本通过 `__file__` 自动解析。

```bash
python {baseDir}/script/batch_generator.py [输入方式] [参数]
```

### 输入方式

| 参数 | 说明 |
|---|---|
| `--tasks ./tasks.json` | JSON 任务列表文件（每个任务可独立参数） |

### 通用参数

| 参数 | 简写 | 默认 | 说明 |
|---|---|---|---|
| `--output-dir` | `-o` | `./generated` | 输出目录 |
| `--project-dir` | `-p` | （自动检测） | 项目根目录，日志存储在 `{project_dir}/.logs/` 下。未指定时自动检测 CWD 下的 `project/` 目录（若唯一则自动使用，否则回退到 CWD） |
| `--project-id` | | （无） | 项目 UUID，写入批次日志与 `_index.json`，用于跨日志关联（与 `.meta/projects/{id}/` 一致）。也可在 JSON 任务表顶层设置 `project_id` 字段声明 |
| `--batch-type` | | （无） | 批次类型：`character_reference` / `storyboard` / `other`，用于索引分类 |
| `--model` | | （配置文件值） | 模型名称，如 `gpt-image-2`、`gpt-image-2-vip`、`nano-banana-2` |
| `--concurrency` | `-c` | `10` | 并发提交数 |
| `--poll-delay` | | `14` | 提交后等待开始轮询的延迟（秒） |
| `--poll-interval` | | `5` | 轮询间隔（秒） |
| `--max-poll-rounds` | | `60` | 最大轮询次数 |

> **日志目录自动检测**：当未显式传 `--project-dir` 时，脚本自动扫描当前工作目录下的 `project/` 目录。若 `project/` 下只有一个非隐藏子目录，自动将其作为项目根目录，`.logs` 正确落在 `project/<项目名>/.logs/` 下。若零个或多个项目目录，回退到 CWD 并打印警告。

## JSON 任务列表格式

完整规范见 [.opencode/schemas/image-generation.json](file:///d:/Dev_project/New/.opencode/schemas/image-generation.json)，所有 Agent 共享。

**要点：**

- `prompt` 是唯一必填字段，原样传递不做修改
- `model` 有两层：**任务列表声明 > 配置文件默认**
  - `task.model` 覆盖此单个任务
  - `JSON顶层.model` 覆盖整个批次
  - 什么都不指定时，走 `~/.trae-cn/media_gen_config.json` 中的 `GRSAI_MODEL`
- `oss_id` / `oss_path` / `output_path` 仅在顶层设置，批次是功能性单元，所有产物归到同一文件夹
- `urls` 字段名已废弃，请使用 `images`。脚本仍兼容读取 `urls`，但提交到 API 时统一使用 `images`

## 执行流程

```
提交阶段（并发） → 等待 poll_delay → 轮询阶段（并发） → 下载阶段
```

所有模型统一使用 `POST /v1/api/generate`（replyType=async）提交，返回 `{id, status: "running"}`
脚本根据模型前缀自动选择参数格式：`gpt-image-*` 使用像素格式 aspectRatio，`nano-banana-*` 使用比例格式 aspectRatio + imageSize
通过 `GET /v1/api/result?id=xxx` 轮询结果
状态值：`running`（进行中）、`violation`（违规）、`succeeded`（生成成功）、`failed`（任务失败）

### 分镜图 / 实拍图的后处理：COS 上传 + _file_map.json 记录

当生成任务类型为分镜图（`--batch-type storyboard`）或产出目录为 `{剧集号}/实拍/` 时，**必须在下载阶段之后**执行以下后处理：

1. 遍历所有已下载的图片（`task["local_path"]`）
2. 调用 `file_cache.py` 的 `process_urls` 将每个本地图片上传到 COS
3. 记录到 `_file_map.json`，存储位置为 `{项目路径}/.logs/_file_map.json`

```python
# 伪代码：在 batch_generator.py 下载完成后调用
from file_cache import load_file_map, save_file_map, process_urls

# 收集所有已下载的本地图片路径
local_images = [t["local_path"] for t in tasks if t.get("local_path")]

# 上传到 COS 并记录到 _file_map.json
cos_config = load_cos_config()  # 从 config.py 加载
file_map = load_file_map(logs_dir)
uploaded_urls, refs = process_urls(
    local_images,
    cos_config=cos_config,
    timestamp=timestamp,
    file_map=file_map,
    logs_dir=logs_dir,
)
```

这样 Video-director 就可以通过读取 `_file_map.json` 获取分镜图的 OSS URL，用于组装 Seedance 多模态参考素材。

## 输出格式

```json
{
  "batch_id": "batch_20250421_120000",
  "total": 3,
  "succeeded": 3,
  "failed": 0,
  "output_dir": "./generated",
  "model": "gpt-image-2-vip",
  "results": [...],
  "failed_tasks": [],
  "batch_log_path": "./generated/.logs/batch_20250421_120000.json"
}
```

失败任务会额外写入 `.logs/failed_batch_{batch_id}.json`，方便重试。

## 使用示例

```bash
# 角色参考生成
python {baseDir}/script/batch_generator.py \
  --tasks task.json \
  --output-dir "中间产物/角色参考图" \
  --project-dir "D:\Dev_project\test\project\绒暖西行" \
  --batch-type character_reference

# 分镜图生成
python {baseDir}/script/batch_generator.py \
  --tasks storyboard.json \
  --output-dir "中间产物/分镜图" \
  --project-dir "D:\Dev_project\test\project\绒暖西行" \
  --batch-type storyboard
```

## 编码注意事项（Windows PowerShell）

> 本技能处理的 JSON 任务表包含中文路径和中文 Prompt，编码错误会导致乱码式生成失败。

1. **Agent 通过 CLI（PowerShell）传入任务表文件路径时**：确保任务表 JSON 文件以 UTF-8 编码保存，且读取时使用 `-Encoding UTF8`
2. **Python 脚本已正确处理编码**：`batch_generator.py` 和 `api_client.py` 内部使用 `encoding="utf-8"` 和 `ensure_ascii=False`，可正常处理含中文的 JSON
3. **如果输出日志中出现乱码**，说明任务表 JSON 在传入前已被 PowerShell 错误编码，应检查中间步骤的文件读写是否有遗漏 `-Encoding UTF8`
4. **临时任务表文件写入 temp/ 目录时**：使用 `Set-Content -Encoding UTF8` 而非默认编码，参考 `AGENTS.md` 的「子 Agent 文件编码规范」