---
name: project-coordinator
description: 项目统筹 agent，负责管理项目全生命周期的目录结构、阶段状态、产物清单、事件日志、项目注销与打包归档。当用户需要创建项目、注销项目、打包项目、查看进度、推进阶段、追踪产物、查看日志或维护项目结构时，应使用此技能。适用于任何需要统一管理项目产物的场景。
---

# 项目统筹

负责管理项目的全生命周期，维护目录结构、阶段状态和产物清单。

## 规则

1. **操作元数据 + 移动文件**：统筹 agent 写 `.meta/projects/{id}/` 下的元数据文件，并负责将产物文件移动到 `project/{name}/` 下的正确路径
2. **绝不读产物业务内容**：统筹 agent 只操作文件路径和元数据（名称、大小、哈希、类型），以及由其他 agent 显式产出的结构化阶段清单文件（如 `妆造匹配清单.json`，作为资产同步的元数据索引，非业务文本）。绝对不打开、读取或显示剧本/设定/图像/分镜脚本等产物的内部业务内容。这是控制 token 开销的核心约束
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
>
> **跨平台提示**：在 Unix/macOS 上可跳过本章节，直接使用 bash 命令。所有 JSON 读写建议统一用 `python3 -c` 调用 json 库（跨平台最稳），避免 bash 的 locale 问题。各操作步骤的 PowerShell / bash 双套命令见下方具体章节。

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

每次通过 CLI 写入 `.json` 或 `.jsonl` 后，立即用 `RunCommand` 调用校验脚本（跨平台，python 命令在 Windows/Unix 通用）：

```bash
python {scriptsDir}/validate.py ".meta/projects/{id}/project_config.json" ".meta/projects/{id}/stages.json" ".meta/projects/{id}/manifest.json" ".meta/projects/{id}/events.jsonl"
```

校验失败 → CLI读取错误 → 修正文件 → 重新校验 → 通过后继续。

### 批量操作脚本

以下 Python 脚本将常见的多步 CLI 调用链压缩为单条命令，减少 token 开销和中间步骤：

| 脚本 | 功能 | 替代的调用链 |
|------|------|-------------|
| `write_validate.py` | 写文件 + 自动校验 | `Set-Content` + `validate.py` |
| `append_event.py` | 追加事件到 events.jsonl + 自动校验 | `Add-Content` + `validate.py` |
| `register_artifact.py` | 哈希 → 注册 → manifest 更新 → 写事件 → 全链校验 | `hash.py` + 读 manifest + 写 manifest + `validate.py` + 写事件 + `validate.py` |

#### `write_validate.py`

```bash
python "{scriptsDir}/write_validate.py" --path ".meta/projects/{id}/stages.json" --value "$jsonContent"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--path` | 是 | 目标文件路径 |
| `--value` | 是 | 写入内容（字符串） |
| `--encoding` | 否 | 编码，默认 utf-8 |
| `--pass-thru` | 否 | 返回校验结果 |

#### `append_event.py`

```bash
python "{scriptsDir}/append_event.py" --events-path ".meta/projects/{id}/events.jsonl" --timestamp "2026-05-16T10:00:00+08:00" --type "project.created" --actor "user" --data '{"name":"山与鱼"}' --project-id "uuid"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--events-path` | 是 | events.jsonl 路径 |
| `--timestamp` | 是 | ISO 8601 时间戳 |
| `--type` | 是 | 事件类型 |
| `--actor` | 是 | 触发者 |
| `--data` | 是 | 事件详情 JSON |
| `--project-id` | 否 | 关联项目 UUID |
| `--batch-id` | 否 | 关联批次 ID |
| `--pass-thru` | 否 | 返回事件 JSON |

#### `register_artifact.py`

```bash
python "{scriptsDir}/register_artifact.py" --manifest-path ".meta/projects/{id}/manifest.json" --events-path ".meta/projects/{id}/events.jsonl" --type "script" --name "01/剧本.md" --artifact-path "project/山与鱼/01/剧本.md" --stage "production" --project-id "uuid"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--manifest-path` | 是 | manifest.json 路径 |
| `--events-path` | 是 | events.jsonl 路径 |
| `--type` | 是 | 产物类型 |
| `--name` | 是 | 产物名称 |
| `--artifact-path` | 是 | 产物文件路径 |
| `--stage` | 是 | 所属阶段 |
| `--actor` | 否 | 触发者，默认 `project-coordinator`（必须是规范定义的 skill name，详见 `project_management.md` 的 events.jsonl 字段说明） |
| `--artifact-id` | 否 | 产物 ID，自动生成 |
| `--tags` | 否 | 标签列表 |
| `--project-id` | 否 | 关联项目 UUID |

该脚本自动执行：计算 SHA-256 → 标记旧条目 deprecated → 写入新条目 → 校验 manifest.json → 写入 artifact.created 事件 → 校验 events.jsonl。

