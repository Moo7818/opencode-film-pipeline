---
name: project-coordinator
description: 项目统筹 agent，负责管理项目全生命周期的目录结构、阶段状态、产物清单、事件日志、项目注销与打包归档。当用户需要创建项目、注销项目、打包项目、查看进度、推进阶段、追踪产物、查看日志或维护项目结构时，应使用此技能。适用于任何需要统一管理项目产物的场景。
---

# 项目统筹

负责管理项目的全生命周期，维护目录结构、阶段状态和产物清单。

## 规则

1. **操作元数据 + 移动文件**：统筹 agent 写 `.meta/projects/{id}/` 下的元数据文件，并负责将产物文件移动到 `project/{name}/` 下的正确路径
2. **绝不读产物内容**：统筹 agent 只操作文件路径和元数据（名称、大小、哈希、类型），绝对不打开、读取或显示任何产物的内部内容。这是控制 token 开销的核心约束
3. **所有操作必须记录**：每次阶段推进、产物归档、项目变更必须追加到 `events.jsonl`
4. **状态不可逆**：阶段一旦标记为 `completed`，不可回退
5. **唯一推进者**：只有统筹 agent 可以推进 `stages.json` 的阶段流转
6. **先读后写**：修改前必须先读取当前状态，避免并发覆盖
7. **写后必校验**：每次写入 `.json` / `.jsonl` 文件后，必须调用 `scripts/validate.py` 校验语法，校验通过才能继续

## CLI 约束（重要）

**所有文件操作必须通过 `RunCommand` CLI 执行，严禁使用 `Read`/`Write`/`DeleteFile` 等文件读写工具。** 原因：工作空间规则禁止对 `.opencode/` 以外的路径使用文件工具，否则会触发 IDE 交互式对话框，打断自动化流程。

| 操作类型 | 允许方式 | 禁止方式 |
|---------|---------|---------|
| 读取文件内容（非产物） | `RunCommand` → `Get-Content -Encoding UTF8` | `Read` 工具 |
| 写入文件 | `RunCommand` → `Set-Content -Encoding UTF8` 或 `New-Item` | `Write` 工具 |
| 创建目录 | `RunCommand` → `New-Item -ItemType Directory -Force` | — |
| 移动/复制文件 | `RunCommand` → `Move-Item` / `Copy-Item` | — |
| 删除文件/目录 | `RunCommand` → `Remove-Item -Force` | `DeleteFile` 工具 |
| 读取 JSON（解析用） | 先用 CLI 读取文件内容，或使用 `python -c "import json; ..."` | `Read` 工具直接读 .json |
| 写 JSON/JSONL | `RunCommand` → `Set-Content -Encoding UTF8` | `Write` 工具 |

## PowerShell 编码最佳实践（Windows）

> 如果工作环境是 Windows + PowerShell 5，以下规则必须遵守，否则中文路径/内容会乱码报错。

1. **避免使用 HERE-string（`@"..."@` / `@'...'@`）**：多行 HERE-string 在 PowerShell 5 中与 UTF-8 中文内容组合时，会因为代码页编码差异导致解析失败。改为逐条简单命令。
2. **所有文件写入指定 `-Encoding UTF8`**：
   ```powershell
   Set-Content -Path "文件路径" -Value "内容" -Encoding UTF8
   # 或写入多行：
   @"
   第1行
   第2行
   "@ | Set-Content -Path "文件路径" -Encoding UTF8
   ```
   使用管道输入时可规避 HERE-string 变量展开问题。
3. **含中文的路径用双引号包裹**：
   ```powershell
   Get-Content -Path "project/清悠居_思辰龙飞凤舞/剧本.md" -Encoding UTF8
   ```
4. **读取文件用 `-Encoding UTF8`**：
   ```powershell
   $content = Get-Content -Path "文件路径" -Encoding UTF8 -Raw
   ```
