---
name: storyboard-generator
description: 将分集剧本拆解为场→组→镜分镜脚本（detailed JSON / simplified Markdown），并按模式生成视觉锚点图或串行分镜图任务表。涉及分镜脚本、镜头分解、分镜图/视觉锚点任务表时使用；分镜导演 Agent 按需加载。
---

# 分镜脚本生成

将分集剧本拆解为**场→组→镜**三级分镜脚本，输出独立组文件供下游消费。

**核心原则：**
- Agent 用自身 LLM **理解剧本、创作分镜**，直接写文件；脚本仅做**机械拆分**（场→组展开），不依赖 Python 管线做内容校验
- **场 = 连续物理空间**（与 producer 场景设定一致）；戏剧节拍/时间流逝节点用**组**表达，禁止按节拍拆场
- 本产出主要供 **AI 视频生成消费**：描写精炼直接，心理活动简要提示，表演抓核心动作
- 详细规则按需加载：Phase A 细则见 `references/storytelling/workflow.md`，Phase B 见 `references/phase-b-*.md`，阶段二见 `references/phase-2-*.md`

---

## Agent 执行隔离

**阶段一（分镜脚本）与阶段二（参考图任务表）必须由不同的子 Agent session 执行。**

| 维度 | 阶段一：分镜脚本 | 阶段二：参考图任务表 |
|------|-----------------|-------------------|
| 执行者 | storyboard-director（session 1） | storyboard-director（session 2，fresh context） |
| 输入 | 剧本.md + 全局设定 + 分镜稿_临时.md | 组{N}.json/md（含场号）+ `meta_query(scope=config)` + 参考图目录 |
| 产出 | 分镜脚本.json/md + 分组/组{N}.json/md | 视觉锚点_任务表.json 或 分镜图_任务表.json |
| 上下文 | 含多轮创作思考 | **干净上下文**，仅读取结构化组文件和参考图清单 |

**隔离理由**：阶段一的创作思考会占据上下文窗口；同一 session 继续执行阶段二易偏离 prompt 模板的严格格式要求（映射块遗漏、参考图排序错误、Feeling 缺失等）。orchestrator 在阶段一完成后 spawn 新 session 执行阶段二，从磁盘读取产出文件，不继承对话上下文。

---

## 工作流程

```
┌─ 阶段一：episode_storyboard_script ─────────────────────┐
│  ⚡ Agent Session 1（storyboard-director）               │
│                                                         │
│  Step 0：轻量总体规划（快速落盘）                        │
│    读剧本 + 全部设定 → 物理分场 + 剧本行区间表           │
│    → 立即写入 分镜稿_临时.md（场级结构）                 │
│                                                         │
│  Step 1~N：逐场 分析→生成→写入（每场独立循环）           │
│    对每一场：                                            │
│      a. 按行区间重读该场剧本 → 分析 shot flow/分组/      │
│         台词时长（A4~A6 细则见 workflow.md）             │
│      b. 生成该场 JSON / MD（仅本场镜头）                 │
│      c. 详细模式：Write 场{N}.json 到 场文件/            │
│         （每场独立完整 JSON，不用 Edit 追加大文件）       │
│      d. 该场分析笔记追加写入 分镜稿_临时.md，            │
│         并同步更新场次戏剧地图行（组数/镜数/时长）       │
│                                                         │
│  全部场完成后：                                          │
│    ├─ 详细模式 → expand_scenes_to_groups.py              │
│    │   一条命令：合并场文件+校验+时间归零+拆分组文件     │
│    └─ 精简模式 → 逐个 Write 组{N}.md                    │
└─────────────────────────────────────────────────────────┘
          ↓（文件交接：组{N}.json/md 就绪）
┌─ 阶段二：参考图生成（按 reference_image_mode 分支）──────┐
│  ⚡ Agent Session 2（storyboard-director，fresh context） │
│    ├─ visual_anchor（默认）→ 视觉锚点图                  │
│    ├─ storyboard_images  → 串行分镜图                    │
│    └─ none → 跳过                                        │
└─────────────────────────────────────────────────────────┘
```

> **数据流原则（按行区间读取，控制 token）**：Step 0 通读剧本时，在分镜稿_临时.md 的场级结构中为每场记录**剧本行区间**（如 `场1：剧本.md L12-L58`）。Step 1~N 逐场分析时用 `Read(offset, limit)` **只读该场对应的行区间**获取逐字台词，不整本重读剧本；同时消费分镜稿_临时.md（场级结构 + 已写入场的分析笔记），**严禁只读其一**。剧本很短（单集 15-30 秒）时可直接整本读。
>
> **阶段间数据交接**：阶段二仅从磁盘读取组{N}.json/md 与参考图目录；配置经 `meta_query(scope=config)` 读取。画面比例固定 `16:9`，无需从配置读取。

---

## 模式选择

通过 `meta_query(scope=config)` 返回的 `config.storyboard_mode` 选择（Step 0 两种模式下完全一致，差异仅在 Step 1~N 输出格式；`"simplified"` 进精简模式，否则详细模式）：

| 模式 | 值 | 分镜脚本输出 | 组文件格式 | 详细文档 |
|------|-----|-------------|-----------|---------|
| 详细模式（默认） | `"detailed"` 或未设置 | 结构化 JSON（17字段×N镜头） | `组{N}.json` | `references/phase-b-detailed.md` |
| 精简模式 | `"simplified"` | 纯 Markdown（讲戏式叙事） | `组{N}.md` | `references/phase-b-simplified.md` |

---

## Step 0：轻量总体规划