### 项目定位

Coordinator 启动后，凡是针对**已存在项目**的操作（推进阶段、注销、打包、注册产物、归档、查询等），必须先定位到目标项目的 UUID。定位规则按以下优先级：

1. **orchestrator 显式传入 UUID** → 直接使用该 UUID，跳过扫描（最高优先级，最快路径）
2. **orchestrator 传入项目名** → 扫描 `.meta/projects/*/project.json`，按 `name` 字段匹配定位 UUID
3. **多项目共存且未指定** → 列出所有 active 项目（`project.json` 中 `current_stage` 非 `delivery`/`cancelled`）供用户选择，等待用户明确选择后再继续
4. **无任何项目存在** → 提示用户先执行"创建项目"流程

**扫描命令（按项目名定位）**：

```powershell
# PowerShell (Windows)：扫描所有 project.json，按 name 字段匹配
$targetName = "项目名"
$matched = @()
Get-ChildItem -Directory ".meta/projects" | ForEach-Object {
  $pj = Join-Path $_.FullName "project.json"
  if (Test-Path $pj) {
    $obj = Get-Content -Encoding UTF8 -Raw $pj | ConvertFrom-Json
    if ($obj.name -eq $targetName) {
      $matched += [PSCustomObject]@{ uuid = $_.Name; name = $obj.name; current_stage = $obj.current_stage }
    }
  }
}
if ($matched.Count -eq 0) { throw "未找到 name='$targetName' 的项目" }
if ($matched.Count -gt 1) { throw "项目名冲突：找到 $($matched.Count) 个同名项目，请改用 uuid 定位" }
$projectId = $matched[0].uuid
```

```bash
# bash (Unix/macOS)：用 python3 扫描，避免 locale 问题
python3 -c "
import json, os, sys
target = '项目名'
matched = []
base = '.meta/projects'
if not os.path.isdir(base):
    print('ERROR: 无任何项目存在', file=sys.stderr); sys.exit(1)
for d in os.listdir(base):
    pj = os.path.join(base, d, 'project.json')
    if not os.path.isfile(pj): continue
    try:
        with open(pj, 'r', encoding='utf-8') as f: obj = json.load(f)
    except Exception: continue
    if obj.get('name') == target:
        matched.append({'uuid': d, 'name': obj.get('name'), 'current_stage': obj.get('current_stage')})
if not matched:
    print(f'ERROR: 未找到 name={target!r} 的项目', file=sys.stderr); sys.exit(1)
if len(matched) > 1:
    print(f'ERROR: 项目名冲突：找到 {len(matched)} 个同名项目，请改用 uuid 定位', file=sys.stderr); sys.exit(1)
print(matched[0]['uuid'])
"
```

**列出所有 active 项目（供用户选择）**：

```powershell
# PowerShell (Windows)
Get-ChildItem -Directory ".meta/projects" | ForEach-Object {
  $pj = Join-Path $_.FullName "project.json"
  if (Test-Path $pj) {
    $obj = Get-Content -Encoding UTF8 -Raw $pj | ConvertFrom-Json
    if ($obj.current_stage -ne 'delivery' -and $obj.current_stage -ne 'cancelled') {
      [PSCustomObject]@{ uuid = $_.Name; name = $obj.name; current_stage = $obj.current_stage }
    }
  }
} | Format-Table -AutoSize
```

```bash
# bash (Unix/macOS)
python3 -c "
import json, os
base = '.meta/projects'
for d in sorted(os.listdir(base)):
    pj = os.path.join(base, d, 'project.json')
    if not os.path.isfile(pj): continue
    try:
        with open(pj, 'r', encoding='utf-8') as f: obj = json.load(f)
    except Exception: continue
    cs = obj.get('current_stage')
    if cs in ('delivery', 'cancelled'): continue
    print(f\"uuid={d}  name={obj.get('name')}  current_stage={cs}\")
"
```

> **重要**：定位 UUID 后，所有后续 CLI 操作中的 `{id}` 占位符都替换为该 UUID；`{name}` 占位符替换为 `project.json` 中的 `name` 字段值。多项目场景下未明确指定 UUID 或项目名时，**禁止猜测**，必须等待用户选择。

### 创建项目

1. 生成 UUID v4
2. 创建元数据目录：
   ```powershell
   # PowerShell (Windows)
   New-Item -ItemType Directory -Force -Path ".meta/projects/{uuid}/"
   ```
   ```bash
   # bash (Unix/macOS)
   mkdir -p ".meta/projects/{uuid}/"
   ```
