---
name: art-director
description: 使用GRSAI MCP 工具生成AI图像。支持 JSON 任务列表，并发提交+自动轮询+本地下载+OSS持久化。当用户需要生成图像、角色参考图、分镜图、批量图像处理、AI绘画、图片素材生成时，务必调用此技能。适用于任何需要将文本提示词转换为图像文件的场景，包括但不限于：角色参考图生成、故事板/分镜图生成、批量商品图生成、创意素材制作。即使只是简单提到"生成图片""画图""出图"也应触发此技能。输入格式见 .opencode/schemas/image-generation.json（共享 Schema，所有 Agent 通用）。MCP 超时等相关规范见本文档「MCP 调用规范」章节。
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
  output_dir: "./output/角色参考图"
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
      "local_path": "./output/角色参考图/character_01.png"
    }
  ]
}
```

### 单张生成

如需生成单张图片（而非批量），使用两步工作流：

**第一步 — 提交任务**：`grsai_submit_image` → 返回 `task_id`
```
tool: grsai_submit_image
input:
  prompt: "..."
  model: "gpt-image-2"
  aspect_ratio: "2048x1152"
  image_size: "4K"
```

**第二步 — 轮询结果**：`grsai_poll_result(task_id)` → 返回生成结果
```
tool: grsai_poll_result
input:
  task_id: "从提交步骤获得的 task_id"
  poll_delay: 5
  poll_interval: 3
  max_poll_rounds: 20
```

### MCP 调用规范

#### a) MCP 工具执行超时
- 当前 MCP 框架超时已设为 `experimental.mcp_timeout=600000ms`（10分钟），见 opencode.json
- 单次生图轮询默认参数：`poll_delay=5, poll_interval=3, max_poll_rounds=20`（总最长约 65s）
- 在此超时范围内可安全执行单张或小批量（≤10 张）任务

#### b) 批量任务策略
- **小批量（≤10 张）**：使用 `grsai_batch_generate`（默认模式，一次性提交+轮询+下载）
- **大批量（>10 张）**：使用 `batch_type="submit_only"` 仅提交拿到 task_id，然后分多次调用 `grsai_poll_result` 分批轮询
- 或逐个调用 `grsai_submit_image` + `grsai_poll_result` 分批处理
- `concurrency` 建议值：10（默认），可根据网络状况调整

#### c) 错误处理规范
- **轮询超时**（返回 status="timeout"）：建议等待后重试 `grsai_poll_result`
- **连续失败**（返回连续失败错误）：检查网络/凭证后重试
- **API 错误**（返回 status="failed"）：检查 prompt 和参数合法性
- 所有错误应记录到事件日志，不静默吞掉

#### d) 禁止行为
- 禁止自行构造 HTTP 请求调用 GRSAI API（必须通过 MCP tool）
- 禁止修改用户提示词
- 禁止在单次 `grsai_batch_generate` 中提交超过 30 个任务（避免超时）

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
