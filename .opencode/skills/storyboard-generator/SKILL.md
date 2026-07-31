---
name: storyboard-generator
description: 将分集剧本先经 storytelling pipeline 精简版（5步）创作分镜稿，再基于分镜稿拆解为场→组→镜结构化分镜脚本。支持详细模式（JSON）和精简模式（讲戏式 Markdown）。仅当 use_storyboard_images=true 时生成分镜图任务表。分镜导演 Agent 依据此技能执行分镜制作。当任务涉及生成分镜脚本、镜头分解、分镜图任务表时加载此技能。注意：这是底层执行技能，由分镜导演 Agent 按需加载，不直接响应路由。
---

# 分镜脚本生成

将分集剧本拆解为**场→组→镜**三级分镜脚本，输出独立组文件供下游消费。

**核心原则：**
- Agent 用自身 LLM **理解剧本、创作分镜**，直接写文件
- 脚本仅做**机械拆分**（场→组展开），不依赖 Python 管线做内容校验
- **本产出主要供 AI 视频生成消费**：描写应精炼直接，人物心理活动只需简要提示，表演/微表情抓住核心动作即可，避免心理独白式渲染

---

## 工作流程

```
┌─ 阶段一：episode_storyboard_script ─────────────────────┐
│                                                         │
│  Phase A：分镜稿创作（storytelling pipeline 精简版）      │
│    A1. 读剧本 + 读所有设定产物 → 戏剧结构笔记              │
│    A2. 时空合理化与分场 → 故事节点（时间流逝地图）         │
│    A3. 场次戏剧地图（sequence map）                      │
│    A4. 逐场戏核 + shot flow                              │
│    A5. 粗略缩略图任务（rough thumbnails）                 │
│    A6. 台词时长校验（Agent 自主计算，无需脚本）           │
│    → 产出：分镜稿_临时.md                                │
│                                                         │
│  Phase B：分镜脚本生成（按模式分支）                      │
│    ├─ 详细模式 → 分镜脚本.json → expand_scenes_to_groups  │
│    └─ 精简模式 → 分镜脚本.md → Agent直接写入组{N}.md     │
└─────────────────────────────────────────────────────────┘
          ↓（剧集级参考图生成完成后）
┌─ 阶段二：episode_storyboard_images ─────────────────────┐
│  （仅 use_storyboard_images=true 时执行）                │
│  → 详见 references/phase-2-storyboard-images.md          │
└─────────────────────────────────────────────────────────┘
```

> **数据流原则**：Phase A 负责所有信息采集（剧本 + 设定），产出分镜稿_临时.md。Phase B 必须同时消费 Phase A 的产出（分镜稿_临时.md）和原始分集剧本（剧本.md）—— 分镜稿提供结构与镜头逻辑，分集剧本提供逐字台词与剧情保真，**严禁只读其一**。

---

## 模式选择

通过 `project_config.json` 的 `storyboard_mode` 字段选择分镜输出模式：

| 模式 | 值 | Phase B 输出 | 组文件格式 | 适用场景 | 详细文档 |
|------|-----|-------------|-----------|---------|---------|
| 详细模式（默认） | `"detailed"` 或未设置 | 结构化 JSON（17字段×N镜头） | `组{N}.json` | 需要精确镜头控制 | `references/phase-b-detailed.md` |
| 精简模式 | `"simplified"` | 纯 Markdown（讲戏式叙事） | `组{N}.md` | 快速产出、text2video、讲戏式叙事 | `references/phase-b-simplified.md` |

**Phase A（分镜稿创作）在两种模式下完全一致**，差异仅在 Phase B 的输出格式。

**模式判断**：读取 `project_config.json` 的 `storyboard_mode` 字段，值为 `"simplified"` 时进入精简模式，否则按详细模式处理。

---

## Phase A：分镜稿创作（storytelling pipeline 精简版）

> 源自 15 步电影级分镜管线，精简为 5 步适配短视频（15-30 秒/集）。详细方法论见 `references/storytelling/` 下文档。

### A1：读剧本 + 读所有设定产物

读取以下内容，产出戏剧结构笔记：