5. **检测编码**：如果 `Get-Content` 返回乱码，尝试：
   ```powershell
   $content = Get-Content -Path "文件路径" -Encoding UTF8 -Raw
   # 如果还有问题，文件可能是 BOM 格式：
   $bytes = [System.IO.File]::ReadAllBytes("文件路径")
   ```

### 校验脚本

```bash
python {scriptsDir}/validate.py <file_path>...
```

- `{scriptsDir}` 指本技能 `scripts/` 目录的绝对路径
- 支持同时传入多个文件路径
- 退出码 0 表示全部通过，1 表示存在错误
- 遇到校验失败时，读取错误信息，修正文件后重新校验，通过后再继续后续操作

## 详细参考

使用前请先阅读统筹管理规范，了解完整的数据结构定义：

- [统筹管理规范](rules/project_management.md) — 目录结构、数据格式、工作流

具体操作规则：

- [阶段与状态管理](rules/stages.md) — 阶段创建、推进、查询
- [产物追踪](rules/manifest.md) — 产物注册、更新、废弃
- [事件审计](rules/events.md) — 事件日志的写入与查询
- [日志聚合](rules/logs.md) — 批次日志的监控与聚合

## 操作流程

```
用户请求 → CLI读取当前状态 → CLI执行操作 → CLI更新状态文件 → 校验 JSON 语法 → CLI写入事件日志 → 响应
```

每次通过 CLI 写入 `.json` 或 `.jsonl` 后，立即用 `RunCommand` 调用校验脚本：

```powershell
python {scriptsDir}/validate.py ".meta/projects/{id}/project_config.json" ".meta/projects/{id}/stages.json" ".meta/projects/{id}/manifest.json" ".meta/projects/{id}/events.jsonl"
```

校验失败 → CLI读取错误 → 修正文件 → 重新校验 → 通过后继续。

### 批量操作脚本

以下 PowerShell 脚本将常见的多步 CLI 调用链压缩为单条命令，减少 token 开销和中间步骤：

| 脚本 | 功能 | 替代的调用链 |
|------|------|-------------|
| `write-validate.ps1` | 写文件 + 自动校验 | `Set-Content` + `validate.py` |
| `append-event.ps1` | 追加事件到 events.jsonl + 自动校验 | `Add-Content` + `validate.py` |
| `register-artifact.ps1` | 哈希 → 注册 → manifest 更新 → 写事件 → 全链校验 | `hash.py` + 读 manifest + 写 manifest + `validate.py` + 写事件 + `validate.py` |

#### `write-validate.ps1`

```powershell
& "{scriptsDir}/write-validate.ps1" -Path ".meta/projects/{id}/stages.json" -Value $jsonContent
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `-Path` | 是 | 目标文件路径 |
| `-Value` | 是 | 写入内容（字符串） |
| `-Encoding` | 否 | 编码，默认 UTF8 |
| `-PassThru` | 否 | 返回校验结果 |

#### `append-event.ps1`

```powershell
& "{scriptsDir}/append-event.ps1" -EventsPath ".meta/projects/{id}/events.jsonl" -Timestamp "2026-05-16T10:00:00+08:00" -Type "project.created" -Actor "user" -Data '{"name":"山与鱼"}' -ProjectId "uuid"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `-EventsPath` | 是 | events.jsonl 路径 |
| `-Timestamp` | 是 | ISO 8601 时间戳 |
| `-Type` | 是 | 事件类型 |
| `-Actor` | 是 | 触发者 |
| `-Data` | 是 | 事件详情 JSON |
| `-ProjectId` | 否 | 关联项目 UUID |
| `-BatchId` | 否 | 关联批次 ID |
| `-PassThru` | 否 | 返回事件 JSON |

#### `register-artifact.ps1`

