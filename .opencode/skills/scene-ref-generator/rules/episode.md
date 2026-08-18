# 剧集级双视图参考流程

> 共享定义（Prompt 模板、参数表、校验规则）见 `rules/common.md`。
> 本模式**只产出任务表 JSON**，不直接生成图片——生图由 Art-director Agent 执行。

## 触发条件

- 阶段：剧集级参考图（episode_scene_ref）
- 输入：project_config.json + 全局场景参考图（双视图基准资产）+ 全局场景设定文件 + 本集分镜脚本
- 输出：`project/{项目名}/{剧集号}/场景参考图_任务表.json`

## 核心职责

Episode 模式负责将"全局双视图基准 + 本集场景变化"组装为任务表 JSON，供 Art-director 执行生图。Agent 的核心工作是：

1. 读取全局场景设定与 project_config.json，确定场景清单
2. 读取本集分镜脚本，提取每个场景在本集的变化描述
3. 仅对**有变化描述**的场景生成 task；无变化的场景不进入任务表（art-director 直接复用全局基准资产即可）
4. 对每个有变化的场景，生成 2 个 task（内景 + 外景），以全局基准资产为视觉一致性锚点，将本集变化叠加进 prompt
5. 输出任务表 JSON

> **重要约束**：Episode 模式不重新定义场景的恒定属性（空间布局、建筑风格、色调色温等）。这些由全局基准资产约束。Episode 模式只叠加本集变化层（如时间推移、天气变化、破坏痕迹、临时陈设等）。

## 步骤 1：收集输入文件

| 文件 | 用途 |
|------|------|
| `.meta/projects/{uuid}/project_config.json` | 项目参数（项目名、剧集号、视觉风格配置等） |
| `project/{项目名}/全局依赖/全局设定.md` | 画风参考、色调色温、视觉语言标准（提取 `{style_desc}` 和英文风格参数） |
| `project/{项目名}/全局依赖/场景设定/场景设定.md` | 场景索引清单 |
| `project/{项目名}/全局依赖/场景设定/具体设定/{场景名}.md` | 各场景的详细设定 |
| `project/{项目名}/全局依赖/场景设定/场景参考图/{场景名}_内景.png` | **全局内景基准资产**（Phase 2 产出） |
| `project/{项目名}/全局依赖/场景设定/场景参考图/{场景名}_外景.png` | **全局外景基准资产**（Phase 2 产出） |
| `project/{项目名}/{剧集号}/分镜/分镜脚本.json` | 提取本集场景变化描述 |
| `project/{项目名}/前期采样/风格/*.png` | 风格参考图（所有 task 共用） |

> **前置依赖**：episode 模式必须在 global_scene_art 阶段完成后执行，即全局双视图基准资产 `{场景名}_内景.png` 和 `{场景名}_外景.png` 必须已存在。若某场景的基准资产缺失，应报告给 orchestrator 并跳过该场景的 task 生成。

## 步骤 2：确定场景清单

1. 读取 `project_config.json`，获取项目名与当前剧集号
2. 读取 `场景设定/场景设定.md` 的场景清单表，列出所有场景名
3. 对每个场景，确认 `{场景名}_内景.png` 和 `{场景名}_外景.png` 均存在；任一缺失则跳过并报告

## 步骤 3：提取本集场景变化描述

读取 `project/{项目名}/{剧集号}/分镜/分镜脚本.json`，对每个场景在本集出现的内容进行扫描，提取变化描述。

### 提取规则

1. 逐场扫描分镜脚本的「通用设定」与「场景描述」字段
2. 查找场景在本集特有的状态变化（与全局设定对比）
3. 同一场景在本集多场出现时，合并所有变化描述（按场次顺序去重）
4. 若场景在本集出场但**无变化描述**，不进入任务表（直接复用全局基准资产）

### 变化类型识别

| 变化类型 | 是否生成 task | 示例 |
|---------|--------------|------|
| **时间/光照变化** | 生成 | 晴日→夜雨、白昼→黄昏、清晨→午夜 |
| **天气/季节变化** | 生成 | 晴→暴雨、夏→冬雪、晨雾→晴空 |
| **场景破坏/损毁** | 生成 | 战后残骸、火灾后废墟、墙体坍塌 |
| **临时陈设/装饰** | 生成 | 节庆装饰、宴会场、临时帐篷、祭坛 |
| **关键道具入景** | 生成 | 巨型战车占据广场、旗帜插满城墙 |
| **场景功能临时转换** | 生成 | 朝堂→宴会厅、卧房→临时病房 |
| **光影氛围变化** | 生成 | 烛光→月光、室内→火光摇曳 |
| **无变化** | 不生成 | 场景状态与全局基准一致 |

> **重要**：本集变化描述需具体、可视觉化，避免抽象描述（如"气氛紧张"）。Agent 应将抽象表述转化为可生图的视觉元素（如"光线昏暗，烛火摇曳，阴影拉长"）。

## 步骤 4：构建 Prompt

### 步骤 4a：模式判断