3. 使用 CLI 创建 `project.json`、`stages.json`、`manifest.json`、`events.jsonl` 四个文件：
   ```powershell
   # PowerShell (Windows)：用 Set-Content -Encoding UTF8 写入初始内容（空 manifest / 空 events / project 元数据 / stages 初始化）
   Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/manifest.json" -Value '{"_version":1,"artifacts":[]}'
   Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value ""
   ```
   ```bash
   # bash (Unix/macOS)：建议用 python3 写入 JSON，避免 locale 问题
   python3 -c "
   import json, os
   os.makedirs('.meta/projects/{id}', exist_ok=True)
   with open('.meta/projects/{id}/manifest.json', 'w', encoding='utf-8') as f:
     json.dump({'_version': 1, 'artifacts': []}, f, ensure_ascii=False, indent=2)
   open('.meta/projects/{id}/events.jsonl', 'w', encoding='utf-8').close()
   "
   ```
   `project.json` 与 `stages.json` 同样按规范初始化（`stages.json` 模板见下方）。

   **`stages.json` 初始化模板**（必须按 stages.md 规范初始化为 17 阶段，每个阶段字段完整：`name` / `label` / `status` / `artifacts` / `started_at` / `completed_at`，初始 `status=pending`、`artifacts=[]`、`started_at=null`、`completed_at=null`；仅 `project_init` 初始为 `in_progress`）：

   ```json
   {
     "_version": 1,
     "current": "project_init",
     "stages": [
       { "name": "project_init",            "label": "项目初始化",            "status": "in_progress", "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "material_sorting",        "label": "前期素材归类",          "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "supervisor_extraction",   "label": "监制提取设定",          "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "global_character_tasks",  "label": "全局角色参考图任务生成", "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "global_character_art",    "label": "全局角色参考图绘制",    "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "global_prop_tasks",       "label": "全局道具参考图任务生成", "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "global_prop_art",         "label": "全局道具参考图绘制",    "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "global_scene_tasks",      "label": "全局场景参考图任务生成", "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "global_scene_art",        "label": "全局场景参考图绘制",    "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "episode_storyboard_script", "label": "剧集分镜脚本",         "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "episode_character_ref",   "label": "剧集级角色参考图生成",  "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "episode_prop_ref",        "label": "剧集级道具参考图生成",  "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "episode_scene_ref",       "label": "剧集级场景参考图生成",  "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "episode_storyboard_images", "label": "剧集分镜图绘制",       "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "asset_sync",              "label": "资产同步",              "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "video_generation",        "label": "视频生成",              "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null },
       { "name": "delivery",                "label": "交付归档",              "status": "pending",     "artifacts": [], "started_at": null, "completed_at": null }
     ]
   }
   ```

   > **阶段顺序固定**：17 阶段必须严格按上方顺序排列，不得缺漏或调整。完整阶段链见 `rules/stages.md`。各字段语义详见 `rules/project_management.md` 的 stages.json schema 说明。
4. 使用 CLI 创建项目完整骨架目录：
   ```powershell
   # PowerShell (Windows)
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/角色设定/角色参考图"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/场景设定/场景参考图"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/道具设定/道具参考图"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/人物"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/场景"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/风格"
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/道具"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/角色设定/具体设定"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/场景设定/具体设定"
   New-Item -ItemType Directory -Force -Path "project/{name}/全局依赖/道具设定/具体设定"
   # 全局设定：不再创建 `全局设定/` 子目录，改为单一占位文件 `全局依赖/全局设定.md`
   # 由 producer 在 supervisor_extraction 阶段输出（世界观、时间线、人物关系等所有全局设定合并到此文件）
   New-Item -ItemType File -Force -Path "project/{name}/全局依赖/全局设定.md"
   ```
   ```bash
   # bash (Unix/macOS)
   mkdir -p "project/{name}/全局依赖/角色设定/角色参考图" \
            "project/{name}/全局依赖/场景设定/场景参考图" \
            "project/{name}/全局依赖/道具设定/道具参考图" \
            "project/{name}/前期采样/人物" \
            "project/{name}/前期采样/场景" \
            "project/{name}/前期采样/风格" \
            "project/{name}/前期采样/道具" \
            "project/{name}/全局依赖/角色设定/具体设定" \
            "project/{name}/全局依赖/场景设定/具体设定" \
            "project/{name}/全局依赖/道具设定/具体设定"
   # 全局设定占位文件（不再创建 `全局设定/` 子目录）
   touch "project/{name}/全局依赖/全局设定.md"
   ```
5. **整理已存在的原始剧本**（如果用户提供了剧本文件）：
   - 用户指定的剧本路径 → `project/{name}/原始剧本.md`
   - 计算 SHA-256，注册到 `manifest.json`（type: `raw_script`）
   - 追加事件：`artifact.created`
   > **注意**：创建项目时**只创建目录骨架**（`前期采样/人物|场景|道具|风格/`、`全局依赖/...`），**不整理前期素材**。前期素材的归类由独立的 `material_sorting` 阶段执行（见下方"material_sorting 阶段操作流程"章节）。
