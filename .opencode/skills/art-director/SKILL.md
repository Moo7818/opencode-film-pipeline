---
name: art-director
description: 使用GRSAI MCP 工具生成AI图像。支持双模式：batch（批量并行，资产/一般图像）和 sequential（参考帧串行：分镜图场内用前帧成图作后帧主连续参考，场=物理空间，场间并行）。自动轮询+本地下载+OSS持久化+全局COS去重。当用户需要生成图像、角色参考图、分镜图、批量图像处理、AI绘画、图片素材生成时，务必调用此技能。适用于任何需要将文本提示词转换为图像文件的场景，包括但不限于：角色参考图生成、故事板/分镜图生成、批量商品图生成、创意素材制作。即使只是简单提到"生成图片""画图""出图"也应触发此技能。输入格式见 .opencode/schemas/image-generation.json（共享 Schema，所有 Agent 通用）。MCP 超时等相关规范见本文档「MCP 调用规范」章节。
---

# AI 图像生成

## 规则
1. 禁止修改用户提示词，原样传递
2. 通过 MCP tool 执行图像生成，禁止自行构造 HTTP 请求
3. **reference_images 路径必须是绝对路径**：MCP server 进程的 CWD 与 Agent 不同（`uv run --directory` 会改变工作目录），相对路径无法被解析。Agent 在调用 `grsai_submit_image` 前，必须将任务表中所有相对路径解析为绝对路径。`{{PREV_OUTPUT}}` 占位符和远程 URL（`https://...`）不需要转换

## 详细参考

使用前请根据需要查阅以下规则文件：

- [模型参数与 aspectRatio 映射](rules/models.md) — 支持模型、像素映射表、比例格式

## 图像生成执行

通过 MCP tool `grsai_submit_image` 提交任务 + `grsai_poll_result` 轮询结果，两步完成生图。

### 输入格式

任务 JSON 格式见 `.opencode/schemas/image-generation.json`（共享 Schema）。
字段映射：
- `prompt` → MCP tool `prompt`
- `model` → MCP tool `model`
- `aspectRatio` → MCP tool `aspect_ratio`
- `imageSize` → MCP tool `image_size`
- `images` → MCP tool `reference_images`（支持 URL、本地路径、`{{PREV_OUTPUT}}` 占位符）
- `id` / `scene` / `depends_on` / `group` → sequential 模式依赖字段（见下文执行模式）
- `mode` → 执行模式选择（`batch` / `sequential`，默认 `batch`）

### 执行模式

任务列表支持两种执行模式，由 `mode` 字段或 `depends_on` 字段自动判定。

#### 模式一：batch（默认）— 批量并行

适用于角色参考图、道具图、商品图等**无依赖**的资产生成任务。

- 所有任务相互独立，可交叉提交
- 策略：连续提交多个 `grsai_submit_image`（拿到多个 task_id），再逐个轮询 `grsai_poll_result`
- `id`、`depends_on`、`group` 字段可省略

#### 模式二：sequential — 参考帧串行（Reference-Frame Mode）

适用于分镜图等**必须用前帧成图锁定后帧空间连续**的任务。`scene` = **物理场**（连续物理空间），不是戏剧节拍编号。

**目标**：场内每一帧的成图成为下一帧的主空间连续参考（参考帧），使同空间内身份/布景/光影可继承；不是独立抽卡。产物是**单帧电影静帧**，不是宫格分镜板、不是烧字幕图。

- **执行前**：分镜任务表必须已通过 `storyboard-generator/scripts/validate_task_table.py`（含 `cast`、单帧声明、禁字幕、角色参考完整性）。未通过不得 submit
- **禁止改 prompt**：仍原样传递；质量靠上游任务表规范，不在此技能「智能改写」
- **场内串行**：同一 `scene` 全部任务按 `depends_on` 链顺序执行（**跨组不断链**）。前序 `completed` 后，用其 `image_url`（COS）**字面替换**后序 `images` 中的 `{{PREV_OUTPUT}}`，再 submit。`{{PREV_OUTPUT}}` 在任务表中须位于角色参考之后、风格之前——替换 URL 后顺序不变
- **场间并行**：不同 `scene` 无依赖，可交叉提交各场首帧
- **失败即断链**：任帧 `failed` 则停止该场后续帧，禁止跳过失败帧（否则参考帧无效）
- **禁止降级**：不得把 sequential 任务表拆成 batch 并行；不得省略 `{{PREV_OUTPUT}}` 替换
- **目检拒收（人工/回报）**：若成图出现 2×2/多宫格、字幕条、具名角色明显换装换脸，标记该帧 failed 并回报上游重写任务表，不得当合格产物入库

执行流程（场1=茶肆内含2组；场2=另一物理空间）：

```
场1: [1-1] submit → poll → completed → url_1-1
     [1-2] images 中 {{PREV_OUTPUT}} → url_1-1 → submit → poll → url_1-2
     [2-1] {{PREV_OUTPUT}} → url_1-2 → submit → …          ← 跨组，仍用参考帧
     [2-2] {{PREV_OUTPUT}} → url_2-1 → submit → …

场2: [3-1] submit → …   ← 与场1并行（不同物理场）
     [3-2] {{PREV_OUTPUT}} → url_3-1 → …
```

