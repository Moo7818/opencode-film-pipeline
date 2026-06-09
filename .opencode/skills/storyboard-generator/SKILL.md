---
name: storyborad-generator
description: 将分集剧本拆解为电影级分镜头脚本（结构化JSON），输出独立组JSON格式的分镜任务表。[可选]按需生成分镜图生图任务表，配套Seedance 2.0 Fast模型实现分镜→视频桥接。分镜导演Agent依据此技能执行分镜制作。当任务涉及生成分镜脚本、镜头分解、分镜图任务表时加载此技能。注意：这是底层执行技能，由分镜导演 Agent 按需加载，不直接响应路由。
---

# 分镜脚本生成

将分集剧本拆解为**场→组→镜**三级结构化 JSON，输出为独立组 JSON 格式的分镜任务表。
[可选] 通过 `--with-task-table` 参数附加生成分镜图生图任务表，配套 Seedance 2.0 Fast 模型实现分镜→视频桥接。

**核心约束（违反即违规）：**
- **Agent 禁止自行构造 JSON 内容。** 所有分镜 JSON 必须经由 `run_pipeline.py --build` 调用 LLM 产出，不得在 Agent 对话中直接生成 JSON 写入文件。
- **无需单独调用 call_llm.py、validators.py、expand_scenes_to_groups.py** — `run_pipeline.py --build` 一条命令自动串联全部步骤。
- **所有中间文件在 `.pipeline/` 目录下，脚本全权管理**，Agent 不得读取或修改其中的文件。

---

## Agent 职责（仅需做 3 件事）

```
┌───────────────────────────────────────────────────────┐
│  Agent 职责（仅此 3 步，不多不少）                      │
│                                                       │
│  1. 读剧本 + 读设定文件 + 读 project_config.json        │
│     （检查 use_storyboard_images 标志）                 │
│  2. 构建 System Prompt（含场级连贯性规则 + 硬约束）      │
│  3. 运行 run_pipeline.py --build                       │
│     （如 use_storyboard_images=true，追加               │
│      --with-task-table 及 Seedance 参数）              │
│                                                       │
│  剩余一切（LLM请求/校验/分组/任务表）由 run_pipeline.py  │
│  自动完成                                              │
└───────────────────────────────────────────────────────┘
```

---

## 流程概览

