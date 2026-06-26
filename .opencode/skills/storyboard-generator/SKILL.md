---
name: storyboard-generator
description: 将分集剧本拆解为电影级分镜头脚本（结构化JSON），输出独立组JSON格式的分镜任务表。[可选]按需生成分镜图生图任务表，配套AIGC视频模型实现分镜→视频桥接。分镜导演Agent依据此技能执行分镜制作。当任务涉及生成分镜脚本、镜头分解、分镜图任务表时加载此技能。注意：这是底层执行技能，由分镜导演 Agent 按需加载，不直接响应路由。
---

# 分镜脚本生成

将分集剧本拆解为**场→组→镜**三级结构化 JSON，输出为独立组 JSON 格式的分镜任务表。
[可选] 通过 `--with-task-table` 参数附加生成分镜图生图任务表，配套 AIGC视频模型实现分镜→视频桥接。

**核心约束（违反即违规）：**
- **Agent 自行构造 JSON 内容。** Agent 必须用自身 LLM 生成符合格式规范的分镜 JSON，写入 `.pipeline/01_response.json`。
- **无需单独调用 validators.py、expand_scenes_to_groups.py** — `run_pipeline.py --build` 一条命令自动串联全部步骤。
- **所有中间文件在 `.pipeline/` 目录下，脚本全权管理**，Agent 不得读取或修改其中的文件（`01_response.json` 除外，此文件由 Agent 写入）。

---

## Agent 职责

```
┌──────────────────────────────────────────────────────┐
│  Agent 职责（仅此 3 步，不多不少）                    │
│                                                      │
│  1. 读剧本 + 读设定文件 + 读 project_config.json      │
│     （检查 use_storyboard_images 标志）               │
│  2. 用自身 LLM 生成分镜 JSON → 写入 01_response.json  │
│  3. 运行 run_pipeline.py --build                      │
│                                                      │
│  剩余一切（校验/分组/任务表）由 run_pipeline.py 自动完成 │
└──────────────────────────────────────────────────────┘
```

---

## 流程概览

```
Agent 读剧本 + 读设定
    │
    ▼
Agent 用自身 LLM 生成分镜 JSON
    │
    ▼
Agent 写入 .pipeline/01_response.json
    │
    ▼
run_pipeline.py --build 自动执行：
  ① 初始化管线目录 .pipeline/
  ② validators.py 校验修复 → 输出 04_validated.json
  ③ expand_scenes_to_groups.py 展开独立组
     → .pipeline/05_groups/组{N}.json
  ④ [可选] 生成分镜图任务表（仅 --with-task-table 时执行）
     → generate_task_table.py → 分镜/分镜图_任务表.json
  ⑤ 复制到最终目录: 分镜/分组/组{N}.json
    │
    ▼
Agent 验证产出
```

---

## 第一步：读取剧本

```bash
Get-Content -Encoding UTF8 "project/{项目名}/{剧集号}/分集剧本.json"
```

通读全文，理解故事内容、角色、场景、关键道具。

---

## 第二步：按需读取设定文件

```
project/{项目名}/全局依赖/
├── 全局设定/
├── 角色设定/
├── 场景设定/
└── 道具设定/
```

只读取与当前剧集相关的设定。

---

## 第三步：输出格式要求

Agent 生成的 JSON 必须为**场→组→镜**三级结构：

```json
[
  {
    "场号": 1,
    "场名称": "...",
    "场叙事概述": "...",
    "场转场": "切",
    "场总时长": "18",
    "通用设定": {
      "风格": "...",
      "场景名称": "...",
      "全局光线基调": "...",
      "全局色彩调性": "...",
      "全局氛围基调": "..."
    },
    "组列表": [
      {
        "组号": 1,
        "组时长": "6",
        "组叙事概述": "...",
        "组转场": "切",
        "镜头列表": [
          {
            "镜号": 1,
            "开始/结束时间": "0-3",
            "时长": "3",
            "场景描述": "...",
            "站位/调度": "...",
            "人物心理活动": "...",
            "表演/微表情": "...",
            "景别": "...",
            "摄影机角度": "...",
            "摄影机运动": "...",
            "焦距景深": "...",
            "光线": "...",
            "氛围": "...",
            "台词": "...",
            "音效": "...",
            "剪辑转场": "...",
            "后期特效": "..."
          }
        ]
      }
    ]
  }
]
```

### 场级连贯性规则

**规则 1：调度设计连贯** — 同一场内相邻组之间人物调度和空间走位形成连续空间叙事线。关键定位物位置一致，人物相对位置不突变，走动方向组间保持一致。