- **分集剧本**：`project/{项目名}/{剧集号}/剧本.md` — 画面内容（AI动效描述 + 产品展示清单）、口播文案（旁白配音文本）、时长（单集15-30秒）
- **全局设定**：`project/{项目名}/全局依赖/全局设定.md`
- **角色设定**：`project/{项目名}/全局依赖/角色设定/`
- **场景设定**：`project/{项目名}/全局依赖/场景设定/`
- **道具设定**：`project/{项目名}/全局依赖/道具设定/`

理解故事内容、画面描述、口播文案，产出戏剧结构笔记。

> Phase A 负责设定采集（角色/场景/道具设定），Phase B 无需重复读取设定；但 Phase B 必须重新读取分集剧本以确保台词逐字一致（详见 Phase B 数据流原则）。

### A2：时空合理化与分场

**核心认知**：戏剧不是物理时空的 1:1 复现。银幕上的几秒钟可能对应故事世界中的数小时、数天乃至数年；只有在剧情点（关键转折、情绪爆发、信息揭晓）上，银幕时间才回归与物理世界等效的实时流逝。通过分场手段将剧情分解为不同时间流逝状态下的**故事节点**。

**故事节点三类型**：

| 节点类型 | 银幕时间 vs 故事时间 | 用途 | 典型手法 |
|---------|---------------------|------|---------|
| 时间压缩 | 银幕秒 ≪ 故事时 | 快速交代剧情、跨越时段 | 蒙太奇、跳切、旁白带过 |
| 实时 | 银幕 ≈ 故事 | 剧情点：转折、对峙、揭晓 | 连续叙事、同步台词 |
| 时间膨胀 | 银幕 ＞ 故事 | 放大关键瞬间 | 慢动作、微表情特写 |

**分场操作**：
1. 通读分集剧本，识别时间跳跃点（显式标记如"三日后""翌日""半年后"，及场景切换隐含的时间流逝）
2. 为每段剧情标注时间流逝类型（压缩/实时/膨胀）
3. 以时间流逝的变化点作为分场边界，将剧情切分为故事节点
4. 每个节点记录：节点名、时间流逝类型、故事世界时长、银幕预估时长、该节点要交代的关键信息

> 模板见 `references/storytelling/templates.md` Template 11。产出的故事节点表作为 A3 场次戏剧地图的分场依据。

### A3：场次戏剧地图（sequence map）

基于 A2 的故事节点表，将每个节点展开为可演绎的戏剧段落，每段标注戏核、观众站位、压力来源、镜头总策略。

> 模板见 `references/storytelling/templates.md` Template 1。

### A4：逐场戏核 + shot flow

为每场戏确定：戏核、观众站位、shot flow（镜头推进逻辑）、开场景别、第一刀 close-up 时机、高潮镜头职责、reaction owner、连续性锚点。

> 模板见 `references/storytelling/templates.md` Template 2。

### A5：粗略缩略图任务（rough thumbnails）

逐场生成面板级缩略图任务表，每个面板包含画面、景别、任务、cut 动机、hold、声音/台词。

> 模板见 `references/storytelling/templates.md` Template 3。

### A6：台词时长校验（Agent 自主计算）

**Agent 自主判断情绪并计算台词时长，无需脚本。** 对 A5 中每个含台词面板执行：

**情绪语速模型**（基础语速 4.0 chars/s × 情绪系数）：

| 情绪 | 系数 | 实际语速 | 典型场景 |
|------|------|---------|---------|
| 悲恸 | 0.50x | 2.0 chars/s | 哽咽/啜泣/泣不成声 |
| 犹豫 | 0.60x | 2.4 chars/s | 结巴/迟疑/支吾 |
| 沉重 | 0.75x | 3.0 chars/s | 颤抖/压抑/悲愤 |
| 低语 | 0.85x | 3.4 chars/s | 轻声/耳语/呢喃 |
| 正常 | 1.00x | 4.0 chars/s | 对白/旁白叙述 |
| 急促 | 1.15x | 4.6 chars/s | 紧张/慌张/匆忙 |
| 激昂 | 1.25x | 5.0 chars/s | 高声/洪亮/坚定 |
| 爆发 | 1.30x | 5.2 chars/s | 呐喊/咆哮/怒吼 |