Episode 模式下，全局基准资产**始终存在**且**必须作为 images[0]**。每个有变化的场景生成 2 个 task（内景 + 外景）：

| 位置 | 内景 task | 外景 task |
|------|---------|---------|
| images[0] | **全局内景基准资产**（`{场景名}_内景.png`） | **全局外景基准资产**（`{场景名}_外景.png`） |
| images[1] | 风格参考图 | 风格参考图 |

> 若 `前期采样/场景/{场景名}*.png` 存在，可作为 images[2] 辅助参考（可选）。

### 步骤 4b：提取视觉风格

按 `rules/common.md` 的「视觉风格提取」规则，提取 `{style_desc}` 和英文风格参数。

### 步骤 4c：Prompt 模板

使用 `rules/common.md` 的**内景/外景 7 段双语模板**，在 SCENE CONTINUITY 段落中追加本集变化声明：

**内景模板（Episode 变化版）— 关键修改点：**

在 SCENE CONTINUITY 段落中追加：
```
Episode-specific changes for {剧集号}:
- {episode_changes_interior}
These changes are layered on top of the global base asset (Image 1).
Maintain all constant spatial attributes from the global base; only the episode-specific changes differ.
```

在 Atmosphere 段落中追加本集氛围变化（中文）。

**外景模板（Episode 变化版）— 关键修改点：**

在 SCENE CONTINUITY 段落中追加：
```
Episode-specific changes for {剧集号}:
- {episode_changes_exterior}
These changes are layered on top of the global base asset (Image 1).
Maintain all constant spatial attributes from the global base; only the episode-specific changes differ.
```

在 Atmosphere 段落中追加本集氛围变化（中文）。

### 步骤 4d：参数说明

| 参数 | 含义 | Episode 模式取值规则 |
|------|------|---------------------|
| 英文风格参数 | 视觉风格 | 按步骤 4b 提取，与全局模式一致 |
| `{scene_name_zh}` | 场景名 | 来自场景设定 |
| `{environment_description_zh}` | 环境描述 | 全局设定 + 本集变化 |
| `{period_description_zh}` | 时代描述 | 从全局设定提取 |
| Scene 段落 | 场景描述 | 全局空间描述 + 本集空间变化（如"夜雨笼罩的长江江面，波涛汹涌"） |
| Lighting 段落 | 光线描述 | 全局光线 + 本集光线变化（如"夜雨笼罩，偶有雷光"） |
| Atmosphere 段落 | 氛围描述 | 本集氛围（如"暴雨夜的肃杀与压抑"） |
| `{episode_changes_interior}` | 本集内景变化 | 从分镜脚本提取，聚焦室内变化 |
| `{episode_changes_exterior}` | 本集外景变化 | 从分镜脚本提取，聚焦室外变化 |

> **关键策略**：Scene / Lighting / Atmosphere 段落既包含全局恒定属性，又叠加本集变化。Agent 应将本集变化**融入**对应字段，而非简单罗列。

## 步骤 5：生成任务表 JSON

```json
{
  "model": "nano-banana-2",
  "episode": "{剧集号}",
  "tasks": [
    {
      "scene_name": "{场景名}",
      "view_type": "interior",
      "episode_specific_changes": "从分镜脚本提取的本集内景变化描述",
      "global_base_image": "project/{项目名}/全局依赖/场景设定/场景参考图/{场景名}_内景.png",
      "prompt": "SCENE REFERENCE FRAME — INTERIOR\n\nCreate a professional cinematic interior scene reference frame for {film_context}.\n\nThis is an interior scene reference image for {scene_name_zh}...\n\nSCENE CONTINUITY:\n\nThis is an interior reference for {scene_name_zh}...\n\nEpisode-specific changes for {剧集号}:\n- {episode_changes_interior}\nThese changes are layered on top of the global base asset (Image 1).\n...",
      "model": "nano-banana-2",
      "imageSize": "4K",
      "aspectRatio": "4:1",
      "filename": "{场景名}_内景_{剧集号}.png",
      "images": [
        "project/{项目名}/全局依赖/场景设定/场景参考图/{场景名}_内景.png",
        "project/{项目名}/前期采样/风格/{风格文件}.png"
      ]
    },
    {
      "scene_name": "{场景名}",
      "view_type": "exterior",
      "episode_specific_changes": "从分镜脚本提取的本集外景变化描述",
      "global_base_image": "project/{项目名}/全局依赖/场景设定/场景参考图/{场景名}_外景.png",
      "prompt": "SCENE REFERENCE FRAME — EXTERIOR\n\nCreate a professional cinematic exterior scene reference frame for {film_context}.\n\nThis is an exterior scene reference image for {scene_name_zh}...\n\nSCENE CONTINUITY:\n\nThis is an exterior reference for {scene_name_zh}...\n\nEpisode-specific changes for {剧集号}:\n- {episode_changes_exterior}\nThese changes are layered on top of the global base asset (Image 1).\n...",
      "model": "nano-banana-2",
      "imageSize": "4K",
      "aspectRatio": "4:1",
      "filename": "{场景名}_外景_{剧集号}.png",
      "images": [
        "project/{项目名}/全局依赖/场景设定/场景参考图/{场景名}_外景.png",
        "project/{项目名}/前期采样/风格/{风格文件}.png"
      ]
    }
  ],
  "output_path": "project/{项目名}/{剧集号}/场景参考图/"
}
```