6. 创建 `project_config.json`（项目运行时配置，记录用户选择的参数）：
    > **⚠️ 由你逐项询问用户填写**：Coordinator 负责向用户依次确认以下配置项。如用户不指定，使用默认值。
    > 记录用户选择后，用变量构建 JSON 写入。

    字段定义以 `.opencode/schemas/project-config.json` 为唯一来源。

    **询问配置项**：

    | 字段 | 说明 | 默认值 |
    |------|------|--------|
    | `aspect_ratio` | 画幅比例 | `16:9` |
    | `resolution` | 分辨率 | `720p` |
    | `model` | 视频生成模型中文名（见下方模型表，填写 modelName 列的值） | — |
    | `use_storyboard_images` | 是否使用分镜图作为视频参考（为 true 时将额外执行 `episode_storyboard_images` 阶段） | `false` |
    | `mode` | 生成模式 | `mixed2video` |
    | `enable_sound` | 是否生成音效 | `true` |

    **模型选择列表**（如 `libtv node -t model -o json` 查询失败，回退到手动输入模型名，**用户只需填写 modelName（中文名）**，值写入 `project_config.json` 的 `model` 字段）：

    | modelName（用户填写此列） | 说明 | VIP | 参考 modelKey（仅排查时使用） |
    |---------------------------|------|-----|------------------------------|
    | `Seedance 2.0 VIP` | 最强视频模型，15s音画同步 | ✅ | `star-video2` |
    | `Seedance 2.0 Fast VIP` | 最强视频模型快速版，15s音画同步 | ✅ | `star-video2-fast` |
    | `Happy Horse 1.0` | 阿里最新视频模型，支持多参生成 | | `happy-horse-1` |
    | `可灵 3.0 Omni` | 视频编辑模型，参考一致性，音画同出，多镜头 | ✅ | `kling-v3-omni` |
    | `可灵 3.0` | 视频生成模型，高质感，支持多镜头 | ✅ | `kling-video-o3` |

    > **重要**：`project_config.json` 的 `model` 字段直接写入上表第一列的 modelName（中文名，如 `Seedance 2.0 VIP`），**不要**写入 modelKey（如 `star-video2`）。modelKey 列仅作为内部参考，用于排查 libtv 调用问题时对照。

    `canvas_uuid` 在创建时为空，由 video-director 首次绑定时写入。

    用用户确认的变量构建 JSON 并写入：
   ```powershell
   $config = @{
     canvas_uuid = ""                         # 创建时为空，video-director 首次运行时写入
     aspect_ratio = "$aspectRatio"           # 用户确认，如 "16:9"
     resolution = "$resolution"              # 用户确认，如 "720p"
     model = "$model"                        # 用户确认的 modelName，如 "Seedance 2.0 VIP"
     use_storyboard_images = $useStoryboard  # 用户确认，如 $false
     mode = "$mode"                          # 用户确认，如 "mixed2video"
     enable_sound = $enableSound             # 用户确认，如 $true
   } | ConvertTo-Json -Depth 10
   Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/project_config.json" -Value $config
   ```
   ```bash
   # bash (Unix/macOS)：建议统一用 python3 写 JSON，避免 locale 引起的中文乱码
   python3 -c "
   import json
   config = {
     'canvas_uuid': '',
     'aspect_ratio': '$aspectRatio',
     'resolution': '$resolution',
     'model': '$model',
     'use_storyboard_images': $useStoryboard,
     'mode': '$mode',
     'enable_sound': $enableSound
   }
   with open('.meta/projects/{id}/project_config.json', 'w', encoding='utf-8') as f:
     json.dump(config, f, ensure_ascii=False, indent=2)
   "
   ```
   > `use_storyboard_images=true` 时建议同步设置 `reference_mode="multi_modal"`。

   **重要**：创建完成后，必须将 `project_config.json` 注册到 `manifest.json`（`type: "project_config"`），并追加一条 `artifact.created` 事件到 `events.jsonl`。
7. 使用 CLI 写入事件：追加一行 `project.created` 到 `events.jsonl`

### 推进阶段

1. **使用 CLI 读取 `stages.json`**，**先校验阶段完整性**：确认 `stages` 数组包含全部 17 阶段（顺序见 `rules/stages.md`），字段齐全（`name`/`label`/`status`/`artifacts`/`started_at`/`completed_at`）。若阶段缺失或字段不全，**立即报错并停止操作**，提示需修复 `stages.json` 后才能推进。

   ```powershell
   # PowerShell (Windows)
   $json = Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/stages.json"
   $stages = $json | ConvertFrom-Json
   # 校验：stages 数组长度必须为 17
   if ($stages.stages.Count -ne 17) { throw "stages.json 阶段数异常: $($stages.stages.Count)，应为 17" }
   ```
   ```bash
   # bash (Unix/macOS)：建议用 python3 解析 JSON，避免 locale 问题
   python3 -c "
   import json
   with open('.meta/projects/{id}/stages.json', 'r', encoding='utf-8') as f:
     s = json.load(f)
   required = ['project_init','material_sorting','supervisor_extraction','global_character_tasks','global_character_art','global_prop_tasks','global_prop_art','global_scene_tasks','global_scene_art','episode_storyboard_script','episode_character_ref','episode_prop_ref','episode_scene_ref','episode_storyboard_images','asset_sync','video_generation','delivery']
   actual = [x['name'] for x in s['stages']]
   assert actual == required, f'stages.json 阶段不匹配: {actual}'
   for x in s['stages']:
     for k in ('name','label','status','artifacts','started_at','completed_at'):
       assert k in x, f'阶段 {x.get(\"name\")} 缺字段 {k}'
   print('OK')
   "
   ```