读取以下内容，产出戏剧结构笔记：

- **分集剧本**：`project/{项目名}/{剧集号}/剧本.md` — 画面内容（AI动效描述 + 产品展示清单）、口播文案、时长（单集15-30秒）
- **全局设定**：`project/{项目名}/全局依赖/全局设定.md`；**角色/场景/道具设定**：`project/{项目名}/全局依赖/{角色,场景,道具}设定/`

执行 A2（时空故事节点 + 物理分场），产出**场列表 + 场名称 + 每场剧本行区间**，立即写入 `{剧集号}/分镜/分镜稿_临时.md`（仅场级结构）。分场规则、节点类型表、一场多组示例见 `references/storytelling/workflow.md` A2。

> Step 0 负责设定采集，Step 1~N 无需重复读取设定；逐场生成时按行区间重读剧本确保台词逐字一致。shot flow / 缩略图 / 台词时长（A4~A6）下沉到逐场阶段，细则见 workflow.md。

---

## Phase B：分镜脚本生成（按模式分支）

**两分支共享同一套硬约束**（时长、组限制、台词格式、场级连贯性、妆造名标注等，清单见 `references/phase-b-detailed.md`「硬约束」），差异仅在输出格式。**上下文只持有当前场**；会话中断后检查已有产出确定续写点（断点恢复详见各分支文档）。

- **详细模式（默认）**：逐场生成场→组→镜 JSON（17字段），每场 Write 一个独立 `场文件/场{N}.json`（**不用 Edit 追加大 JSON**——超长追加载荷易损坏整个文件）；完成后 `expand_scenes_to_groups.py --input 场文件/ --output-dir 分组/` 一条命令完成合并+逐文件校验+组时间归零+拆分 → `references/phase-b-detailed.md`
- **精简模式**：逐场生成讲戏式 Markdown（一段一镜），Write 建初始 `分镜脚本.md`（含 `<!-- END -->` 标记），后续每场 Edit 替换标记追加；完成后逐个 Write `组{N}.md` → `references/phase-b-simplified.md`

---

## 阶段二：参考图生成（独立 session）

通过 `meta_query(scope=config)` 返回的 `config.reference_image_mode` 选择（未设置默认 `visual_anchor`）。两种分镜模式均支持以下参考图模式：

| 模式 | 产出 | 详细文档 |
|------|------|---------|
| `visual_anchor`（默认） | 视觉锚点_任务表.json：按角色阶段每场一张锚点图，场内阶段串行、场间并行 | `references/phase-2-visual-anchors.md` |
| `storyboard_images` | 分镜图_任务表.json：每镜头一张，场内帧链串行（参考帧模式） | `references/phase-2-storyboard-images.md` |
| `none` | 跳过参考图生成；video-director 仅用角色/场景/道具参考图 | — |

两模式共用的收集/排序/铁律/净化/模板/校验规则见 **`references/phase-2-common.md`**（单一事实源）。

**质量四条铁律**（一行版）：1. 在场必引参考（局部入画/站位被点名的具名角色都进 `cast`+`images`）；2. 无图龙套时代锚（具名无图→硬终止补图；无名路人锁时代服化+降权句）；3. 单帧画布（禁 multi-panel/宫格/collage）；4. 禁烧字幕。

**提示词净化（硬规则）**：提交给生图模型的 prompt 必须为纯画面描述语言，禁止混入元约束/元语言（11 类必删项清单见 phase-2-common.md）；`validate_task_table.py` 对残留输出告警。

Agent 编写任务表 → `validate_task_table.py --check 任务表.json --mode {anchor|storyboard}` 校验 → 加载 art-director 以 sequential 模式执行。

---

## 最终产出结构

```
{剧集号}/
└── 分镜/
    ├── 分镜稿_临时.md              ← Phase A 产出（过程产物，不供下游消费）
    ├── 〔详细模式〕场文件/场{N}.json（逐场直写）→ 分镜脚本.json + 分组/组{N}.json（expand_scenes_to_groups.py 合并+拆出）
    ├── 〔精简模式〕分镜脚本.md + 分组/组{N}.md（Agent 直接写入）
    ├── 〔visual_anchor〕视觉锚点_任务表.json + 视觉锚点/锚点_场{N}{阶段?}_{场景名}.png
    ├── 〔storyboard_images〕分镜图_任务表.json + 分镜图/组{N}_镜{M}.png
    └── 〔none〕无参考图产出
```

---

## 参考文档（按需加载）

**Phase A / storytelling**
- `references/storytelling/workflow.md` — A2~A6 五步实操手册（分场规则、节点表、戏核/shot flow、缩略图、台词时长模型）
- `references/storytelling/templates.md` — 产出模板 T1~T5
- `references/storytelling/floobynooby-core.md` — 分镜方法论九原则
- `references/storytelling/night-nuo-case-study.md` — 案例精华（完整档案在 `doc/storytelling-night-nuo-case/`）

**Phase B**
- `references/phase-b-detailed.md` — 详细模式：JSON 格式、16 条硬约束、场级连贯性、Write+Edit 流程、拆分脚本
- `references/phase-b-simplified.md` — 精简模式：写作要求、格式规范、示例、组文件直接写入
- `references/examples.md` — 详细模式完整填充示例

**阶段二**
- `references/phase-2-common.md` — 两模式公共规范（单一事实源）
- `references/phase-2-visual-anchors.md` — 视觉锚点图：角色阶段拆分、双语 prompt、锚点模板与示例
- `references/phase-2-storyboard-images.md` — 串行分镜图：参考帧链、英文 prompt、帧模板与示例
