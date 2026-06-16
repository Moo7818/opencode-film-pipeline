---
name: art-director
description: 使用GRSAI平台模型生成AI图像。支持 JSON 任务列表，并发提交+自动轮询+本地下载+OSS持久化。当用户需要生成图像、角色参考图、分镜图、批量图像处理、AI绘画、图片素材生成时，务必调用此技能。适用于任何需要将文本提示词转换为图像文件的场景，包括但不限于：角色参考图生成、故事板/分镜图生成、批量商品图生成、创意素材制作。即使只是简单提到"生成图片""画图""出图"也应触发此技能。输入格式见 .opencode/schemas/image-generation.json（共享 Schema，所有 Agent 通用）。
---

# AI 图像生成

## 规则
1. 禁止修改用户提示词，原样传递
2. 通过 MCP tool 执行图像生成，禁止自行构造 HTTP 请求

## 详细参考

使用前请根据需要查阅以下规则文件：

- [模型参数与 aspectRatio 映射](rules/models.md) — 支持模型、像素映射表、比例格式

## 图像生成执行

通过 MCP tool `grsai_batch_generate` 执行批量生图。

### 输入格式

任务 JSON 格式不变（仍按 `.opencode/schemas/image-generation.json` 生成），
字段映射：
- `prompt` → MCP tool `prompt`
- `model` → MCP tool `model`
- `aspectRatio` → MCP tool `aspect_ratio`
- `imageSize` → MCP tool `image_size`
- `images` → MCP tool `reference_images`
- `filename` → MCP tool `filename`

### 调用示例

```
tool: grsai_batch_generate
input:
  tasks:
    - prompt: "生成全局角色参考图，..."
      model: "gpt-image-2"
      aspect_ratio: "2048x1152"
      image_size: "4K"
      filename: "character_01.png"
  output_dir: "./generated/角色参考图"
  concurrency: 10
```

### 返回格式

```json
{
  "batch_id": "batch_20260616_120000",
  "total": 5,
  "succeeded": 5,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "status": "completed",
      "image_url": "https://...",
      "local_path": "./generated/角色参考图/character_01.png"
    }
  ]
}
```

### 单张生成

如需生成单张图片（而非批量），使用 `grsai_generate_image`：
```
tool: grsai_generate_image
input:
  prompt: "..."
  model: "gpt-image-2"
  aspect_ratio: "16:9"
  image_size: "4K"
```

## 模型差异说明

脚本根据模型前缀自动选择参数格式：
- `gpt-image-*` 使用像素格式 aspectRatio（如 `2048x1152`）
- `nano-banana-*` 使用比例格式 aspectRatio（如 `16:9`）+ imageSize

## JSON 任务列表格式

完整规范见 [.opencode/schemas/image-generation.json](../schemas/image-generation.json)，所有 Agent 共享。

**要点：**

- `prompt` 是唯一必填字段，原样传递不做修改
- `model` 有两层：**任务列表声明 > 配置文件默认**
  - `task.model` 覆盖此单个任务
  - `JSON顶层.model` 覆盖整个批次
- `oss_id` / `oss_path` / `output_path` 仅在顶层设置，批次是功能性单元，所有产物归到同一文件夹
- `urls` 字段名已废弃，请使用 `images`