单场内执行步骤：
1. 解析 `images` 中本地相对路径为绝对路径（`{{PREV_OUTPUT}}` 与 `https://` 不转）
2. 提交场首帧（无 `depends_on`）→ `grsai_submit_image` → `task_id`
3. 等 5-10s → `grsai_poll_result`；`pending` 则再等再查，直到 `completed` 得 `image_url`（优先 COS 持久 URL）
4. 深拷贝下一任务 `images`，将其中**每一个** `{{PREV_OUTPUT}}` 替换为该 `image_url`
5. 再解析本地路径 → submit 下一帧 → 重复 3-5 直至场内链结束
6. 每帧完成后按 `filename` 下载到 `output_path`，便于目检链连续性

> 替换后的参考帧 URL 与角色/场景本地路径一起传入 `reference_images`。模型侧靠 prompt 的 Previous Frame Anchor 把该图当作 live set。
>
> **COS 全局去重**：本地参考图上传自动去重（路径+mtime / hash），跨项目复用。
### 调用示例

**第一步 — 提交任务**：`grsai_submit_image` → 返回 `task_id`
```
tool: grsai_submit_image
input:
  prompt: "生成全局角色参考图，..."
  model: "gpt-image-2"
  aspect_ratio: "2048x1152"
  image_size: "4K"
  reference_images: ["D:/Opencode project/New/project/.../掌柜.png", "https://..."]
```

> **路径规则**：`reference_images` 中的本地路径必须是**绝对路径**。任务表中可写相对路径，但 Agent 调用 MCP tool 前必须解析为绝对路径。远程 URL（`https://...`）和 `{{PREV_OUTPUT}}` 占位符无需转换。

**第二步 — 查询结果**：`grsai_poll_result(task_id)` → 非阻塞单次查询，立即返回
```
tool: grsai_poll_result
input:
  task_id: "从提交步骤获得的 task_id"
```

返回 `status="pending"` 时，等待 5-10s 后再次调用本工具查询。重复直到 `completed` 或 `failed`。

### 返回格式

提交返回：
```json
{
  "status": "submitted",
  "task_id": "abc123",
  "uploaded_refs": [{"local": "...", "remote": "https://...", "cached": false}]
}
```

查询返回（生成中）：
```json
{
  "status": "pending",
  "task_id": "abc123"
}
```

查询返回（生成完成）：
```json
{
  "status": "completed",
  "image_url": "https://...",
  "oss_url": "https://...",
  "task_id": "abc123"
}
```

### MCP 调用规范

#### a) 非阻塞查询策略
- `grsai_poll_result` 为**非阻塞单次查询**，立即返回当前状态（pending/completed/failed）
- 每次查询耗时 < 1s，不会触发 MCP 超时（32001）
- 调用方控制轮询节奏：submit 后等 5-10s 首次查询，若 pending 则 sleep 5-10s 后再查
- 图像生成本身可能耗时 30-120s，需要多次查询

#### b) 路径解析规则
- MCP server 进程的 CWD 与 Agent 不同（`uv run --directory` 改变了工作目录）
- 任务表 JSON 中可使用相对路径（如 `project/荼荼茶业-古装/...`）
- **Agent 调用 `grsai_submit_image` 前，必须将所有相对路径解析为绝对路径**
- 远程 URL（`https://...`）和 `{{PREV_OUTPUT}}` 占位符不需要转换

#### c) 任务执行策略

**batch 模式**（批量并行）：
- 连续提交多个 `grsai_submit_image`（拿到多个 task_id），再逐个查询 `grsai_poll_result`
- 多个 task 可交叉查询：先查 task_1，若 pending 则查 task_2，最大化利用等待时间

**sequential 模式**（参考帧串行）：
- 场间并行：不同物理场（`scene`）的首帧可交叉提交
- 场内串行：同场下一帧（跨组）必须等上一帧 `completed` + 有效 `image_url` 后，替换全部 `{{PREV_OUTPUT}}` 再提交
- 失败不跳帧；不把同场任务改 batch

#### d) 错误处理规范
- **查询返回 pending**：正常状态，sleep 5-10s 后再次查询
- **生成失败**（返回 status="failed"）：【终态】不可重试同一 task_id，检查 prompt 和参数合法性
- **网络错误**（查询请求本身失败）：检查网络/凭证后重试同一 task_id
- 所有错误应记录到事件日志，不静默吞掉

#### e) 禁止行为
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
- `mode`：`batch`（默认，无依赖资产）或 `sequential`（参考帧串行：场内链 + 场间并行）
- sequential 专属：
  - `id` — 唯一标识，供 `depends_on` 引用
  - `scene` — **物理场** ID；同场一条参考帧链，异场并行
  - `depends_on` — 直接前帧 id；其输出 URL 替换本任务全部 `{{PREV_OUTPUT}}`
  - `group` — 组（从属于场；跨组仍串在同一 `scene` 链上）
- `images` 中 `{{PREV_OUTPUT}}`（仅 sequential）：建议顺序为 角色… → `{{PREV_OUTPUT}}` → 场景 → 道具… → 风格
- `oss_id` / `oss_path` / `output_path` 仅在顶层设置，批次是功能性单元，所有产物归到同一文件夹
- `urls` 字段名已废弃，请使用 `images`
