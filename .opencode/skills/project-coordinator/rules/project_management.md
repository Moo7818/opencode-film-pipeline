# 项目统筹管理规范

项目统筹 agent（project-coordinator）的操作手册。定义了项目从创建到交付全生命周期的目录结构、数据规范和操作流程。

---

## 1. 项目目录结构

```
{workspace_root}/
│
├── .meta/projects/{id}/               # 统筹管理区（相对路径 = .meta/...）
│   ├── project.json                       # 项目元数据
│   ├── stages.json                        # 阶段状态机
│   ├── manifest.json                      # 产物清单
│   └── events.jsonl                       # 事件溯源日志
│
├── project/
│   ├── {项目名}/                               # 项目名，如"山与鱼"
│   ├── 原始剧本.md                         # 项目原始剧本（raw_script 类型）
│   ├── project_config.json                 # 项目运行时配置（画幅比例/分辨率/模型/分镜图模式）
│   │
│   ├── 前期采样/                           # 用户提供的参考素材
│   │   ├── 人物/                          # 角色参考图
│   │   ├── 场景/                          # 场景参考图
│   │   ├── 风格/                          # 影像风格参考图
│   │   └── 道具/                          # 道具参考图
│   │
│   ├── 全局依赖/                           # 全剧共用的设定
│   │   ├── 全局设定.md                     # 单一文件：世界观、时间线、人物关系等所有全局设定（由 producer 在 supervisor_extraction 阶段输出，coordinator 创建项目时占位）
│   │   ├── 角色设定/                       # 角色清单 + 按角色拆分的设定
│   │   │   ├── 角色设定.md                # 入口文档：角色清单及路径索引
│   │   │   ├── 具体设定/                  # 独立角色文档（扁平文件）
│   │   │   │   ├── {角色名1}.md
│   │   │   │   └── {角色名2}.md
│   │   │   └── 角色参考图/                # 角色基准 PNG
│   │   ├── 场景设定/
│   │   │   ├── 场景设定.md                # 入口文档：场景清单及路径索引
│   │   │   ├── 具体设定/                  # 独立场景文档（扁平文件）
│   │   │   │   └── {场景名}.md
│   │   │   └── 场景参考图/                # 场景参考 PNG
│   │   ├── 道具设定/
│   │   │   ├── 道具设定.md                # 入口文档：道具清单及路径索引
│   │   │   ├── 具体设定/                  # 独立道具文档（扁平文件）
│   │   │   │   └── {道具名}.md
│   │   │   └── 道具参考图/                # 道具参考 PNG（{道具名}_{出现场合}_基准.png）
│   │
│   ├── 01/                                # 第 1 集
│   │   ├── 剧本.md                        # 分集剧本（script 类型）
│   │   ├── 分镜/                          # 分镜图 PNG + 分镜脚本.json
│   │   └── 海报设计/                       # 海报任务（按需）
│   ├── 02/
│   │   └── ...
│   └── ...
│
└── {其他项目}/
    └── ...
```

`{id}` 是项目的 UUID，与 `{项目名}` 一一对应。建议在 `project.json` 中记录映射关系。

**路径基准说明**：目录树以 `{workspace_root}/` 为根。所有代码操作路径必须以 `project/` 为前缀（相对于 workspace root），例如项目内容文件的完整相对路径为 `project/{name}/原始剧本.md`。元数据路径使用 `.meta/projects/{id}/` 前缀。

`temp/` 目录下存放打包项目的 ZIP 归档文件，文件名为 `{项目名}_{UUID前8位}_{YYYYMMDD}.zip`。

