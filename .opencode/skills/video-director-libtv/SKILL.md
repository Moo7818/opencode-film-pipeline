---
name: video-director-libtv
description: 基于 libtv CLI 的视频导演 Skill。覆盖：分镜视频化、图生视频、文生视频、AI视频生成、动效视频。通过 `libtv node -t video` / `libtv upload` / `libtv group` 等 CLI 命令完成视频生成全流程。
---

# video-director-libtv — 基于 libtv CLI 的视频导演 Skill

影视生产管线中的**「视频导演」**，负责将分镜组 JSON 通过 **libtv CLI** 转化为画布上的 video 节点并触发生成。

## 前置依赖

- 已完成 `libtv login web` 或 `libtv login phone`
- 凭证文件已就位：`.opencode/credentials/libtv_credentials.json`
- 已在画布上创建项目并已绑定画布：`libtv project use <画布UUID>`
- `libtv` CLI 版本 ≥ **1.1.1**（使用 `libtv --version` 确认；关键变化见文末）
- 分镜组 JSON 已就绪（`分组/组{N}.json`）
- `project_config.json` 已配置（字段定义见 `.opencode/schemas/project-config.json`）

## 凭证路径配置

视频导演执行 libtv CLI 命令时，通过 `LIBTV_CONFIG_DIR` 环境变量指定凭证目录：

```bash
# 设置 libtv 凭证指向工作空间的 .opencode/credentials/
$env:LIBTV_CONFIG_DIR = (Resolve-Path ".opencode/credentials").Path
```

所有调用 libtv CLI 的命令前必须先设置此环境变量，确保使用 `.opencode/credentials/libtv_credentials.json` 而非默认的 `~/.libtv/credentials.json`。

如果该文件不存在，提示用户先执行 `libtv login web --open` 或 `libtv login phone` 完成登录，然后将生成的 `~/.libtv/credentials.json` 复制到 `.opencode/credentials/libtv_credentials.json`。

## 参数查找与引用

视频导演在执行时，所有全局参数来源于 `.meta/projects/{uuid}/project_config.json`，字段映射规则见 `references/storyboard-to-libtv.md` 第 1 节「字段对应表」。分镜组本地参数来源于 `分组/组{N}.json`。

`canvas_uuid` 为特殊字段：项目创建时为空字符串，视频导演首次运行时从 `.libtv/project.json` 读取并写入配置。

| 参数 | 来源文件 | 对应 libtv 参数 | 读写 |
|------|----------|----------------|:----:|
| 画面比例 | `project_config.json → aspect_ratio` | `--set ratio` | 读 |
| 分辨率 | `project_config.json → resolution` | `--set resolution` | 读 |
| 模型 | `project_config.json → model` | `--set model` | 读 |
| ↳ 注意 | 1.1.1+ 要求填 **modelName**（中文名），如 `Seedance 2.0 VIP`，非 modelKey |
| 生成模式 | `project_config.json → mode` | `--set modeType` | 读 |
| 音频开关 | `project_config.json → enable_sound` | `--set enableSound` | 读 |
| 分镜图模式 | `project_config.json → use_storyboard_images` | 决定参考素材选取策略 | 读 |
| 画布 UUID | `.libtv/project.json → projectUuid` | `libtv project use <值>` | **写**入 `.meta/projects/{uuid}/project_config.json` |
| ↳ `project use` 副作用 | v1.1.1+ 同时将画布所属项目 `workspaceId` 与团队 `teamId` 同步写入 `.libtv/project.json` | — |
| 组时长 | `组{N}.json → 组时长` | `--set duration` | 读 |

`use_storyboard_images` 影响参考素材的连线策略（详见 `references/storyboard-to-libtv.md` 第 6 节）：为 `true` 时优先选取分镜图作为主要参考，否则以角色/场景参考图为主。

## 工作流总览

```
  1. 读取上下文                  ← project_config.json + 分组 JSON
  2. 绑定画布项目                ← libtv project use <UUID>
  3. 上传参考素材为资源节点       ← libtv upload
  4. 创建 video 节点             ← 一次性创建 或 两阶段（占位 → 查顺序 → 写引用）
  5. 批量分组运行                ← libtv group create + --run
  6. 轮询等待生成完成
  7. 报告 Coordinator 归档
```