2. 确认当前阶段 `status` 已为 `completed`
3. 验证前驱产物是否齐全（查 `manifest.json`）
4. **特殊校验 — 推进到 `delivery` 时**：若当前阶段为 `video_generation`，**必须**读取 `project/{项目名}/{剧集号}/视频/_manifest.json`，校验 `status` 字段：
   - `status` 为 `success`（`failed=0`）→ 正常推进
   - `status` 为 `partial`（`failed>0`）→ **禁止推进**，提示用户处理失败组后再推进
   - `_manifest.json` 不存在（未执行 `--download`）→ **禁止推进**，提示用户先执行视频下载
5. 更新 `stages.json`：将当前阶段标记 `completed`（写 `completed_at`），下一阶段标记 `in_progress`（写 `started_at`）
6. 更新 `project.json` 中的 `current_stage`
7. 写入事件：`stage.transition`

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

1. **使用 CLI 读取 manifest.json**：
   ```powershell
   # PowerShell (Windows)
   $json = Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/manifest.json"
   $manifest = $json | ConvertFrom-Json
   ```
   ```bash
   # bash (Unix/macOS)：JSON 读写建议统一用 python3 调用 json 库，避免 locale 问题
   python3 -c "
   import json
   with open('.meta/projects/{id}/manifest.json', 'r', encoding='utf-8') as f:
     m = json.load(f)
   "
   ```
2. 追加产物条目，计算 SHA-256（`python scripts/hash.py --fast "文件路径"`）
3. 若产物已存在（同名 `path`），将旧条目标记 `deprecated`
4. **使用 CLI 写入 events.jsonl**：
   ```powershell
   # PowerShell (Windows)
   Add-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value "事件JSON"
   ```
   ```bash
   # bash (Unix/macOS)：用 python3 追加，确保 UTF-8 编码与紧凑序列化
   python3 -c "
   import json
   event = {'timestamp':'...','type':'artifact.created','actor':'project-coordinator','data':{...}}
   with open('.meta/projects/{id}/events.jsonl', 'a', encoding='utf-8') as f:
     f.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
   "
   ```

### 产物归档

其他 agent 将产物输出到临时路径后，统筹 agent 负责将产物移动到项目目录下的正确位置并注册。这是多 agent 协作中统一路径管理的核心机制。

**前置约束**：
- 绝不读取产物业务内容。归档操作只涉及文件路径级别的操作（移动、重命名、计算文件大小）
- SHA-256 哈希只用于文件指纹识别，不用于 LLM 分析内容

**归档流程**：