**计算公式**：
- 总需时 = 朗读时间 + 标点停顿 + 情绪停顿
- 朗读时间 = 中文字数 ÷ 情绪语速
- 标点停顿：逗号 0.3s / 句号·感叹号·问号 0.5s / 省略号 0.8s / 破折号 0.5s
- 情绪停顿：悲恸每分句 +0.5s / 犹豫 +0.4s / 沉重 +0.3s / 低语 +0.2s / 爆发 +0.1s

**校验原则**：台词需时 ≤ 面板 hold（严格容纳，无溢出容忍）

**超时修复优先级**：1.压缩台词 → 2.调整情绪 → 3.延长 hold → 4.拆分面板

> 计算结果直接写入面板的 `台词时长` 字段，校验汇总表嵌入分镜稿末尾。详见 `references/storytelling/templates.md` Template 10。

### Phase A 产出

将 A1-A6 的产出整合写入 `{剧集号}/分镜/分镜稿_临时.md`（过程产物，不供下游消费）。

---

## Phase B：分镜脚本生成（按模式分支）

Phase A 完成后，根据 `storyboard_mode` 进入对应分支。**两个分支共享同一套硬约束**（时长、组限制、台词格式、场级连贯性、妆造名标注等），差异仅在输出格式。

### 详细模式（默认）

生成结构化 JSON（场→组→镜，17字段×N镜头），调用 `expand_scenes_to_groups.py` 拆分为 `组{N}.json`。

> **按需加载**：完整的 JSON 格式规范、场级连贯性规则、16 条硬约束、拆分脚本用法详见 → `references/phase-b-detailed.md`

### 精简模式

生成讲戏式 Markdown（一段一镜，技术参数融入叙述），Agent 直接使用 Write 工具逐个写入 `组{N}.md`（不使用脚本拆分）。

> **按需加载**：完整的写作要求、格式规范、示例、组文件直接写入流程详见 → `references/phase-b-simplified.md`

---

## 阶段二：分镜图绘制（条件执行）

仅当 `project_config.json` 中 `use_storyboard_images=true` 时执行。两种模式均支持分镜图绘制。Agent 直接使用 Write 工具编写 `分镜图_任务表.json`（含逐组参考图匹配），然后运行 `validate_task_table.py` 校验。

> **按需加载**：参考图收集、任务表编写规范、校验流程详见 → `references/phase-2-storyboard-images.md`

---

## 最终产出结构

```
{剧集号}/
└── 分镜/
    ├── 分镜稿_临时.md              ← Phase A 产出（过程产物，不供下游消费）
    │
    ├── 〔详细模式〕
    │   ├── 分镜脚本.json           ← Phase B 产出（场→组→镜，17字段×N镜头）
    │   ├── 分组/                   ← expand_scenes_to_groups.py 拆出（组{N}.json）
    │   └── 分镜图_任务表.json      ← 条件：use_storyboard_images=true 时生成
    │
    ├── 〔精简模式〕
    │   ├── 分镜脚本.md             ← Phase B 产出（讲戏式 Markdown）
    │   ├── 分组/                   ← Agent 直接写入（组{N}.md）
    │   └── 分镜图_任务表.json      ← 条件：use_storyboard_images=true 时生成
```

---

## 参考文档

### Phase B 分支文档（按需加载）
- `references/phase-b-detailed.md` — 详细模式：JSON 格式、16 条硬约束、场级连贯性规则、expand_scenes_to_groups.py
- `references/phase-b-simplified.md` — 精简模式：写作要求、格式规范、示例、组文件直接写入流程

### 阶段二文档（按需加载）
- `references/phase-2-storyboard-images.md` — 分镜图绘制：参考图收集、任务表直接编写、校验

### 示例
- `references/examples.md` — 详细模式与精简模式的完整示例

### 分镜稿创作（storytelling pipeline）
- `references/storytelling/floobynooby-core.md` — 分镜核心方法论（9 条原则）
- `references/storytelling/workflow.md` — 15 步管线详细说明（精简为 5 步使用）
- `references/storytelling/templates.md` — 10 种产出模板
- `references/storytelling/night-nuo-case-study.md` — 完整案例研究
