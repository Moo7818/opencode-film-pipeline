---
name: video-director-libtv
description: 基于 libtv CLI 的视频导演 Skill。覆盖：分镜视频化、图生视频、文生视频、AI视频生成、动效视频。通过 `libtv node -t video` / `libtv upload` / `libtv group` 等 CLI 命令完成视频生成全流程。
---

# video-director-libtv — 基于 libtv CLI 的视频导演 Skill

影视生产管线中的**「视频导演」**，负责将分镜组（JSON 或 MD 格式）通过 **libtv CLI** 转化为画布上的 video 节点。

## 前置依赖

- 已完成 `libtv login web` 或 `libtv login phone`
- 凭证文件已就位：`.opencode/credentials/libtv_credentials.json`
- 已创建项目工作区（workspace）和对应剧集的画布（canvas），详见 `references/workflow.md` 步骤 2a/2b
- `libtv` CLI 版本 ≥ **1.1.1**（使用 `libtv --version` 确认；关键变化见文末）
- 分镜组文件已就绪（`分组/组{N}.json` 或 `分组/组{N}.md` 格式均可）
- `project_config.json` 已配置（字段定义见 `.opencode/schemas/project-config.json`）

## 凭证路径配置

视频导演执行 libtv CLI 命令时，通过 `LIBTV_CONFIG_DIR` 环境变量指定凭证目录：

```bash
# 设置 libtv 凭证指向工作空间的 .opencode/credentials/
$env:LIBTV_CONFIG_DIR = (Resolve-Path ".opencode/credentials").Path
```

所有调用 libtv CLI 的命令前必须先设置此环境变量，确保使用 `.opencode/credentials/libtv_credentials.json` 而非默认的 `~/.libtv/credentials.json`。

如果该文件不存在，提示用户先执行 `libtv login web --open` 或 `libtv login phone` 完成登录，然后将生成的 `~/.libtv/credentials.json` 复制到 `.opencode/credentials/libtv_credentials.json`。完整的凭证管理（登录、登出、同步、多账号隔离）流程见 `.opencode/rules/credential-management.md`。

## 参数查找与引用

视频导演在执行时，所有全局参数来源于 `.meta/projects/{uuid}/project_config.json`，字段映射规则见 `references/storyboard-to-libtv.md` 第 1 节「字段对应表」。分镜组本地参数来源于 `分组/组{N}.json`。

`workspace_id` 和 `episodes` 为特殊字段：项目创建时不初始化，视频导演首次运行时创建/绑定后写入。`workspace_id` 对应项目工作区（一个项目一个），`episodes.{剧集号}.canvas_uuid` 对应每集的画布（每个剧集一个）。

| 参数 | 来源文件 | 对应 libtv 参数 | 读写 |
|------|----------|----------------|:----:|
| 画面比例 | `project_config.json → aspect_ratio` | `--set ratio` | 读 |
| 分辨率 | `project_config.json → resolution` | `--set resolution` | 读 |
| 模型 | `project_config.json → model` | `--set model` | 读 |
| ↳ 注意 | 1.1.1+ 要求填 **modelName**（中文名），如 `Seedance 2.0 VIP`，非 modelKey |
| ↳ 硬约束 | `project_config.json` 中 `model` 字段**必须填 modelName**（中文名），**禁止填 modelKey**（如 `kling-v3-omni`、`star-video2`）。libtv 1.1.1+ 直接使用该字段值作为 modelName，**不做 modelKey → modelName 转换**。读取后直接用作 `--set model` 的值，无需任何映射 |
| 生成模式 | `project_config.json → mode` | `--set modeType` | 读 |
| 音频开关 | `project_config.json → enable_sound` | `--set enableSound` | 读 |
| 参考图模式 | `project_config.json → reference_image_mode` | 决定参考素材选取策略 | 读 |
| 工作区 ID | `project_config.json → workspace_id` | `libtv workspace use <值>` | **写**入 `project_config.json` |
| 画布 UUID | `project_config.json → episodes.{剧集号}.canvas_uuid` | `libtv project use <值>` | **写**入 `project_config.json` 的 `episodes` 映射 |
| ↳ `project use` 副作用 | v1.1.1+ 同时将画布所属项目 `workspaceId` 与团队 `teamId` 同步写入 `.libtv/project.json` | — |
| 组时长 | `组{N}.json → 组时长` | `--set duration` | 读 |
| 音色参考目录 | `project_config.json → has_audio_reference` | 仅作参考；音色参考由 Agent 通过 `--voice-refs` 显式指定上传 | 读 |
| 禁止运行 | `project_config.json → suppress_run` | `true` 时**无条件拒绝** `--run`，只做准备工作 | 读 |

