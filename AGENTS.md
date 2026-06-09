# 全局行为规则

所有 agent 使用中文推理。

## 文件操作规则
- 项目业务文件存放在 `project/` 目录下
- `temp/` 路径下的任何文件**禁止删除**
- `.opencode/` 配置目录只读，业务文件放 `project/`

## PowerShell 编码规范（Windows）
所有文件读写必须显式指定 `-Encoding UTF8`：
- 读取：`Get-Content -Encoding UTF8 -Raw "路径"`
- 写入：`Set-Content -Encoding UTF8 "路径" -Value "内容"`
- Python：`open("路径", "r", encoding="utf-8")` / `open("路径", "w", encoding="utf-8")`
- JSON：`ConvertTo-Json -Depth 10` / `json.dump(data, f, ensure_ascii=False, indent=2)`

## 主 Agent 执行规则
- 主 agent **禁止直接执行任何具体业务任务**，所有任务必须通过 `task` 工具 spawn 对应的子 agent 完成
- 主 agent 的职责：识别用户意图 → 匹配阶段/子 agent → spawn 任务 → 汇总结果
- 当用户请求涉及影视制作全流程时，按「项目生产管线」的阶段定义推进，通过 `.meta/projects/{uuid}/stages.json` 确定当前阶段（uuid 由 coordinator 创建项目时生成并返回）
- 任何涉及具体工作（文件操作、代码编写、数据生成等）都必须交由子 agent 执行

## 配置与技能修改规则
- 涉及创建、编辑、优化 skill、agent 定义、opencode 配置或任何 `.opencode/` 下的规则文件时，必须 spawn `skill-engineer` 子 agent 执行
- 主 agent 不得直接修改 `.opencode/` 下的 skill/agent/config 文件——这是 `skill-engineer` 的专属职责
- `skill-engineer` 按需加载 `skill-creator` 技能完成具体工作

## 音频规则
禁止输出背景音乐，仅允许对白和音效。

## 项目生产管线

影视项目分 4 个阶段依次推进，主 agent 通过 `.meta/projects/{uuid}/stages.json` 的 `current` 字段确定当前执行位置（uuid 由 coordinator 创建项目时生成并返回）。

### 阶段总览

| 阶段 | 名称 | 执行子 Agent | 产出 |
|------|------|-------------|------|
| 1 | 项目初始化 | `coordinator` | 项目骨架、project_config.json、原始剧本归档 |
| 2 | 监制提取设定 | `producer` | 角色/场景/道具设定、分集剧本 |
| 3 | 全局视觉资产生成 | `character-director` + `prop-maker` + `set-designer` + `art-director` | 角色/场景/道具参考图 |
| 4 | 剧集制作（每集循环） | `storyboard-director` + `character-director` + `prop-maker` + `set-designer` + `video-director` | 分镜脚本、剧集参考图、视频 |

### 阶段推进规则

1. 阶段开始前，检查 `.meta/projects/{uuid}/stages.json` 读取 `current` 阶段
2. 已完成阶段（`status=completed`）跳过，从 `current` 阶段继续
3. 不允许跳过 `pending` 阶段执行后续阶段
4. 每个子 agent 完成后，spawn `coordinator` 更新 `stages.json` 并归档产物

### 阶段 1：项目初始化

**触发条件**：用户要求创建新项目、开始新制作、处理新剧本

**执行流程**：
1. spawn `coordinator` → 创建项目目录结构（UUID 由 coordinator 生成），在 `.meta/projects/{uuid}/` 下生成 `project_config.json`（加载 skill: `project-coordinator`）
2. 主 agent 逐项询问项目基础配置：画幅（默认 16:9）、分辨率（默认 480p）、项目类型等
3. 将以下模型列表呈现给用户选择：

| modelKey | modelName | 说明 | VIP |
|----------|-----------|------|-----|
| `star-video2` | Seedance 2.0 VIP | 最强视频模型，15s音画同步 | ✅ |
| `star-video2-fast` | Seedance 2.0 Fast VIP | 最强视频模型快速版，15s音画同步 | ✅ |
| `happy-horse-1` | Happy Horse 1.0 | 阿里最新视频模型，支持多参生成 | |
| `kling-v3-omni` | **可灵 3.0 Omni** | 视频编辑模型，参考一致性，音画同出，多镜头 | ✅ |
| `kling-video-o3` | **可灵 3.0** | 视频生成模型，高质感，支持多镜头 | ✅ |
4. spawn `coordinator` → 更新 `project_config.json` 写入模型配置，注册 `manifest.json`，记录事件

