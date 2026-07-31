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

通过 MCP tool `grsai_submit_image` 提交任务 + `grsai_poll_result` 轮询结果，两步完成生图。

### 输入格式

任务 JSON 格式不变（仍按 `.opencode/schemas/image-generation.json` 生成），
字段映射：
- `prompt` → MCP tool `prompt`
- `model` → MCP tool `model`
- `aspectRatio` → MCP tool `aspect_ratio`
- `imageSize` → MCP tool `image_size`
- `images` → MCP tool `reference_images`

### 调用示例

**第一步 — 提交任务**：`grsai_submit_image` → 返回 `task_id`
```
tool: grsai_submit_image
input:
  prompt: "生成全局角色参考图，..."
  model: "gpt-image-2"
  aspect_ratio: "2048x1152"
  image_size: "4K"
  reference_images: ["https://..."]
```

**第二步 — 轮询结果**：`grsai_poll_result(task_id)` → 返回生成结果
```
tool: grsai_poll_result
input:
  task_id: "从提交步骤获得的 task_id"
  poll_delay: 5
  poll_interval: 3
  max_poll_rounds: 60
```

### 返回格式

提交返回：
```json
{
  "status": "submitted",
  "task_id": "abc123",
  "uploaded_refs": [{"local": "...", "remote": "https://..."}]
}
```

轮询返回：
```json
{
  "status": "completed",
  "image_url": "https://...",
  "oss_url": "https://...",
  "task_id": "abc123"
}
```

### MCP 调用规范

#### a) MCP 工具执行超时
- 当前 MCP 框架超时已设为 `experimental.mcp_timeout=600000ms`（10分钟），见 opencode.json
- 单次生图轮询默认参数：`poll_delay=5, poll_interval=3, max_poll_rounds=60`（总最长约 185s）
- 在此超时范围内可安全执行单张任务

#### b) 批量任务策略
- 逐个调用 `grsai_submit_image` 拿到所有 task_id，再逐个调用 `grsai_poll_result` 轮询
- 多张任务可交叉提交：先连续提交多个 `grsai_submit_image`（拿到多个 task_id），再逐个轮询，缩短总等待时间
- 单个 task 轮询超时后，可先轮询其他已提交的 task，最后回来增加 `max_poll_rounds` 重试

#### c) 错误处理规范
- **轮询超时**（返回 status="timeout"）：增加 `max_poll_rounds` 后重试 `grsai_poll_result`
- **生成失败**（返回 status="failed"）：【终态】不可重试同一 task_id，检查 prompt 和参数合法性
- **连续失败**（返回连续失败错误）：检查网络/凭证后重试
- 所有错误应记录到事件日志，不静默吞掉

#### d) 禁止行为
- 禁止自行构造 HTTP 请求调用 GRSAI API（必须通过 MCP tool）
- 禁止修改用户提示词

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