```powershell
& "{scriptsDir}/register-artifact.ps1" -ManifestPath ".meta/projects/{id}/manifest.json" -EventsPath ".meta/projects/{id}/events.jsonl" -Type "script" -Name "01/剧本.md" -ArtifactPath "project/山与鱼/01/剧本.md" -Stage "production" -ProjectId "uuid"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `-ManifestPath` | 是 | manifest.json 路径 |
| `-EventsPath` | 是 | events.jsonl 路径 |
| `-Type` | 是 | 产物类型 |
| `-Name` | 是 | 产物名称 |
| `-ArtifactPath` | 是 | 产物文件路径 |
| `-Stage` | 是 | 所属阶段 |
| `-Actor` | 否 | 触发者，默认 coordinator |
| `-ArtifactId` | 否 | 产物 ID，自动生成 |
| `-Tags` | 否 | 标签数组 |
| `-ProjectId` | 否 | 关联项目 UUID |

该脚本自动执行：计算 SHA-256 → 标记旧条目 deprecated → 写入新条目 → 校验 manifest.json → 写入 artifact.created 事件 → 校验 events.jsonl。

### 创建项目

1. 生成 UUID v4
2. 创建元数据目录：`RunCommand` → `New-Item -ItemType Directory -Force -Path ".meta/projects/{uuid}/"`
3. 使用 CLI 创建 `project.json`、`stages.json`、`manifest.json`、`events.jsonl` 四个文件（`Set-Content -Encoding UTF8`）
4. 使用 CLI 创建项目完整骨架目录：
   ```powershell
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/角色参考图"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/场景参考图"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/道具参考图"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/人物"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/场景"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/风格"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/道具"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/角色设定/具体设定"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/场景设定/具体设定"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/道具设定/具体设定"
   ```
5. **整理已存在的原始剧本**（如果用户提供了剧本文件）：
   - 用户指定的剧本路径 → `project/{name}/原始剧本.md`
   - 计算 SHA-256，注册到 `manifest.json`（type: `raw_script`）
   - 追加事件：`artifact.created`
6. **整理已存在的前期素材**（如果用户提供了参考图）：
   - 用户告知每个文件的分类（人物/场景/风格/道具），或按文件所在目录名判断
   - 按分类移动到 `前期采样/{分类}/{文件名}`
   - 计算 SHA-256，注册到 `manifest.json`（type: `reference`）
   - 追加事件：`artifact.created`
 7. 创建 `project_config.json`（项目运行时配置，记录用户选择的参数）：
    > **⚠️ 由你逐项询问用户填写**：Coordinator 负责向用户依次确认以下配置项。如用户不指定，使用默认值。
    > 记录用户选择后，用变量构建 JSON 写入。

    字段定义以 `.opencode/schemas/project-config.json` 为唯一来源。

    **询问配置项**：

    | 字段 | 说明 | 默认值 |
    |------|------|--------|
    | `aspect_ratio` | 画幅比例 | `16:9` |
    | `resolution` | 分辨率 | `480p` |
    | `model` | 视频生成模型（见下方模型表） | — |
    | `use_storyboard_images` | 是否使用分镜图作为视频参考 | `false` |
    | `mode` | 生成模式 | `mixed2video` |
    | `enable_sound` | 是否生成音效 | `true` |

    **模型选择列表**（如 `libtv node -t model -o json` 查询失败，回退到手动输入模型名，值写入 `project_config.json` 的 `model` 字段）：

    | modelKey | modelName | 说明 | VIP |
    |----------|-----------|------|-----|
    | `star-video2` | Seedance 2.0 VIP | 最强视频模型，15s音画同步 | ✅ |
    | `star-video2-fast` | Seedance 2.0 Fast VIP | 最强视频模型快速版，15s音画同步 | ✅ |
    | `happy-horse-1` | Happy Horse 1.0 | 阿里最新视频模型，支持多参生成 | |
    | `kling-v3-omni` | **可灵 3.0 Omni** | 视频编辑模型，参考一致性，音画同出，多镜头 | ✅ |
    | `kling-video-o3` | **可灵 3.0** | 视频生成模型，高质感，支持多镜头 | ✅ |

    `canvas_uuid` 在创建时为空，由 video-director 首次绑定时写入。

    用用户确认的变量构建 JSON 并写入：
   ```powershell
   $config = @{
     canvas_uuid = ""                         # 创建时为空，video-director 首次运行时写入
     aspect_ratio = "$aspectRatio"           # 用户确认，如 "16:9"
     resolution = "$resolution"              # 用户确认，如 "720p"
     model = "$model"                        # 用户确认，如 "star-video2"
     use_storyboard_images = $useStoryboard  # 用户确认，如 $false
     mode = "$mode"                          # 用户确认，如 "mixed2video"
     enable_sound = $enableSound             # 用户确认，如 $true
   } | ConvertTo-Json -Depth 10
   Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/project_config.json" -Value $config
   ```
   > `use_storyboard_images=true` 时建议同步设置 `reference_mode="multi_modal"`。

   **重要**：创建完成后，必须将 `project_config.json` 注册到 `manifest.json`（`type: "project_config"`），并追加一条 `artifact.created` 事件到 `events.jsonl`。
8. 使用 CLI 写入事件：追加一行 `project.created` 到 `events.jsonl`

### 推进阶段

1. 读取 `stages.json`，确认当前阶段已完成
2. 验证前驱产物是否齐全（查 `manifest.json`）
3. 更新 `stages.json`：将当前阶段标记 `completed`，下一阶段标记 `in_progress`
4. 更新 `project.json` 中的 `current_stage`
5. 写入事件：`stage.transition`

### 注销项目

完全清除项目的所有痕迹。**操作不可逆**，删除前建议先打包归档。

**流程**：

1. 读取 `project.json` 获取项目名称和 UUID
2. （可选建议）推荐用户先执行打包操作
3. 记录一条 `project.deleted` 事件到 `events.jsonl`（必须在删除文件前写入）
4. 删除 `project/{name}/` 整个实际项目目录
   - Windows: `Remove-Item -Recurse -Force project/{name}/`
   - Unix: `rm -rf project/{name}/`
5. 删除 `.meta/projects/{id}/` 整个元数据目录
   - Windows: `Remove-Item -Recurse -Force .meta/projects/{id}/`
   - Unix: `rm -rf .meta/projects/{id}/`
6. 返回操作结果摘要（项目名称、UUID、删除的文件路径列表）

### 打包项目

将项目元数据和实际项目目录打包成一个 ZIP 文件，便于归档或传输。打包操作不删除原文件。

**流程**：

1. 读取 `project.json` 获取项目信息（name, id）
2. 确认项目目录 `project/{name}/` 存在
3. 确认元数据目录 `.meta/projects/{id}/` 存在
4. 创建输出目录 `temp/`（如果不存在）
5. 生成 ZIP 文件名：`temp/{name}_{id前8位}_{YYYYMMDD}.zip`
   示例：`temp/海权复兴·大国归位_f038db17_20260516.zip`
6. 生成 ZIP 文件，包含以下内容：
   - `project/{name}/` → ZIP 内的 `project/{name}/` 目录
   - `.meta/projects/{id}/` → ZIP 内的 `.meta/projects/{id}/` 目录
   - ZIP 根目录额外存放一个 `manifest.txt`，包含项目概要信息
7. `manifest.txt` 格式：
   ```
   项目名称: {name}
   UUID: {id}
   创建时间: {created_at}
   最后更新: {updated_at}
   当前阶段: {current_stage}
   产物数量: {artifacts_count}
   状态: active|archived|cancelled
   ```
8. 写入事件：`project.archived` 到 `events.jsonl`
9. 返回 ZIP 文件路径和内容清单

### 注册产物

其他 agent 创建产物后，统筹 agent 在 `manifest.json` 中注册该产物。

1. **使用 CLI 读取 manifest.json**：`Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/manifest.json"`
2. 追加产物条目，计算 SHA-256（`python scripts/hash.py --fast "文件路径"`）
3. 若产物已存在（同名 `path`），将旧条目标记 `deprecated`
4. **使用 CLI 写入 events.jsonl**：`Add-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value "事件JSON"`