**规则 2：不越轴（180° 规则）** — 同一场内所有组摄影机轴线方向保持一致。如需越轴，中间必须插入中性镜头缓冲。

**规则 3：剧情与蒙太奇连贯** — 组间叙事推进自然流畅，情绪落点引导下一组的情绪起点。

### 硬约束

1. **台词时长**：每个含台词镜头，时长 ≥ 汉字数 ÷ 4 + 0.5 秒
2. **组时长**：每组镜头时长之和 ≤ 15 秒
3. **组镜头数**：每组 ≤ 9 个镜头
4. **长镜头独占**：≥10 秒的镜头独占一组
5. **快切独立成组**：快切镜头组单独成组
6. **台词格式**：`台词` 字段必须以`角色名：`开头，与原始剧本逐字一致
7. **字段完整**：每个镜头必须包含全部 17 个字段
8. **时间连续**：同组内首镜从 0 开始
9. **字数范围**：光线/氛围 60~120 字，表演/微表情 60~120 字，站位/调度 80~160 字，人物心理活动 80~160 字，场景描述 60~100 字
10. **纯中文输出**（除 f/2.8 等技术表达外）
11. **通用设定在场级统一定义**
12. **场级连贯性**：遵守调度连贯、不越轴、剧情蒙太奇连贯三条规则
13. **音频规则**：仅允许对白和音效，禁止背景音乐
14. **禁止冗余描述**：去掉"仿佛""让观众感受到""传递出""营造出"等引导性修辞，描述像导演给摄影师的指令一样精炼

---

## 第四步：Agent 生成分镜 JSON 并写入

### 操作步骤

**Step 1：初始化管线目录**
```powershell
python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --setup `
  --pipeline-dir "project/{项目名}/{剧集号}/.pipeline"
```

**Step 2：用自身 LLM 生成分镜 JSON**
严格按照上文的 JSON 格式、场级连贯性规则和硬约束生成。

**Step 3：写入 `01_response.json`**
将生成的 JSON 字符串包装为以下格式写入 `.pipeline/01_response.json`：

```json
{
  "content": "[{\"场号\": 1, \"场名称\": \"...\", ...}]"
}
```

> ⚠ **重要**：`01_response.json` 的 `content` 字段值必须是 **JSON 字符串**（即用 `json.dumps()` 序列化后的分镜数组），而非直接嵌入 JSON 对象。`validators.py` 期望 `content` 为字符串类型。

### 01_response.json 格式说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | string | 分镜 JSON 数组的**字符串序列化**形式（JSON 字符串） |

管线中 `validators.py` 读取 `content` 字段，将字符串反序列化为 JSON 数组后进行校验修复。

## 第五步：执行管线

### 方式 A：命令行模式

```powershell
python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --build `
  --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
  --output-dir "project/{项目名}/{剧集号}/分镜"
```

### 方式 B：配置文件模式

**`pipeline_config.json`** 示例：
```json
{
  "pipeline_dir": "project/{项目名}/{剧集号}/.pipeline",
  "output_dir": "project/{项目名}/{剧集号}/分镜"
}
```
```powershell
python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --build --config pipeline_config.json
```

---

## 第六步：验证产出

管线完成后，确认以下文件存在：

```
{剧集号}/
└── 分镜/
    ├── 分镜脚本.json              ← 场级完整 JSON（由管线从 .pipeline/ 拷贝）
    ├── 分镜图_任务表.json          ← [可选] 生图任务表（仅 --with-task-table 时生成）
    └── 分组/                     ← 独立组 JSON（每个文件自包含，含场级通用设定）
        ├── 组1.json
        ├── 组2.json
        └── ...
```

检查每个组 JSON 都包含 `通用设定` 字段（来自场级注入），确认镜号连续。

**如管线失败**：
1. 检查 `01_response.json` 格式是否正确（`content` 字段必须为 JSON 字符串）
2. 检查 `04_validated.json` 是否存在 → 修整 System Prompt 后重试
3. 最多重试 1 次，仍失败则报告问题

---

## 脚本功能速查

| 模式 | 命令 | 自动完成的步骤 |
|------|------|--------------|
| `--build --config`（推荐） | `python run_pipeline.py --build --config config.json` | 从配置文件读取参数 → 校验 → 展开 → 输出 |
| `--build` | `python run_pipeline.py --build` | 初始化 → 校验 → 展开 → 输出（Agent 需先写入 01_response.json） |
| `--build --with-task-table` | `python run_pipeline.py --build --with-task-table ...` | 同上 + 生成分镜图_任务表.json |
| `--setup` | `python run_pipeline.py --setup` | 仅初始化管线目录 |
| `--process` | `python run_pipeline.py --process` | 仅校验 → 展开 → 输出（01_response.json 已就位时） |
| `--process --with-task-table` | `python run_pipeline.py --process --with-task-table` | 校验 → 展开 → 生成任务表 → 输出 |