**执行说明**：
- 如果用户尚未登录 libtv，模型查询会失败，此时回退到手动输入模型名
- `.meta/projects/{uuid}/project_config.json` 中模型字段为 `model`，值为用户选择的模型 modelKey

### 阶段 2：监制提取设定

**触发条件**：用户要求处理剧本、提取设定、生成分集剧本

**前置条件**：阶段 1 完成（`.meta/projects/{uuid}/project_config.json` 存在）

**执行流程**：
1. spawn `producer` → 多模态分析采样图（如有）→ 联网检索历史资料 → 提取角色/场景/道具设定 → 生成分集剧本（加载 skill: `producer`）
2. spawn `coordinator` → 归档设定文件到 `全局依赖/`

### 阶段 3：全局视觉资产生成

**触发条件**：设定文件就绪，需要生成参考图

**前置条件**：阶段 2 完成（设定文件存在）

**执行流程**（可并行）：
1. spawn `character-director` → 生成角色参考图任务表（加载 skill: `roles-ref-generator`）
2. spawn `prop-maker` → 生成道具参考图任务表（加载 skill: `prop-ref-generator`）
3. spawn `set-designer` → 生成场景参考图任务表（加载 skill: `scene-ref-generator`）
4. spawn `art-director` → 执行批量绘制（加载 skill: `art-director`）
5. spawn `coordinator` → 归档参考图到 `全局依赖/`

### 阶段 4：剧集制作

**触发条件**：需要制作具体剧集的分镜、参考图、视频

**前置条件**：阶段 3 完成（全局视觉资产就绪）

**每集执行流程**：
1. spawn `storyboard-director` → 生成分镜脚本（加载 skill: `storyboard-generator`）
2. spawn `character-director` → 生成剧集级角色参考图任务表（加载 skill: `roles-ref-generator`）
3. spawn `prop-maker` → 生成剧集级道具参考图任务表（加载 skill: `prop-ref-generator`）
4. spawn `set-designer` → 生成剧集级场景参考图任务表（加载 skill: `scene-ref-generator`）
5. [可选] spawn `art-director` → 生成分镜图（加载 skill: `art-director`）
6. spawn `video-director` → 基于分镜组生成视频（加载 skill: `video-director-libtv`）
7. spawn `coordinator` → 归档产物
8. 进入下一集

### 阶段路由

主 agent 收到用户请求时，按以下优先级匹配阶段：

| 用户意图关键词 | 匹配阶段 | 行为 |
|--------------|---------|------|
| 创建项目、新项目、开始制作、初始化 | 阶段 1 | 如已有 `.meta/projects/{uuid}/project_config.json` 则提示 |
| 处理剧本、提取设定、监制、分集剧本 | 阶段 2 | 检查阶段 1 是否完成 |
| 参考图、视觉资产、角色图、场景图、道具图、出图 | 阶段 3 | 检查阶段 2 是否完成 |
| 分镜、故事板、视频生成、剧集、制作视频 | 阶段 4 | 检查阶段 3 是否完成 |
| 继续、推进、下一步 | 自动 | 读取 `.meta/projects/{uuid}/stages.json` 从 `current` 继续 |

如用户意图不匹配任何阶段关键词，按原有单次意图匹配逻辑直接 spawn 对应子 agent。

### 子 Agent → Skill 映射

| 子 Agent | 对应 Skill 目录 |
|----------|---------------|
| `coordinator` | `.opencode/skills/project-coordinator` |
| `producer` | `.opencode/skills/producer` |
| `character-director` | `.opencode/skills/roles-ref-generator` |
| `prop-maker` | `.opencode/skills/prop-ref-generator` |
| `set-designer` | `.opencode/skills/scene-ref-generator` |
| `art-director` | `.opencode/skills/art-director` |
| `storyboard-director` | `.opencode/skills/storyboard-generator` |
| `video-director` | `.opencode/skills/video-director-libtv` |
| `writer` | `.opencode/skills/script-writer` |
| `skill-engineer` | `.opencode/skills/skill-creator` |