> **写后必校验**：每次写入或更新 `.json` / `.jsonl` 文件后，必须调用 `scripts/validate.py` 校验语法，校验通过才能继续后续操作。详见 [SKILL.md](../SKILL.md#校验脚本)。

---

## 2. 统筹管理区 — `.meta/projects/{id}/`

此目录对用户不可见，是统筹 agent 的私有工作区。所有文件由统筹 agent 读写，其他 agent 只读。

> **协调边界**：统筹 agent 的写操作范围包括：
> - `.meta/projects/{id}/` 下的元数据文件（`project.json`、`stages.json`、`manifest.json`、`events.jsonl`）
> - 将产物文件从临时路径移动到 `project/{name}/` 下的正确路径
> - **绝不读取产物文件的内容**（详见 [manifest.md](manifest.md#核心约束)）
>
> **操作约束**：所有文件操作必须通过 `RunCommand` CLI 执行（`Get-Content`/`Set-Content`/`Move-Item`/`Remove-Item` 等），**禁止使用 `Read`/`Write`/`DeleteFile` 等文件工具**，否则会触发 IDE 交互确认对话框，破坏自动化流程。

### 2.1 `project.json` — 项目元数据

```json
{
  "_version": 1,
  "id": "a1b2c3d4-...",
  "name": "山与鱼",
  "type": "animation_series",
  "status": "active",
  "created_at": "2026-05-16T10:00:00+08:00",
  "updated_at": "2026-05-16T12:00:00+08:00",
  "description": "一部关于...的动画剧集",
  "current_stage": "supervisor_extraction"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `_version` | int | 数据格式版本，用于向后兼容 |
| `id` | string | UUID |
| `name` | string | 项目名称，对应 `project/{name}/` |
| `type` | string | 项目类型：`animation_series` / `film` / `episode` / `other` |
| `status` | string | `active` / `archived` |
| `current_stage` | string | 当前所处阶段，与 `stages.json` 同步 |

### 2.2 `stages.json` — 阶段状态机

```json
{
  "_version": 1,
  "current": "supervisor_extraction",
  "stages": [
    {
      "name": "project_init",
      "label": "项目初始化",
      "status": "completed",
      "started_at": "2026-05-16T10:00:00+08:00",
      "completed_at": "2026-05-16T10:30:00+08:00",
      "artifacts": ["原始剧本.md"]
    },
    {
      "name": "material_sorting",
      "label": "前期素材归类",
      "status": "completed",
      "started_at": "2026-05-16T10:30:00+08:00",
      "completed_at": "2026-05-16T11:00:00+08:00",
      "artifacts": ["前期采样/"]
    },
    {
      "name": "supervisor_extraction",
      "label": "监制提取设定",
      "status": "in_progress",
      "started_at": "2026-05-16T11:00:00+08:00",
      "completed_at": null,
      "artifacts": ["角色设定/", "场景设定/", "道具设定/"]
    },
    {
      "name": "global_character_tasks",
      "label": "全局角色参考图任务生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "global_character_art",
      "label": "全局角色参考图绘制",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "global_prop_tasks",
      "label": "全局道具参考图任务生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "global_prop_art",
      "label": "全局道具参考图绘制",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "global_scene_tasks",
      "label": "全局场景参考图任务生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "global_scene_art",
      "label": "全局场景参考图绘制",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "episode_storyboard_script",
      "label": "剧集分镜脚本",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "episode_character_ref",
      "label": "剧集级角色参考图生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "episode_prop_ref",
      "label": "剧集级道具参考图生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "episode_scene_ref",
      "label": "剧集级场景参考图生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "episode_storyboard_images",
      "label": "剧集分镜图绘制",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "asset_sync",
      "label": "资产同步",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "video_generation",
      "label": "视频生成",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    },
    {
      "name": "delivery",
      "label": "交付归档",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifacts": []
    }
  ]
}
```

**阶段状态流转：** `pending` → `in_progress` → `completed`

只有统筹 agent 可以推进阶段状态。`completed` 的状态不可逆转。

**stages.json schema 说明**：

顶层字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `_version` | int | 是 | 数据格式版本，当前为 `1` |
| `current` | string | 是 | 当前所处阶段的 `name`，与 `stages` 数组中某个元素的 `name` 一致；与 `project.json` 的 `current_stage` 同步 |
| `stages` | array | 是 | 阶段数组，**必须严格按规范顺序包含 17 个阶段**（见 `rules/stages.md`），不得缺漏或调整顺序 |

`stages` 数组元素字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 阶段标识，与 `stages.md` 阶段定义表一致（如 `project_init`、`material_sorting` 等 17 个） |
| `label` | string | 是 | 阶段中文标签，用于展示 |
| `status` | string | 是 | 阶段状态：`pending` / `in_progress` / `completed` |
| `artifacts` | array<string> | 是 | 本阶段产出的产物路径或名称列表；初始为 `[]`，阶段完成后由 coordinator 填入 |
| `started_at` | string\|null | 是 | 阶段开始时间（ISO 8601 含时区）；未开始时为 `null` |
| `completed_at` | string\|null | 是 | 阶段完成时间（ISO 8601 含时区）；未完成时为 `null` |

**初始化约束**：coordinator 创建项目时必须按 `rules/stages.md` 的 17 阶段顺序初始化 `stages.json`，每个阶段 `status="pending"`、`artifacts=[]`、`started_at=null`、`completed_at=null`，仅 `project_init` 初始为 `in_progress`。**禁止**只初始化部分阶段或省略字段。

**推进时校验**：每次推进阶段前，coordinator 必须先读 `stages.json` 校验阶段完整性（17 阶段齐全、字段齐全），缺失或字段不全则**立即报错**，不得继续推进。

### 2.3 `manifest.json` — 产物清单

```json
{
  "_version": 1,
  "artifacts": [
    {
      "id": "art_001",
      "type": "script",
      "name": "01/剧本.md",
      "path": "project/山与鱼/01/剧本.md",
      "stage": "production",
      "status": "final",
      "created_at": "2026-05-21T10:00:00+08:00",
      "updated_at": "2026-05-21T15:00:00+08:00",
      "hash": "sha256-xxxx",
      "size": 12345,
      "tags": ["episode_01"]
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 产物类型：`raw_script` / `script` / `character_design` / `storyboard` / `poster` / `reference` / `setting` / `audio_reference` / `other` |
| `status` | string | `draft` / `review` / `final` / `deprecated` |
| `hash` | string | 文件内容 SHA-256，用于检测变更 |
| `tags` | string[] | 自定义标签，方便检索 |

agent 在创建或更新产物时，应同步更新 `manifest.json`。`deprecated` 表示该文件已被废弃但仍保留。

### 2.4 `events.jsonl` — 事件溯源日志

每行一个 JSON 对象，追加写入：

```json
{"timestamp":"2026-05-16T10:00:00+08:00","type":"project.created","actor":"user","data":{"name":"山与鱼"}}
{"timestamp":"2026-05-16T10:05:00+08:00","type":"stage.transition","actor":"project-coordinator","data":{"from":"","to":"project_init","reason":"项目初始化"}}
{"timestamp":"2026-05-16T11:00:00+08:00","type":"artifact.created","actor":"producer","data":{"artifact_id":"art_001","type":"script","path":"project/山与鱼/01/剧本.md"}}
{"timestamp":"2026-05-16T12:00:00+08:00","type":"stage.transition","actor":"project-coordinator","data":{"from":"project_init","to":"material_sorting","reason":"项目初始化完成"}}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | string | ISO 8601 时间戳，含时区 |
| `type` | string | `project.created` / `stage.transition` / `artifact.created` / `artifact.updated` / `artifact.deprecated` / `batch.submitted` / `batch.completed` / `error` / `其他自定义事件` |
| `actor` | string | 触发者，**必须是 opencode.json 中定义的 skill name**：`user` / `producer` / `storyboard-generator` / `roles-ref-generator` / `scene-ref-generator` / `prop-ref-generator` / `art-director` / `video-director-libtv` / `project-coordinator`。**禁止**使用 `script_writer`、`character-director`、`prop-maker`、`set-designer`、`storyboard-director`、`video-director`、`coordinator` 这类未在 skill 目录中定义的名（`character-director` 实际对应 skill 是 `roles-ref-generator`；`coordinator` 角色统一用 `project-coordinator`）。 |
| `data` | object | 事件详情，自由结构 |

---

## 3. 产物归档路径映射

### 3.1 映射规则

其他 agent 将产物写入临时路径 `temp/{batch_id}/{filename}` 后，统筹 agent 根据产物类型将文件移动到项目目录下的标准路径。

以下映射规则定义了 **`type` + 元信息 → 目标路径** 的转换：

| 产物类型 `type` | 元信息 | 目标路径模板 |
|----------------|--------|------------|
| `raw_script` | — | `project/{name}/原始剧本.md` |
| `project_config` | — | `.meta/projects/{uuid}/project_config.json` |
| `script` | `episode` | `project/{name}/{episode}/剧本.md` |
| `character_design` | `character` | `project/{name}/全局依赖/角色设定/具体设定/{character}.md` |
| `character_ref` | `character` | `project/{name}/全局依赖/角色设定/角色参考图/{character}.png` |
| `scene_design` | `scene` | `project/{name}/全局依赖/场景设定/具体设定/{scene}.md` |
| `scene_ref` | `scene` | `project/{name}/全局依赖/场景设定/场景参考图/{scene}.png` |
| `prop_design` | `prop` | `project/{name}/全局依赖/道具设定/具体设定/{prop}.md` |
| `prop_ref` | `prop` | `project/{name}/全局依赖/道具设定/道具参考图/{prop}_{出现场合}_基准.png` |
| `storyboard` | `episode` + `filename` | `project/{name}/{episode}/分镜/{filename}` |
| `poster` | `episode` + `filename` | `project/{name}/{episode}/海报设计/{filename}` |
| `setting` | — | `project/{name}/全局依赖/全局设定.md`（单一文件，由 producer 在 supervisor_extraction 阶段输出，包含世界观、时间线、人物关系等所有全局设定；coordinator 创建项目时创建空文件占位） |
| `reference` | `subtype` + `filename` | `project/{name}/前期采样/{subtype}/{filename}` |
| `audio_reference` | `filename` | `project/{name}/全局依赖/音色参考/{filename}` |
| `video` | `episode` + `filename` | `project/{name}/{episode}/视频/{filename}` |
| `video_manifest` | `episode` | `project/{name}/{episode}/视频/_manifest.json` |
| `other` | 按 `path` 字段直接使用 | `project/{name}/{path}` |

### 3.2 变量说明

| 变量 | 来源 | 示例 |
|------|------|------|
| `{name}` | `project.json` 中的 `name` | `山与鱼` |
| `{episode}` | 其他 agent 通知时提供 | `01`、`02` |
| `{character}` | 其他 agent 通知时提供 | `小青`、`老鱼` |
| `{scene}` | 其他 agent 通知时提供 | `河底水潭`、`岸上木屋` |
| `{prop}` | 其他 agent 通知时提供 | `鱼篓`、`灯笼` |
| `{filename}` | 原始文件名 | `frame_001.png`、`角色设定.md` |
| `{subtype}` | 参考素材的子类型 | `人物`、`场景`、`风格`、`道具` |

### 3.3 操作边界

- 目标目录若不存在，由统筹 agent 自动创建
- 若目标文件已存在，统筹 agent 不做覆盖写入，而是通知其他 agent 确认是否替换
- 统筹 agent **绝不打开或解析**产物文件的内容，所有操作基于文件系统元数据（路径、大小、修改时间）

---

## 4. 日志管理 — `.logs/`

各技能生成的任务日志统一存放在 `project/{项目名}/.logs/` 下。

### 4.1 `_index.json` — 轻量索引表

```json
{
  "batches": [
    {
      "batch_id": "batch_20260516_120000",
      "type": "character_reference",
      "created_at": "2026-05-16T12:00:00+08:00",
      "total": 5,
      "succeeded": 4,
      "failed": 1,
      "log_file": "batch_20260516_120000.json"
    }
  ]
}
```

### 4.2 全量批次日志

文件路径：`batch_YYYYMMDD_HHmmss.json`

```json
{
  "batch_id": "batch_20260516_120000",
  "type": "character_reference",
  "created_at": "...",
  "completed_at": "...",
  "model": "gpt-image-2-vip",
  "total": 5,
  "succeeded": 4,
  "failed": 1,
  "results": [
    {
      "task_index": 0,
      "status": "succeeded",
      "output_path": "project/山与鱼/全局依赖/角色设定/角色参考图/character_a.png",
      "seed": 12345
    },
    {
      "task_index": 1,
      "status": "failed",
      "error": "violation",
      "prompt": "..."
    }
  ]
}
```

### 4.3 失败任务详情

文件路径：`failed_batch_YYYYMMDD_HHmmss.json`

仅记录失败任务，结构与批次日志相同但只含 `failed` 项。

---

## 5. 工作流概览

```
创建项目 → 前期筹备（角色/场景/道具设定）→ 制作（逐集剧本→分镜→海报）→ 后期 → 归档
```

统筹 agent 的职责：

1. **创建项目**：生成 UUID，初始化 `.meta/` 下所有文件，创建 `project/{name}/` 骨架目录
2. **状态管理**：维护 `stages.json` 的阶段流转
3. **产物追踪**：更新 `manifest.json`，确保每份关键产物被记录
4. **事件审计**：向 `events.jsonl` 追加每一次有意义的状态变更
5. **日志聚合**：监控 `.logs/`，在需要时提供任务状态概览
6. **全局一致性**：确保项目目录结构始终符合本规范

---

## 6. 项目注销

### 6.1 定义

项目注销是指**完全清除**项目在文件系统中的所有痕迹，包括：
- 项目实际目录 `project/{name}/`
- 统筹管理区元数据目录 `.meta/projects/{id}/`

### 6.2 不可逆声明

**项目注销操作不可逆**。一旦执行，项目的所有文件和记录将被永久删除，无法恢复。

### 6.3 推荐操作顺序

1. **先打包，后注销**：推荐先执行"打包项目"操作将项目归档为 ZIP，再执行注销，确保数据可追溯
2. **记录最终事件**：在删除文件前，必须先将 `project.deleted` 事件写入 `events.jsonl`
3. **删除元数据目录最后执行**：因为元数据目录中的 `events.jsonl` 需要先记录注销事件

### 6.4 操作边界

- 只操作当前工作空间内的文件，不涉及外部存储
- 不询问用户确认（调用者已确认）
- 删除前不备份（由调用者决定是否先打包）

---

## 7. 项目打包

### 7.1 定义

项目打包是指将项目的**实际文件目录**和**元数据目录**归档为一个 ZIP 文件，便于传输、备份或长期存储。

### 7.2 输出路径

打包产物保存到 `temp/` 目录，文件命名规则：

```
temp/{项目名}_{UUID前8位}_{YYYYMMDD}.zip
```

示例：`temp/海权复兴·大国归位_f038db17_20260516.zip`

### 7.3 ZIP 内部结构

```
{项目名}_{UUID前8位}_{YYYYMMDD}.zip
├── manifest.txt                          # 项目概要信息
├── project/{name}/                       # 项目实际目录
│   ├── 原始剧本.md
│   ├── 全局依赖/
│   │   ├── 角色设定/
│   │   ├── 场景设定/
│   │   └── ...
│   └── ...
└── .meta/projects/{id}/       # 项目元数据目录
    ├── project.json
    ├── stages.json
    ├── manifest.json
    └── events.jsonl
```

### 7.4 manifest.txt 格式

ZIP 根目录的 `manifest.txt` 包含项目概要信息，使用纯文本键值对格式：

```
项目名称: {name}
UUID: {id}
创建时间: {created_at}
最后更新: {updated_at}
当前阶段: {current_stage}
产物数量: {artifacts_count}
状态: active|archived|cancelled
打包时间: {YYYY-MM-DD HH:mm:ss}
```

### 7.5 操作边界

- **打包不删除原文件**：打包是复制归档，原项目文件和元数据保持不变
- 输出目录 `temp/` 若不存在则自动创建
- ZIP 使用标准 DEFLATE 压缩
- 路径中的中文字符使用 UTF-8 编码