---

## 常见问题

### Q：为什么会漏掉分组步骤？

上一轮创建第三集时，Agent **没有使用 `run_pipeline.py`**，而是在对话中直接让自身 LLM 生成了完整的 `分镜脚本.json`。由于跳过了标准 Prompt 模板和 `expand_scenes_to_groups.py` 的机械展开，导致：
- `.pipeline/` 目录不存在
- `分镜/分组/组{N}.json` 不存在
- 各组中没有注入场级 `通用设定`

**解决办法**：使用 `run_pipeline.py --build` 一站式完成，Agent 不再手动分步操作。

### Q：已有 `分镜脚本.json` 怎么补分组？

```powershell
python "$SKILL/expand_scenes_to_groups.py" `
  --input "project/{项目名}/{剧集号}/分镜/分镜脚本.json" `
  --output-dir "project/{项目名}/{剧集号}/分镜/分组/"
```

### Q：如何启用分镜图生成分支流程？

分镜图分支流程由项目配置 `project_config.json` 中的 `use_storyboard_images` 字段控制。

**启用步骤：**
1. 检查 `.meta/projects/{uuid}/project_config.json` 中 `use_storyboard_images` 是否为 `true`
2. 如为 `true`，在 `run_pipeline.py` 命令中追加 `--with-task-table` 参数
3. 从 `project_config.json` 读取画幅比例、分辨率、模型选择参数传给 `--task-table-*`

```powershell
# 读取 project_config.json
$config = Get-Content -Encoding UTF8 -Raw ".meta/projects/{uuid}/project_config.json" | ConvertFrom-Json

# 如启用分镜图模式，追加 --with-task-table 参数
if ($config.use_storyboard_images) {
  python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --build `
    --with-task-table `
    --task-table-model gpt-image-2 `
    --task-table-resolution 1K `
    --task-table-aspect-ratio $config.aspect_ratio `
    --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
    --output-dir "project/{项目名}/{剧集号}/分镜"
} else {
  python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --build `
    --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
    --output-dir "project/{项目名}/{剧集号}/分镜"
}
```

**配套关系：**
- 分镜图模式默认配套 **gpt-image-2 模型**，输出静态分镜网格图
- `--task-table-model` 可选 `gpt-image-2`（默认）、`nano-banana-2`、`gpt-image-2-vip`
- `--task-table-resolution` 可选 `1K`（默认）、`2K`（需 vip）、`4K`（需 vip）
- `--task-table-aspect-ratio` 从 `project_config.json` 的 `aspect_ratio` 读取，默认 `16:9`
- 分镜图任务表产出后，由 Art-director 执行绘制，产出 PNG 作为 Video-director 的多模态参考素材
- Video-director 读取分镜图 OSS URL 作为多模态参考输入，提升视频生成的角色/场景一致性

### Q：分镜图绘制如何引用角色/道具/场景参考图？

分镜图生成位于剧集级角色/道具/场景参考图绘制**之后**，因此 Art-director 绘制分镜图时可以使用已就位的参考图作为输入。

**分镜图任务表 Prompt 注入参考图标注：**

```powershell
# 分镜图任务表生成时，通过 --image-refs 注入参考图标注
# 标注会自动拼入每个组的 prompt 头部，告知 Art-director 使用哪些参考图
python ".opencode/skills/storyboard-generator/scripts/generate_task_table.py" `
  --groups-dir ".pipeline/05_groups/" `
  --output-dir "project/{项目名}/{剧集号}/分镜" `
  --model gpt-image-2 `
  --image-size 1K `
  --aspect-ratio 16:9 `
  --image-refs 校长角色 婚宴场景 奢华风格
```

`--image-refs` 参数值（如 `校长角色 婚宴场景`）会拼入 prompt 头部：
```
【第1组】校长角色参考图片1，婚宴场景参考图片2。本组叙事摘要...
```

**run_pipeline.py 配置文件中也可声明：**
```json
{
  "pipeline_dir": "project/X/EP01/.pipeline",
  "output_dir": "project/X/EP01/分镜",
  "with_task_table": true,
  "task_table_model": "gpt-image-2",
  "task_table_resolution": "1K",
  "task_table_aspect_ratio": "16:9",
  "image_refs": ["校长角色", "婚宴场景", "奢华风格"]
}
```

> **注意**：`--image-refs` 是可选的。未指定时不生成参考标注行，Art-director 仅基于分镜组 JSON 文字描述绘图。