`reference_image_mode` 影响参考素材的连线策略（详见 `references/storyboard-to-libtv.md` 第 6 节）：`visual_anchor`（默认）时自动按场号匹配视觉锚点图作为场景连续性参考；`storyboard_images` 时自动扫描分镜图按组号匹配；`none` 时不自动添加参考图，Agent 仅使用角色/场景/道具参考图。

## 工作流总览

```
  1. 读取上下文                  ← project_config.json + 分组文件（JSON 或 MD）
  2. 创建/绑定工作区 + 画布      ← workspace use（项目级） + project use（剧集级）
  3. 上传参考素材为资源节点       ← libtv upload（按需上传，仅上传 --refs/--voice-refs 指定的素材）
  4. 创建 video 节点             ← 一次性创建 或 两阶段（占位 → 查顺序 → 写引用）
  5. [可选] 批量建组             ← libtv group create（--no-group 可跳过；默认只建组，不运行）
  6. [可选] 运行视频生成         ← libtv group --run（仅当用户明确要求时）
  7. 轮询等待生成完成
  8. 报告 Coordinator 归档       ← 含产物注册要求（见下方）
```

### 步骤 8 产物注册要求

video-director 完成视频生成后，须向 Coordinator 报告并确保以下产物被注册到 `manifest.json`：

| 产物 | type | 路径 | 注册条件 |
|------|------|------|---------|
| 每个视频文件 | `video` | `project/{项目名}/{剧集号}/视频/组{N}.mp4` | `--download` 执行后 |
| 下载清单 | `video_manifest` | `project/{项目名}/{剧集号}/视频/_manifest.json` | `--download` 执行后 |

> **Coordinator 推进校验**：Coordinator 在将 `video_generation` 标记为 `completed` 并推进到 `delivery` 前，**必须**读取 `_manifest.json`，校验 `status` 字段。仅当 `status` 为 `success`（`failed=0`）时方可推进；`partial` 时须提示用户处理失败组后再推进。

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

**引用描述行**由 agent 根据参考图文件名中的语义信息，用自然语言描述每个参考图的用途，后接 `{{Image N}}` 占位符。N 编号与 `--left` 传入顺序一致（第1个 → `{{Image 1}}`）。

**分组文件格式支持**：
- **JSON 格式**（`组{N}.json`）：原样拷贝完整 JSON 内容到 prompt
- **MD 格式**（`组{N}.md`）：读取 MD 文件的全部内容作为视频生成提示词

有参考图时：
```
{名称}{类型}参考{{Image 1}}、{名称}{类型}参考{{Image 2}}

画面严禁出现任何字幕，无配乐
---
{提示词内容}
```

> **提示词内容来源（由 `project_config.json` 的 `video_prompt_mode` 控制）**：
> - `optimized`（默认）：加载 seedance-prompt-optimizer 技能，按其「分镜脚本适配模式」将组文件适配为 Seedance 工程型指令提示词后填入。适配规则：台词逐字保留转 `{}`、心理活动外化为身体细节、运镜单一、补画质风格约束词。
> - `raw`：组文件内容原样填入（JSON 完整读取原样粘贴 / MD 读取全部内容）。

引用行格式统一为 `{名称}{类型}参考{{Image N}}`，参考图按类型排序：**分镜图（按镜号）→ 视觉锚点（按场号）→ 角色 → 道具 → 音色**：
- 文件名 `角色_掌柜` → `掌柜角色参考{{Image N}}`
- 文件名 `场景_茶馆` → `茶馆场景参考{{Image N}}`
- 文件名 `道具_平板` → `平板道具参考{{Image N}}`
- 文件名 `分镜_组1_镜1` → `镜头1参考{{Image N}}`（分镜图按镜号编号引用，非辅助参考）
- 文件名 `分镜_组1_镜2` → `镜头2参考{{Image N}}`
- 文件名 `视觉锚点_场1` → `场1视觉锚点参考{{Image N}}`（视觉锚点按场号引用，同场各组共享）

> `reference_image_mode=storyboard_images` 时，分镜图由脚本自动扫描 `{剧集号}/分镜/分镜图/` 目录上传，无需在 `--refs` 中手动指定。
>
> `reference_image_mode=visual_anchor`（默认）时，视觉锚点图由脚本自动扫描 `{剧集号}/分镜/视觉锚点/` 目录上传，按组文件的场号自动匹配，无需在 `--refs` 中手动指定。
>
> 场景通常不引用（分镜图/视觉锚点已含场景信息）。

无参考图时跳过引用行和空行，直接用约束行 + 分隔线 + 组文件内容。

**MD 格式示例**（当分组文件为 `组1.md` 时）：
```
场景参考{{Image 1}}、角色参考{{Image 2}}

画面严禁出现任何字幕，无配乐
---
# 组1

## 组叙事概述
城市天际线航拍，镜头从高空俯瞰逐渐下降

## 镜头列表
1. **镜头1**：5秒，航拍城市全景
2. **镜头2**：3秒，镜头下降至街道
```