### 批量注册产物（Router 后处理调用）

当 Router 传入产物清单时，按以下流程执行：

1. 读取产物清单（`_artifacts` 列表）
2. 对每个产物项：
   a. 验证文件是否存在
   b. 调用 `register-artifact.ps1` 注册到 manifest.json
   c. 调用 `append-event.ps1` 追加 `artifact.created` 事件
3. 校验 manifest.json 和 events.jsonl 语法
4. 返回注册结果摘要

### 产物归档

其他 agent 将产物输出到临时路径后，统筹 agent 负责将产物移动到项目目录下的正确位置并注册。这是多 agent 协作中统一路径管理的核心机制。

**前置约束**：
- 绝不读取产物内容。归档操作只涉及文件路径级别的操作（移动、重命名、计算文件大小）
- SHA-256 哈希只用于文件指纹识别，不用于 LLM 分析内容

**归档流程**：

1. 其他 agent 完成任务时，通知统筹 agent：产物在 `temp/{batch_id}/{filename}`，以及产物的 `type`、`name` 等元信息
2. 根据 `type` 和 `stage`，按路径映射规则计算目标路径（详见 [统筹管理规范](rules/project_management.md#3-产物归档路径映射)）
3. **使用 CLI 移动文件**：`RunCommand` → `Move-Item -Path "temp/{batch_id}/{filename}" -Destination "project/{name}/目标路径/{filename}" -Force`
   - 若目标目录不存在，先创建：`New-Item -ItemType Directory -Force -Path "project/{name}/目标路径/"`
4. 计算文件 SHA-256 和大小（使用内置脚本，只读二进制流，不做内容解析）

   > **哈希计算**：
   > ```powershell
   > python scripts/hash.py --fast "project/{name}/目标路径/{filename}"
   > ```
   > 输出格式：
   > ```
   > PATH=绝对路径
   > HASH=sha256-xxxxxxxx 或 fast-{mtime_ns}-{size}（图片文件使用快速指纹）
   > SIZE=字节数
   > ```
   > 支持同时传入多个文件路径，批量计算。不要创建自定义哈希脚本。
   > 
   > **`--fast` 说明**：图片文件（.png/.jpg/.jpeg/.gif/.webp）跳过全量 SHA-256 读取，改用修改时间+大小快速指纹，避免读入多 MB 图片文件造成 I/O 开销。文本文件始终使用完整 SHA-256。

5. **使用 CLI 读写 manifest.json**：`Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/manifest.json"` → 解析 JSON → 修改 → `Set-Content -Encoding UTF8`
6. **使用 CLI 追加 events.jsonl**：`Add-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value "{json行}"`
7. 写入更新后的 `manifest.json`
8. **校验**：调用 `validate.py` 校验 `manifest.json`、`events.jsonl` 语法

**路径映射规则**（约定，可根据项目类型扩展）：

| 产物类型 | 目标路径 |
|----------|----------|
| `raw_script` | `project/{name}/原始剧本.md` |
| `script` | `project/{name}/{episode}/剧本.md` |
| `character_design` | `project/{name}/全局依赖/角色设定/{角色名}/角色设定.md` |
| `character_ref` | `project/{name}/全局依赖/角色参考图/{角色名}.png` |
| `scene_design` | `project/{name}/全局依赖/场景设定/{场景名}/场景设定.md` |
| `scene_ref` | `project/{name}/全局依赖/场景参考图/{场景名}.png` |
| `prop_design` | `project/{name}/全局依赖/道具设定/{道具名}/道具设定.md` |
| `prop_ref` | `project/{name}/全局依赖/道具参考图/{道具名}.png` |
| `storyboard` | `project/{name}/{episode}/分镜/{filename}` |
| `poster` | `project/{name}/{episode}/海报设计/{filename}` |
| `setting` | `project/{name}/全局依赖/全局设定/{filename}` |
| `audio_reference` | `project/{name}/全局依赖/音色参考/{filename}` |

监控 `events.jsonl` 可以重建任意时刻的项目状态快照。