1. 其他 agent 完成任务时，通知统筹 agent：产物在 `temp/{batch_id}/{filename}`，以及产物的 `type`、`name` 等元信息
2. 根据 `type` 和 `stage`，按路径映射规则计算目标路径（详见 [统筹管理规范](rules/project_management.md#3-产物归档路径映射)）
3. **使用 CLI 移动文件**（若目标目录不存在，先创建）：

   ```powershell
   # PowerShell (Windows)
   New-Item -ItemType Directory -Force -Path "project/{name}/目标路径/"
   Move-Item -Path "temp/{batch_id}/{filename}" -Destination "project/{name}/目标路径/{filename}" -Force
   ```
   ```bash
   # bash (Unix/macOS)
   mkdir -p "project/{name}/目标路径/"
   mv "temp/{batch_id}/{filename}" "project/{name}/目标路径/{filename}"
   ```

4. 计算文件 SHA-256 和大小（使用内置脚本，只读二进制流，不做内容解析）

   > **哈希计算**（跨平台，python 脚本在 Windows/Unix 通用）：
   > ```bash
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

5. **使用 CLI 读写 manifest.json**：

   ```powershell
   # PowerShell (Windows)
   $json = Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/manifest.json"
   $manifest = $json | ConvertFrom-Json
   # ... 追加新条目、标记旧条目 deprecated ...
   $manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/manifest.json"
   ```
   ```bash
   # bash (Unix/macOS)：建议统一用 python3 调用 json 库读写，跨平台最稳
   python3 -c "
   import json
   with open('.meta/projects/{id}/manifest.json', 'r', encoding='utf-8') as f:
     m = json.load(f)
   # ... 追加新条目、标记旧条目 deprecated ...
   with open('.meta/projects/{id}/manifest.json', 'w', encoding='utf-8') as f:
     json.dump(m, f, ensure_ascii=False, indent=2)
   "
   ```

6. **使用 CLI 追加 events.jsonl**：

   ```powershell
   # PowerShell (Windows)
   Add-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value "{json行}"
   ```
   ```bash
   # bash (Unix/macOS)
   python3 -c "
   import json
   event = {...}
   with open('.meta/projects/{id}/events.jsonl', 'a', encoding='utf-8') as f:
     f.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
   "
   ```

7. 写入更新后的 `manifest.json`
8. **校验**：调用 `validate.py` 校验 `manifest.json`、`events.jsonl` 语法

**路径映射规则**（约定，可根据项目类型扩展）：

| 产物类型 | 目标路径 |
|----------|----------|
| `raw_script` | `project/{name}/原始剧本.md` |
| `script` | `project/{name}/{episode}/剧本.md` |
| `character_design` | `project/{name}/全局依赖/角色设定/具体设定/{角色名}.md` |
| `character_ref` | `project/{name}/全局依赖/角色设定/角色参考图/{角色名}.png` |
| `scene_design` | `project/{name}/全局依赖/场景设定/具体设定/{场景名}.md` |
| `scene_ref` | `project/{name}/全局依赖/场景设定/场景参考图/{场景名}.png` |
| `prop_design` | `project/{name}/全局依赖/道具设定/具体设定/{道具名}.md` |
| `prop_ref` | `project/{name}/全局依赖/道具设定/道具参考图/{道具名}_{出现场合}_基准.png` |
| `storyboard` | `project/{name}/{episode}/分镜/{filename}` |
| `poster` | `project/{name}/{episode}/海报设计/{filename}` |
| `setting` | `project/{name}/全局依赖/全局设定.md`（单一文件，由 producer 在 supervisor_extraction 阶段输出，包含世界观、时间线、人物关系等所有全局设定） |
| `audio_reference` | `project/{name}/全局依赖/音色参考/{filename}` |
| `video` | `project/{name}/{episode}/视频/{filename}` |
| `video_manifest` | `project/{name}/{episode}/视频/_manifest.json` |

监控 `events.jsonl` 可以重建任意时刻的项目状态快照。

### material_sorting 阶段操作流程

`material_sorting` 是 `project_init` 之后的独立阶段，负责把用户上传到 `前期采样/` 下的原始素材按角色/场景/道具/风格归类，并在 manifest 中注册 `reference` 类型产物。

> **职责边界**：创建项目时**只创建 `前期采样/人物|场景|道具|风格/` 空目录骨架**，不整理素材；素材归类统一在本阶段执行，避免与创建项目流程耦合。

**前置条件**：
- `stages.json` 中 `project_init` 已 `completed`，`material_sorting` 已 `in_progress`
- 用户已把参考素材文件放入 `project/{name}/前期采样/人物|场景|道具|风格/` 目录

**操作步骤**：

1. **使用 CLI 扫描 `前期采样/` 下四个子目录**，获取所有文件列表（仅文件名，不读取内容）：

   ```powershell
   # PowerShell (Windows)
   Get-ChildItem -Recurse -File "project/{name}/前期采样" | Select-Object FullName, Name
   ```
   ```bash
   # bash (Unix/macOS)
   find "project/{name}/前期采样" -type f -print
   ```

2. **按文件名前缀归类**（约定：`{角色名/场景名/道具名/风格名}_序号.扩展名`，如 `张三_01.png` 归到 `人物/张三/`）：
   - `前期采样/人物/{文件名}` → 解析前缀（`_` 之前的部分）→ 目标子目录 `前期采样/人物/{前缀}/`
   - `前期采样/场景/{文件名}` → `前期采样/场景/{前缀}/`
   - `前期采样/道具/{文件名}` → `前期采样/道具/{前缀}/`
   - `前期采样/风格/{文件名}` → `前期采样/风格/{前缀}/`（风格可按主题归类，无前缀时整体归为 `风格/通用/`）

   > **不读取文件内容**：仅依据文件名前缀归类，前缀解析失败时保留在原子目录并提示用户。

3. **使用 CLI 移动文件**到归类后的子目录：

   ```powershell
   # PowerShell (Windows)
   New-Item -ItemType Directory -Force -Path "project/{name}/前期采样/人物/{前缀}"
   Move-Item -Path "project/{name}/前期采样/人物/{原文件名}" -Destination "project/{name}/前期采样/人物/{前缀}/{原文件名}" -Force
   ```
   ```bash
   # bash (Unix/macOS)
   mkdir -p "project/{name}/前期采样/人物/{前缀}"
   mv "project/{name}/前期采样/人物/{原文件名}" "project/{name}/前期采样/人物/{前缀}/{原文件名}"
   ```

4. **在 manifest 注册 `reference` 类型产物**（每类一个条目，`path` 指向归类后的目录）：
   - 每个 `前期采样/{分类}/{前缀}/` 目录注册为一个 `reference` 产物条目
   - `tags` 字段标注分类与名称，如 `["人物", "张三"]`
   - 调用 `python scripts/register_artifact.py` 完成注册（自动计算目录指纹、写 manifest、写事件、校验）

5. **追加事件**：`artifact.created`（actor=`project-coordinator`，每注册一个目录写一条）

6. **推进阶段**：完成后将 `material_sorting` 标记为 `completed`，下一阶段 `supervisor_extraction` 标记为 `in_progress`

**特殊说明**：若用户未提供任何前期素材（`前期采样/` 全空），跳过归类步骤，但仍需推进阶段状态，并在 `events.jsonl` 记录一条 `material_sorting.skipped` 事件（`data.reason="无前期素材"`）。

### 资产同步（asset_sync）

`asset_sync` 阶段位于 `episode_scene_ref` 之后、`video_generation` 之前。Coordinator 读取本集 `episode_character_ref` 阶段产出的"妆造匹配清单.json"，按清单把所需角色/场景/道具参考图从全局依赖目录复制到 `temp/分组素材/{剧集号}/` 下，供 video-director 直接消费。

> **铁律一致性说明**：本阶段 Coordinator 读取"妆造匹配清单.json"是铁律明确允许的行为——清单本身是其他 agent 显式产出的结构化阶段清单文件（角色名 → 参考图文件名映射），属于元数据索引，非业务文本。读取时只消费其结构化字段，不读取任何图像产物的二进制内容，也不读取剧本/分镜等业务文本内容。

**前置条件**：
- `stages.json` 中 `episode_scene_ref` 已 `completed`，`asset_sync` 已 `in_progress`
- 本集 `episode_character_ref` 阶段产出的 `妆造匹配清单.json` 已就绪（路径：`project/{项目名}/{剧集号}/角色参考图/妆造匹配清单.json`）

> **妆造匹配清单缺失降级策略**：若 `妆造匹配清单.json` 不存在（`episode_character_ref` 阶段异常或被跳过），**不得直接报错阻断**，改为执行降级流程：
> 1. 输出告警：`⚠️ 妆造匹配清单.json 不存在，降级为复制全部全局角色参考图`
> 2. 将 `全局依赖/角色设定/角色参考图/` 下的**所有** `.png` 文件复制到 `temp/分组素材/{剧集号}/角色参考/`
> 3. 在 `events.jsonl` 追加 `asset_sync.degraded` 事件，记录降级原因
> 4. 继续执行后续场景/道具参考图复制步骤
>
> 此降级策略确保 video-director 至少有角色参考图可用，避免单点依赖导致整条管线阻塞。

**操作步骤**：

1. **检查妆造匹配清单是否存在并读取**（仅元数据，不读图像内容）：

   > **降级触发**：若 `妆造匹配清单.json` 文件不存在，跳过步骤 1 的读取，直接执行降级流程：
   > - 输出告警 `⚠️ 妆造匹配清单.json 不存在，降级为复制全部全局角色参考图`
   > - 步骤 3 改为：将 `全局依赖/角色设定/角色参考图/` 下所有 `.png` 复制到 `temp/分组素材/{剧集号}/角色参考/`
   > - 在 `events.jsonl` 追加 `asset_sync.degraded` 事件（data 含 `reason: "妆造匹配清单缺失"`）
   > - 继续执行步骤 2 及后续

   ```powershell
   # PowerShell (Windows)：检查文件是否存在
   $manifestPath = "project/{项目名}/{剧集号}/角色参考图/妆造匹配清单.json"
   if (Test-Path $manifestPath) {
     $json = Get-Content -Encoding UTF8 -Raw $manifestPath
     $manifest = $json | ConvertFrom-Json
   } else {
     Write-Host "⚠️ 妆造匹配清单.json 不存在，降级为复制全部全局角色参考图"
   }
   ```
   ```bash
   # bash (Unix/macOS)
   python3 -c "
   import json, os
   p = 'project/{项目名}/{剧集号}/角色参考图/妆造匹配清单.json'
   if os.path.exists(p):
     with open(p, 'r', encoding='utf-8') as f:
       m = json.load(f)
     print(json.dumps(m, ensure_ascii=False, indent=2))
   else:
     print('⚠️ 妆造匹配清单.json 不存在，降级为复制全部全局角色参考图')
   "
   ```

2. **创建目标目录**：

   ```powershell
   # PowerShell (Windows)
   New-Item -ItemType Directory -Force -Path "temp/分组素材/{剧集号}/角色参考"
   New-Item -ItemType Directory -Force -Path "temp/分组素材/{剧集号}/场景参考"
   New-Item -ItemType Directory -Force -Path "temp/分组素材/{剧集号}/道具参考"
   New-Item -ItemType Directory -Force -Path "temp/分组素材/{剧集号}/分镜图"
   ```
   ```bash
   # bash (Unix/macOS)
   mkdir -p "temp/分组素材/{剧集号}/角色参考" "temp/分组素材/{剧集号}/场景参考" "temp/分组素材/{剧集号}/道具参考" "temp/分组素材/{剧集号}/分镜图"
   ```

3. **按清单复制角色参考图**：

   **正常模式**（清单存在）：清单中每条记录形如 `{"角色名": "张三", "参考图文件名": "张三_剧集01.png"}`，从全局依赖目录复制：

   ```powershell
   # PowerShell (Windows)
   Copy-Item -Path "project/{项目名}/全局依赖/角色设定/角色参考图/{参考图文件名}" -Destination "temp/分组素材/{剧集号}/角色参考/" -Force
   ```
   ```bash
   # bash (Unix/macOS)
   cp "project/{项目名}/全局依赖/角色设定/角色参考图/{参考图文件名}" "temp/分组素材/{剧集号}/角色参考/"
   ```

   **降级模式**（清单不存在）：复制全部全局角色参考图：

   ```powershell
   # PowerShell (Windows)
   Copy-Item -Path "project/{项目名}/全局依赖/角色设定/角色参考图/*.png" -Destination "temp/分组素材/{剧集号}/角色参考/" -Force
   ```
   ```bash
   # bash (Unix/macOS)
   cp "project/{项目名}/全局依赖/角色设定/角色参考图/"*.png "temp/分组素材/{剧集号}/角色参考/"
   ```

4. **复制本集涉及的场景参考图、道具参考图**（优先使用剧集级参考图，无剧集级时回退全局基准图）：
   - 场景参考图来源（优先）：`project/{项目名}/{剧集号}/场景参考图/*.png` → 目标 `temp/分组素材/{剧集号}/场景参考/`（覆盖同名全局基准图）
   - 场景参考图来源（回退）：`project/{项目名}/全局依赖/场景设定/场景参考图/` → 目标 `temp/分组素材/{剧集号}/场景参考/`（仅复制剧集级目录中不存在的场景）
   - 道具参考图来源（优先）：`project/{项目名}/{剧集号}/道具参考图/*.png` → 目标 `temp/分组素材/{剧集号}/道具参考/`（覆盖同名全局基准图）
   - 道具参考图来源（回退）：`project/{项目名}/全局依赖/道具设定/道具参考图/` → 目标 `temp/分组素材/{剧集号}/道具参考/`（仅复制剧集级目录中不存在的道具）
   > **道具基准文件名含出现场合**：全局基准资产文件名格式为 `{道具名}_{出现场合}_基准.png`。回退复制时需读取 `具体设定/{道具名}.md` 中的 `出现场合` 字段，匹配正确的基准文件。仅复制该道具 `出现场合` 包含当前剧集号的基准图，**禁止**复制不属于本集的道具资产。
   - 涉及清单：依据本集分镜脚本中场景/道具出场列表（由 storyboard-generator 在 `episode_storyboard_script` 阶段产出的"分组/组{N}.json"中给出，仅读取其中 `scene_refs` / `prop_refs` 字段，不读镜号描述等业务内容）
   - **复制分镜图**（仅当 `use_storyboard_images=true` 时）：分镜图来源 `project/{项目名}/{剧集号}/分镜/分镜图_*.png` → 目标 `temp/分组素材/{剧集号}/分镜图/`。分镜图由 storyboard-director 在 `episode_storyboard_images` 阶段产出、art-director 绘制

5. **在 manifest 注册 `asset_sync` 类型产物**：
   - 每个复制后的目录（`temp/分组素材/{剧集号}/角色参考/` 等）注册为一个 `asset_sync` 产物条目
   - `path` 指向复制后的目录
   - `stage`=`asset_sync`，`tags` 标注剧集号与素材类型（如 `["episode_01", "character_ref"]`）

6. **追加事件**：`artifact.created`（actor=`project-coordinator`，每个目录一条）

7. **校验**：调用 `validate.py` 校验 `manifest.json`、`events.jsonl` 语法

8. **推进阶段**：将 `asset_sync` 标记为 `completed`，下一阶段 `video_generation` 标记为 `in_progress`

**注意事项**：
- 复制而非移动：全局依赖目录下的参考图必须保留原文件，供后续剧集继续使用
- `temp/分组素材/` 下的文件由 video-director 在 `video_generation` 阶段消费，不归档到 `project/{name}/` 下
- 若清单中某个参考图文件在全局依赖目录下不存在，**立即报错**并提示用户先补充对应参考图，不得跳过