## Prompt 传递方式

**禁止**将完整 prompt 直接作为 `--prompt "..."` 内联参数传递到 CLI。分镜 JSON 含大量特殊字符（引号、换行），直接内联会导致：
- Shell 引号嵌套爆炸（PowerShell / bash 均受影响）
- 命令行长度限制（Windows 8191 字符；Unix ARG_MAX 也会触发）

**必须使用临时 Python 脚本**传递 prompt（跨平台方案，macOS / Linux / Windows 通用）。标准流程：

```python
# temp/create_group1.py
#!/usr/bin/env python3
import os
import subprocess
import sys

# 设置 libtv 凭证目录（指向工作空间 .opencode/credentials/）
os.environ["LIBTV_CONFIG_DIR"] = os.path.abspath(".opencode/credentials")

# Prompt 内容（Python 三引号字符串可自由包含 " 和换行）
prompt = """一岛角色参考{{Image 1}}、现代南京长江边场景参考{{Image 2}}

画面严禁出现任何字幕，无配乐
---
{组 JSON 内容，原样拷贝}
"""

cmd = [
    "libtv", "node", "create", "组1", "-t", "video",
    "--prompt", prompt,
    "--set", "model=Seedance 2.0 VIP",
    "--set", "modeType=mixed2video",
    "--set", "duration=5",
    "--left", "角色_一岛",
    "--left", "场景_现代南京长江边",
]

result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(1)
```

执行命令（跨平台一致）：
```bash
# Unix/macOS 和 Windows 通用
python3 temp/create_group1.py
```

优势：
- **跨平台**：macOS / Linux / Windows 通用，无需依赖 PowerShell
- **无引号嵌套**：Python 三引号字符串 `"""..."""` 内可自由包含 `"` 和换行
- **无长度限制**：脚本文件不受命令行长度限制
- **便于调试**：脚本文件可作为执行记录保留（`temp/` 目录文件禁止删除）

### 两阶段更新 prompt

两阶段方式中，更新 prompt 同样使用临时 Python 脚本：

```python
# temp/update_prompt_group1.py
#!/usr/bin/env python3
import os
import subprocess
import sys

os.environ["LIBTV_CONFIG_DIR"] = os.path.abspath(".opencode/credentials")

prompt = """一岛角色参考{{Image 1}}、现代南京长江边场景参考{{Image 2}}

画面严禁出现任何字幕，无配乐
---
{组 JSON 内容，原样拷贝}
"""

cmd = ["libtv", "node", "组1", "--prompt", prompt]

result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(1)
```

执行命令：
```bash
python3 temp/update_prompt_group1.py
```

### ⛔ Prompt 硬约束（必须遵守）

1. **引用格式统一**：引用行格式为 `{名称}{类型}参考{{Image N}}`（如 `掌柜角色参考{{Image 1}}`），分镜图为 `镜头{M}参考{{Image N}}`，视觉锚点为 `场{N}视觉锚点参考{{Image N}}`
2. **提示词内容保真**：`video_prompt_mode=raw` 时组文件内容必须原样粘贴，不得概括、摘要、改写；`video_prompt_mode=optimized`（默认）时组文件经 seedance-prompt-optimizer 适配后填入，适配须遵守其适配铁律（台词逐字保留、关键信息不遗漏、不添加原文件没有的创意内容）
3. **禁止省略约束行**：`画面严禁出现任何字幕，无配乐` 和 `---` 分隔线必须保留，不得省略
4. **禁止修改引用格式**：引用行必须使用 `{{Image N}}` 格式（如 `{{Image 1}}`），不得替换为 `{{Node uuid}}` 等其他格式。`{{Image N}}` 由 libtv 服务端自动解析为节点引用
5. **禁止擅自截断**：不得以任何理由（字符限制、长度限制等）截断或省略 JSON 内容
6. **⛔ 禁止使用选角参考图**：`{角色名}_选角.png` 是 Tier 1 选角资产（白T恤+灰背景），**绝对不能**用于视频生成。脚本已自动过滤，Agent 在手动指定 `--refs` 时也必须确保不引用选角资产。应使用 Tier 2 妆造资产（`{角色名}_默认.png` 或 `{角色名}_{妆造名}.png`）
7. **参考选取由 Agent 判断**：脚本不做自动匹配，Agent 必须读取每个分组的实际内容，判断出场的角色/场景/道具，通过 `--refs` 显式指定。未指定 `--refs` 的分组将以纯文生视频模式生成（无参考图）
8. **违规后果**：违反上述任一条款将导致视频生成质量下降，视为 agent 执行错误

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