```
Agent 读剧本 + 读设定
    │
    ▼
Agent 构建 System Prompt（含场级连贯性规则 + 硬约束）
    │
    ▼
Agent 判断剧本长度 → 选择 run_pipeline.py --build 模式
    │
    ├── 短剧本（≤2000字）→ 单次请求
    │   python run_pipeline.py --build ^
    │     --system "(System Prompt)" ^
    │     --user "(User Message)" ^
    │     --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" ^
    │     --output-dir "project/{项目名}/{剧集号}/分镜"
    │
    └── 长剧本（>2000字）→ 自动分片并发
        python run_pipeline.py --build ^
          --system "(System Prompt)" ^
          --user "(User Message)" ^
          --shard --script-path "project/{项目名}/{剧集号}/剧本.md" ^
          --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" ^
          --output-dir "project/{项目名}/{剧集号}/分镜"
    │
    ▼
run_pipeline.py 自动执行：
  ① 初始化管线目录 .pipeline/
  ② call_llm.py 构建请求 → 调用 LLM
     （长剧本：shard_manager.py 分片 → 并发调用 → 合并）
  ③ validators.py 校验修复 → 输出 04_validated.json
  ④ expand_scenes_to_groups.py 展开独立组
     → .pipeline/05_groups/组{N}.json
  ⑤ [可选] 生成分镜图任务表（仅 --with-task-table 时执行）
     → generate_task_table.py → 分镜/分镜图_任务表.json
  ⑥ 复制到最终目录: 分镜/分组/组{N}.json
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

## 第三步：构建 System Prompt

System Prompt 必须包含以下内容：

### 1. 输出格式要求

输出为**场→组→镜**三级 JSON 数组格式：

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

### 2. 场级连贯性约束规则（必须强调）

**规则 1：调度设计连贯** — 同一场内的相邻组之间，人物调度和空间走位应形成连续的空间叙事线。关键定位物位置一致，人物相对位置不突变，走动方向在组间保持一致。

**规则 2：不越轴（180° 规则）** — 同一场内所有组的摄影机轴线方向保持一致。如需越轴，中间必须插入中性镜头作为缓冲。

**规则 3：剧情与蒙太奇连贯** — 同一场内的组间叙事推进自然流畅，情绪落点引导下一组的情绪起点，形成"起→承→转→合"的完整叙事曲线。

### 3. 硬约束

1. **台词时长**：每个含台词镜头，时长 ≥ 汉字数 ÷ 4 + 0.5 秒
2. **组时长**：每组镜头时长之和 ≤ 15 秒
3. **组镜头数**：每组 ≤ 9 个镜头
4. **长镜头独占**：≥10 秒的镜头独占一组
5. **快切独立成组**：快切镜头组单独成组
6. **台词保真**：与原始剧本逐字一致
7. **字段完整**：每个镜头必须包含全部 17 个字段（镜号、开始/结束时间、时长、场景描述、站位/调度、人物心理活动、表演/微表情、景别、摄影机角度、摄影机运动、焦距景深、光线、氛围、台词、音效、剪辑转场、后期特效）
8. **时间连续**：同组内首镜从 0 开始
9. **字数下限**：光线/氛围 ≥ 60 字，表演/微表情 ≥ 60 字，站位/调度/人物心理活动 ≥ 80 字
10. **纯中文输出**（除 f/2.8 等技术表达外）
11. **通用设定在场级统一定义**：风格、场景名称、全局光线基调、全局色彩调性、全局氛围基调在每场只定义一次
12. **场级连贯性**：同一场内遵守调度连贯、不越轴、剧情蒙太奇连贯三条规则
13. **音频规则**：仅允许对白和音效，禁止输出背景音乐

---

## 第四步：执行管线（唯一入口）

### 方式 A：配置文件模式（推荐，避免 PowerShell 引号问题）

把参数写入 JSON 配置文件，直接引用：

**`pipeline_config.json`** 示例：
```json
{
  "pipeline_dir": "project/{项目名}/{剧集号}/.pipeline",
  "output_dir": "project/{项目名}/{剧集号}/分镜",
  "output_groups": "分组",
  "system_file": "project/{项目名}/{剧集号}/temp/system_prompt.txt",
  "user_file": "project/{项目名}/{剧集号}/temp/user_message.txt",
  "shard": false,
  "script_path": null
}
```

```powershell
python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --build --config pipeline_config.json
```

**优点**：Separate Prompt 文件存入 `temp/`，配置 JSON 管理路径，一行命令执行。

### 方式 B：文件传参模式（次推荐）

Prompt 写入文件，命令行只传路径：

```powershell
$SKILL = ".opencode/skills/storyboard-generator/scripts"

# 短剧本
python "$SKILL/run_pipeline.py" --build `
  --system-file "project/{项目名}/{剧集号}/temp/system_prompt.txt" `
  --user-file "project/{项目名}/{剧集号}/temp/user_message.txt" `
  --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
  --output-dir "project/{项目名}/{剧集号}/分镜"

# 长剧本
python "$SKILL/run_pipeline.py" --build `
  --system-file "project/{项目名}/{剧集号}/temp/system_prompt.txt" `
  --user-file "project/{项目名}/{剧集号}/temp/user_message.txt" `
  --shard --script-path "project/{项目名}/{剧集号}/分集剧本.json" `
  --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
  --output-dir "project/{项目名}/{剧集号}/分镜"
```

### 方式 C：直接传参（仅简短提示词可用）