## `{{Image N}}` 引用规则

`--left` 的传入顺序决定 `imageList` 中 `{{Image N}}` 的编号，第一个 `--left` 为 `{{Image 1}}`。

### 两种创建方式

| 方式 | 做法 | 适用场景 |
|------|------|---------|
| **一次性** | `libtv node create` 中同时传入 `--left` + `--prompt`（含引用行） | `--left` 顺序明确，可直接写引用 |
| **两阶段** | ① 创建节点（占位 prompt + `--left`）② 查询实际 `imageList` 顺序 ③ `--prompt` 写入含引用行的最终 prompt | 需要验证顺序后再写引用 |

### `--prompt` 不会触发重算

实测验证：`libtv node "节点" --prompt "新内容"` **不会**触发 `imageList` 重算。`imageList` 顺序在创建时由 `--left` 确定，后续 `--prompt` 写入保持稳定。

### 唯一会触发重算的因素

| 触发源 | 说明 |
|--------|------|
| **Web UI 加载画布** | 打开画布网页端会触发 `_lastAppliedFullyAtMs`，导致 `imageList` 按服务端内部逻辑重排 |
| **服务端自动同步** | 偶发行为，概率较低 |

**核心原则**：创建节点到 `--run` 完成之间不要打开 Web UI 查看画布。

### Prompt 格式

有参考图时：
```
请参考场景氛围{{Image 1}}和角色形象{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝}
```

无参考图时跳过引用行和空行，直接用约束行 + 分隔线 + JSON。

## 文档地图

| 内容 | 文件 |
|------|------|
| **工作流详细步骤** | [references/workflow.md](./references/workflow.md) |
| **模型选择与配置** | [references/models.md](./references/models.md) |
| **映射规则：分镜组 JSON → libtv video node** | [references/storyboard-to-libtv.md](./references/storyboard-to-libtv.md) |
| **常见场景命令序列** | [references/workflow-examples.md](./references/workflow-examples.md) |
| **自动化管线脚本（一站式）** | [references/pipeline-script.md](./references/pipeline-script.md) |

### 共享 Schema

| 内容 | 文件 |
|------|------|
| 项目全局配置字段定义 | [.opencode/schemas/project-config.json](.opencode/schemas/project-config.json) |

### 外部依赖

| 内容 | 文件 |
|------|------|
| libtv CLI 节点命令 | [libtv-cli/commands/node.md](../libtv-cli/commands/node.md) |
| libtv CLI 上传命令 | [libtv-cli/commands/upload.md](../libtv-cli/commands/upload.md) |
| libtv CLI 分组命令 | [libtv-cli/commands/group.md](../libtv-cli/commands/group.md) |
| libtv CLI 模型检索 | [libtv-cli/commands/model.md](../libtv-cli/commands/model.md) |
| libtv CLI 视频节点类型 | [libtv-cli/node-types/video.md](../libtv-cli/node-types/video.md) |
| libtv CLI 画布命令（含 workspace） | [libtv-cli/commands/project.md](../libtv-cli/commands/project.md) |
| libtv CLI 项目/工作区 | [libtv-cli/commands/workspace.md](../libtv-cli/commands/workspace.md) |

### libtv CLI v1.1.1 关键行为变化

`libtv` 从 v1.1.0 起有以下影响视频导演工作流的变化：

| 变化 | 对视频导演的影响 |
|------|------------------|
| **`--left`/`--right` 改为 ensure 模式** | 不会删除未在列表中指定的已有边。需要增删时用 `--left-add`/`--left-rm` |
| **`node --run` 阻塞等待终态** | `libtv node <名> --run` 内部完成轮询并输出终态 JSON，外部不要再封装轮询 |
| **`group --run` 阻塞等待终态** | `libtv group <组名> --run` 阻塞等待全部节点完成，stderr 每 ~3 分钟输出进度，stdout 输出终态 JSON |
| **`project use` 同步 workspaceId + teamId** | 不影响现有流程，但 `.libtv/project.json` 会多出 workspace/team 字段 |
| **`{{Node "节点名"}}` prompt 占位符** | 可替代 `{{Image N}}` 更可靠地引用已连线的上游节点 |