### 任务表字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `scene_name` | string | 场景名（与全局场景设定一致） |
| `view_type` | string | `"interior"` 或 `"exterior"` |
| `episode_specific_changes` | string | 本集变化描述，从分镜脚本提取 |
| `global_base_image` | string | 全局基准资产路径（与 `images[0]` 一致） |
| `prompt` | string | 生图提示词，7 段双语结构 + episode 变化声明 |
| `model` | string | 固定 `nano-banana-2` |
| `imageSize` | string | 固定 `4K` |
| `aspectRatio` | string | 固定 `4:1` |
| `filename` | string | `{场景名}_内景_{剧集号}.png` 或 `{场景名}_外景_{剧集号}.png` |
| `images` | string[] | `images[0]` 为对应视图的全局基准资产 |

**自检清单：**
- [ ] 仅有变化描述的场景才生成 task，无变化的场景不进入任务表
- [ ] 每个有变化的场景生成 2 个 task（内景 + 外景）
- [ ] 内景 task 的 `images[0]` 为 `{场景名}_内景.png`，外景 task 的 `images[0]` 为 `{场景名}_外景.png`
- [ ] `filename` 格式为 `{场景名}_内景_{剧集号}.png` 或 `{场景名}_外景_{剧集号}.png`
- [ ] `output_path` 为 `project/{项目名}/{剧集号}/场景参考图/`
- [ ] 每个 prompt 包含 7 段结构 + Episode-specific changes 声明
- [ ] prompt 中 SCENE CONTINUITY 段落包含 `Episode-specific changes for {剧集号}` 声明
- [ ] prompt 禁止出现剧情角色描述
- [ ] `view_type` 字段为 `"interior"` 或 `"exterior"`
- [ ] `episode_specific_changes` 字段已填写本集变化摘要
- [ ] `images` 数组不包含角色参考图或道具参考图
- [ ] model 固定为 `nano-banana-2`，imageSize 固定为 `4K`，aspectRatio 固定为 `4:1`

## 步骤 6：Schema 校验

1. `validate_top_level(data)` 校验顶层字段
2. `validate_tasks(tasks, "episode")` 校验任务列表

> Episode 模式扩展字段（`scene_name`、`view_type`、`episode_specific_changes`、`global_base_image`）不参与 schema 严格校验，但 Agent 应确保字段非空且语义合理。

两个函数均返回空列表则通过。

## 步骤 7：输出完成提示

```
剧集 {剧集号} 双视图场景参考图任务表已生成，等待 Art-director 执行生图
- {N} 个场景有本集变化，已生成 {N*2} 个 task（内景 {N} + 外景 {N}）
- {M} 个场景无变化，将直接复用全局基准资产
```

## 参考图上传顺序

### 内景 task

| 位置 | 内容 |
|------|------|
| images[0] | **全局内景基准资产**（`{场景名}_内景.png`） |
| images[1] | 风格参考图（`前期采样/风格/*.png`） |
| images[2]（可选） | 场景采样图（`前期采样/场景/{场景名}*.png`，辅助参考） |

### 外景 task

| 位置 | 内容 |
|------|------|
| images[0] | **全局外景基准资产**（`{场景名}_外景.png`） |
| images[1] | 风格参考图（`前期采样/风格/*.png`） |
| images[2]（可选） | 场景采样图（`前期采样/场景/{场景名}*.png`，辅助参考） |

**绝对禁止**加入角色参考图或道具参考图。

## 差异对比

| 维度 | 全局模式（Phase 2） | Episode 模式（Phase 3，本文件） |
|------|--------------------|------------------------------|
| 触发阶段 | 全局视觉资产生成 | 剧集级参考图（episode_scene_ref） |
| 核心输入 | 场景设定 + 风格采样 + 前期采样 | 双视图基准资产 + 本集分镜脚本中场景变化描述 |
| 任务数量 | 每场景 2 个 task（内景 + 外景） | 仅有变化描述的场景生成 task，每场景 2 个（内景 + 外景） |
| images[0] | 场景采样图（模式 A）或风格参考图（模式 B） | **全局双视图基准资产**（内景 task 用内景基准，外景 task 用外景基准） |
| prompt 结构 | 7 段双语模板 | 7 段双语模板 + Episode-specific changes 声明 |
| 扩展字段 | 无 | `scene_name`、`view_type`、`episode_specific_changes`、`global_base_image` |
| 输出路径 | `全局依赖/场景设定/场景参考图/` | `{剧集号}/场景参考图/` |
| 输出文件名 | `{场景名}_内景.png` / `{场景名}_外景.png` | `{场景名}_内景_{剧集号}.png` / `{场景名}_外景_{剧集号}.png` |
| 是否直接生图 | 否（由 art-director 执行） | 否（由 art-director 执行） |