```powershell
$SKILL = ".opencode/skills/storyboard-generator/scripts"

# 短剧本
python "$SKILL/run_pipeline.py" --build `
  --system "(System Prompt 全文)" `
  --user "(User Message 全文，包含剧本内容)" `
  --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
  --output-dir "project/{项目名}/{剧集号}/分镜"

# 长剧本
python "$SKILL/run_pipeline.py" --build `
  --system "(System Prompt 全文)" `
  --user "(User Message 全文，包含剧本内容)" `
  --shard --script-path "project/{项目名}/{剧集号}/分集剧本.json" `
  --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
  --output-dir "project/{项目名}/{剧集号}/分镜"
```

> ⚠ **方式 C 的 PowerShell 限制**：System Prompt 和 User Message 若含双引号、反引号、$ 变量符等特殊字符，PowerShell 会错误解析。**长提示词请使用方式 A 或 B。**

---

## 第五步：验证产出

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
1. 检查 LLM 调用是否超时 → 重试 `--build`
2. 检查 `04_validated.json` 是否存在 → 修整 System Prompt 后重试
3. 最多重试 1 次，仍失败则报告问题

---

## 脚本功能速查

| 模式 | 命令 | 自动完成的步骤 |
|------|------|--------------|
| `--build --config`（推荐） | `python run_pipeline.py --build --config config.json` | 从配置文件读取所有参数 → 同上 |
| `--build`（短剧本） | `python run_pipeline.py --build --system "..." --user "..."` | 构建请求 → 调用LLM → 校验 → 展开 → 输出 |
| `--build`（短剧本，文件传参） | `python run_pipeline.py --build --system-file sys.txt --user-file user.txt` | 从文件读取 Prompt → 同上 |
| `--build`（长剧本） | `python run_pipeline.py --build --system "..." --user "..." --shard --script-path 剧本.md` | 分片 → 并发调用 → 合并 → 校验 → 展开 → 输出 |
| `--build --with-task-table` | `python run_pipeline.py --build ... --with-task-table --task-table-model ...` | 同上 + 生成分镜图_任务表.json |
| `--setup` | `python run_pipeline.py --setup` | 仅初始化管线目录 |
| `--process` | `python run_pipeline.py --process` | 仅校验 → 展开 → 输出（LLM 响应已就位时） |
| `--process --with-task-table` | `python run_pipeline.py --process --with-task-table` | 校验 → 展开 → 生成任务表 → 输出 |

---

## 常见问题

### Q：为什么会漏掉分组步骤？

上一轮创建第三集时，Agent **没有使用 `run_pipeline.py`**，而是在对话中直接让 LLM 生成了完整的 `分镜脚本.json`。由于跳过了 `call_llm.py` 的标准 Prompt 模板和 `expand_scenes_to_groups.py` 的机械展开，导致：
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
    --system "..." --user "..." `
    --with-task-table `
    --task-table-model gpt-image-2 `
    --task-table-resolution 1K `
    --task-table-aspect-ratio $config.aspect_ratio `
    --pipeline-dir "project/{项目名}/{剧集号}/.pipeline" `
    --output-dir "project/{项目名}/{剧集号}/分镜"
} else {
  python ".opencode/skills/storyboard-generator/scripts/run_pipeline.py" --build `
    --system "..." --user "..." `
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
python ".opencode/skills/storyboard-generator/scripts/generate_task_table.py" ^
  --groups-dir ".pipeline/05_groups/" ^
  --output-dir "project/{项目名}/{剧集号}/分镜" ^
  --model gpt-image-2 ^
  --image-size 1K ^
  --aspect-ratio 16:9 ^
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
  "shard": false,
  "with_task_table": true,
  "task_table_model": "gpt-image-2",
  "task_table_resolution": "1K",
  "task_table_aspect_ratio": "16:9",
  "image_refs": ["校长角色", "婚宴场景", "奢华风格"]
}
```

> **注意**：`--image-refs` 是可选的。未指定时不生成参考标注行，Art-director 仅基于分镜组 JSON 文字描述绘图。