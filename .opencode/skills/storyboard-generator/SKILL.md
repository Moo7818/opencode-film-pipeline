---
name: storyboard-generator
description: 将分集剧本先经 storytelling pipeline 精简版创作分镜稿，再拆解为场→组→镜分镜脚本。场=连续物理空间（非戏剧节拍）；同空间多节拍为多组。支持 detailed JSON / simplified Markdown。reference_image_mode=visual_anchor（默认）时按角色阶段为每场生成视觉锚点图（sequential：场内阶段串行、场间并行）锁定场景/氛围/人物站位；reference_image_mode=storyboard_images 时产出 sequential 参考帧任务表（场内前帧成图作后帧主连续参考，场间并行）；reference_image_mode=none 时跳过参考图生成。分镜导演 Agent 执行分镜制作时加载。涉及分镜脚本、镜头分解、分镜图/视觉锚点任务表时使用。底层执行技能，由分镜导演按需加载。
---

# 分镜脚本生成

将分集剧本拆解为**场→组→镜**三级分镜脚本，输出独立组文件供下游消费。

**核心原则：**
- Agent 用自身 LLM **理解剧本、创作分镜**，直接写文件
- **场 = 连续物理空间**（与 producer 场景设定一致）；戏剧节拍/时间流逝节点用**组**表达，禁止按节拍拆场
- 脚本仅做**机械拆分**（场→组展开），不依赖 Python 管线做内容校验
- 分镜图为 **sequential 参考帧模式**：同场帧链用前帧成图作后帧主连续参考
- **本产出主要供 AI 视频生成消费**：描写精炼直接，心理活动简要提示，表演抓核心动作

---

## Agent 执行隔离

**阶段一（分镜脚本）与阶段二（参考图任务表）必须由不同的子 Agent session 执行。**

| 维度 | 阶段一：分镜脚本 | 阶段二：参考图任务表 |
|------|----------------|-------------------|
| 执行者 | storyboard-director（session 1） | storyboard-director（session 2，fresh context） |
| 输入 | 剧本.md + 全局设定 + 分镜稿_临时.md | 组{N}.json/md（含场号） + project_config.json + 参考图目录 |
| 产出 | 分镜脚本.json/md + 分组/组{N}.json/md | 视觉锚点_任务表.json（visual_anchor）或 分镜图_任务表.json（storyboard_images） |
| 上下文 | 含多轮创作思考（戏剧结构、镜头逻辑、台词校验） | **干净上下文**，仅读取结构化组文件和参考图清单 |

**隔离理由**：阶段一涉及大量创意思考（storytelling pipeline 5 步、台词时长计算、场级连贯性推理），这些中间推理会占据上下文窗口。若同一 session 继续执行阶段二，Agent 注意力被前期创作上下文稀释，容易偏离 prompt 模板的严格格式要求，导致映射块遗漏、参考图排序错误、Feeling 字段缺失等问题。

**编排方式**：orchestrator 在阶段一完成后，spawn 一个新的 storyboard-director session 执行阶段二。新 session 从磁盘读取阶段一的产出文件（组{N}.json/md），不继承前序对话上下文。

---

## 工作流程

```
┌─ 阶段一：episode_storyboard_script ─────────────────────┐
│  ⚡ Agent Session 1（storyboard-director）               │
│                                                         │
│  Step 0：轻量总体规划（快速落盘）                        │
│    读剧本 + 读所有设定 → 物理分场（场列表+场名称）        │
│    → 立即写入 分镜稿_临时.md（仅场级结构）               │
│                                                         │
│  Step 1~N：逐场 分析→生成→写入（每场独立循环）           │
│    对每一场：                                            │
│      a. 分析该场 shot flow + 分组 + 台词时长（仅本场）    │
│      b. 生成该场 JSON / MD（仅本场镜头）                 │
│      c. Write（场1）或 Edit（场2+）追加到分镜脚本文件     │
│      d. 该场分析笔记追加写入 分镜稿_临时.md              │
│    → 下一场                                              │
│                                                         │
│  全部场完成后：                                          │
│    ├─ 详细模式 → expand_scenes_to_groups 拆分            │
│    └─ 精简模式 → 逐个 Write 组{N}.md                    │
│                                                         │
│  → Session 1 结束，产出落盘                              │
└─────────────────────────────────────────────────────────┘
          ↓（文件交接：组{N}.json/md + 剧集级参考图就绪）
┌─ 阶段二：参考图生成（按 reference_image_mode 分支）──────┐
│  ⚡ Agent Session 2（storyboard-director，fresh context） │
│                                                         │
│  ├─ visual_anchor（默认）：视觉锚点图                    │
│  │   按角色阶段为每场生成锚点图（无角色变化时每场一张）  │
│  │   sequential：场内阶段串行，场间并行                  │
│  │   → 详见 references/phase-2-visual-anchors.md         │
│  │                                                       │
│  ├─ storyboard_images：串行分镜图                        │
│  │   每镜头一张，场内帧链串行（参考帧模式）               │
│  │   → 详见 references/phase-2-storyboard-images.md      │
│  │                                                       │
│  └─ none：跳过参考图生成                                 │
│      video-director 仅使用角色/场景/道具参考图            │
│                                                         │
│  → Session 2 结束                                       │
└─────────────────────────────────────────────────────────┘
```

> **数据流原则**：Step 0 负责信息采集（剧本 + 设定）与物理分场，产出分镜稿_临时.md 的场级结构。Step 1~N 逐场循环：每场分析时须同时消费分镜稿_临时.md（场级结构 + 已写入场的分析笔记）和原始分集剧本（逐字台词），**严禁只读其一**。
>
> **阶段间数据交接**：阶段一与阶段二通过磁盘文件交接，不依赖对话上下文。阶段二 Agent 仅需读取：组{N}.json/md（分镜内容，含场号/场名称）、project_config.json（模型配置）、参考图目录（角色/场景/道具/风格）。画面比例固定 `16:9`，无需从配置读取。

---

## 模式选择

通过 `project_config.json` 的 `storyboard_mode` 字段选择分镜输出模式：

| 模式 | 值 | 分镜脚本输出 | 组文件格式 | 适用场景 | 详细文档 |
|------|-----|-------------|-----------|---------|---------|
| 详细模式（默认） | `"detailed"` 或未设置 | 结构化 JSON（17字段×N镜头） | `组{N}.json` | 需要精确镜头控制 | `references/phase-b-detailed.md` |
| 精简模式 | `"simplified"` | 纯 Markdown（讲戏式叙事） | `组{N}.md` | 快速产出、text2video、讲戏式叙事 | `references/phase-b-simplified.md` |

**Step 0（总体规划）在两种模式下完全一致**，差异仅在 Step 1~N 的输出格式。

**模式判断**：读取 `project_config.json` 的 `storyboard_mode` 字段，值为 `"simplified"` 时进入精简模式，否则按详细模式处理。

---

## Step 0：轻量总体规划（快速落盘）

> 源自 15 步电影级分镜管线。详细方法论见 `references/storytelling/` 下文档。Step 0 只做场级规划，shot flow / 缩略图 / 台词时长下沉到 Step 1~N 逐场阶段。

### 读取剧本与设定

读取以下内容，产出戏剧结构笔记：

- **分集剧本**：`project/{项目名}/{剧集号}/剧本.md` — 画面内容（AI动效描述 + 产品展示清单）、口播文案（旁白配音文本）、时长（单集15-30秒）
- **全局设定**：`project/{项目名}/全局依赖/全局设定.md`
- **角色设定**：`project/{项目名}/全局依赖/角色设定/`
- **场景设定**：`project/{项目名}/全局依赖/场景设定/`
- **道具设定**：`project/{项目名}/全局依赖/道具设定/`

理解故事内容、画面描述、口播文案，产出戏剧结构笔记。

> Step 0 负责设定采集（角色/场景/道具设定），Step 1~N 逐场阶段无需重复读取设定；但逐场生成时必须重新读取分集剧本以确保台词逐字一致。

### 物理分场（场 = 连续物理空间）

A2 产出两层结构，**不得混用**：

| 层 | 名称 | 划分依据 | 用途 |
|----|------|---------|------|
| 故事节点 | 时间流逝地图 | 银幕时间 vs 故事时间的变化 | 控制节奏、时长、蒙太奇手法 |
| **场** | 物理空间连续单元 | **同一连续物理空间 + 连续故事时间** | 分镜脚本场级边界；分镜图串行链边界 |

#### 故事节点（时间流逝，不直接等于场）

**核心认知**：戏剧不是物理时空的 1:1 复现。银幕几秒可对应故事世界数小时/数天；仅在剧情点上银幕时间≈故事时间。用**故事节点**标注时间流逝类型，**不要**用时间流逝变化点直接当分场边界。

| 节点类型 | 银幕时间 vs 故事时间 | 用途 | 典型手法 |
|---------|---------------------|------|---------|
| 时间压缩 | 银幕秒 ≪ 故事时 | 快速交代、跨越时段 | 蒙太奇、跳切、旁白带过 |
| 实时 | 银幕 ≈ 故事 | 剧情点：转折、对峙、揭晓 | 连续叙事、同步台词 |
| 时间膨胀 | 银幕 ＞ 故事 | 放大关键瞬间 | 慢动作、微表情特写 |

操作：通读剧本 → 标时间跳跃与流逝类型 → 每个节点记录：节点名、时间流逝类型、故事世界时长、银幕预估、关键信息、**所在物理空间**。

#### 物理分场规则（场 = 连续物理空间）

**场的定义（硬约束）**：一场 = 在**同一个独立物理空间**内、故事时间**连续不跳切到他处**的全部镜头。与 producer 场景设定一致：一个物理空间 = 一个房间/建筑/户外地点（非子区域机位）。

**必须新开一场**（满足任一即切）：
1. **物理空间切换** — 角色离开 A 地进入 B 地（茶肆内 → 街口 → 包子铺 = 至少 3 场）
2. **显著时间断裂** — 同地但日/夜切换、或显式时间跳跃（"三日后"），视觉光影与调度链已断
3. **平行切出** — 插叙/平行蒙太奇切到另一空间，返回原空间时若中间已切走，返回后开新场或并入原场需按连续性判断；默认**切走即断链**，返回开新场

**禁止**因下列原因拆场（应留在同一场，用**组**区分戏剧节拍）：
- 同一物理空间内的多个戏剧节拍/故事节点（发布→问答→排队 同在茶肆日/内 → **一场多组**）
- 同一空间内景别/机位变化（柜台特写 vs 全景仍是同一场）
- 纯情绪/节奏变化而无空间或时间断裂

**一场多节点示例**（正确）：
```
场1 春生茶肆·日/内
  组1 ← 节点N1 会员制发布（实时）
  组2 ← 节点N3 排队办卡（微压缩）
  组3 ← 节点N4 小二翻簿（实时）
场2 春生茶肆门口·日/外   ← 物理空间变
场3 赵胖包子铺·日/内     ← 物理空间变
场4 春生茶肆·夜/内       ← 同地但日→夜，时间断裂
```

**错误示例**（EP04 旧病）：把「茶肆日/内」的发布、排队、翻簿拆成场1/3/4 → 同空间被切断，分镜图串行参考帧链断裂，角色/布景在组间漂移。

> 模板见 `references/storytelling/templates.md` Template 11。故事节点表标注物理空间；**A3 按物理场聚合节点**，不是一对一把每个节点当成一场。

### A3：场次戏剧地图（sequence map）

基于 A2-b 的**物理场**列表建场次地图。同一物理场内可含多个故事节点/戏剧节拍，在场内用段落或后续「组」表达。每场标注：物理空间名、含哪些故事节点、戏核、观众站位、压力来源、镜头总策略。

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

**两个分支均采用 Write + Edit 逐场追加**：Write 建初始文件（仅场1），后续每场用 Edit 追加到文件末尾。agent 上下文只持有当前场，不需要持有已写入的场。会话中断后重新拉起时，Read 已有文件确定已完成场数，从缺失场继续。详见各分支文档。

### 详细模式（默认）

逐场生成结构化 JSON（场→组→镜，17字段×N镜头），Write 建初始 `分镜脚本.json`（含场1），后续每场用 Edit 匹配 `  }\n]` 追加新场。全部完成后调用 `expand_scenes_to_groups.py` 拆分为 `组{N}.json`。

> **按需加载**：完整的 JSON 格式规范、场级连贯性规则、16 条硬约束、Write+Edit 逐场追加与断点恢复、拆分脚本用法详见 → `references/phase-b-detailed.md`

### 精简模式

逐场生成讲戏式 Markdown（一段一镜，技术参数融入叙述），Write 建初始 `分镜脚本.md`（含文件头+场1+`<!-- END -->`标记），后续每场用 Edit 替换标记追加新场。全部完成后逐个 Write `组{N}.md`（不使用脚本拆分）。

> **按需加载**：完整的写作要求、格式规范、示例、Write+Edit 逐场追加与断点恢复、组文件直接写入流程详见 → `references/phase-b-simplified.md`

---

## 阶段二：参考图生成（按 reference_image_mode 分支）

> **独立 Agent session 执行**：本阶段必须在 fresh context 中执行，不得继承阶段一的对话上下文。详见上方「Agent 执行隔离」节。

通过 `project_config.json` 的 `reference_image_mode` 字段选择参考图模式（未设置时根据 `use_storyboard_images` 推断：`true`→`storyboard_images`，`false`/未设置→`visual_anchor`）。两种分镜模式（detailed/simplified）均支持以下参考图模式。

> **提示词净化规范（元约束净化 · 硬规则）**：所有提交给生图模型的 `prompt` 必须为**纯画面描述语言**，禁止混入"本应属于智能体编写规范、而非发送给模型"的元约束/元语言（段落放置/编排指令、Decision rule、括号标签机制解释、编写者脑补禁令、编译器/流水线说明、中文事实保留指令、占位符机制解释、锚点职责定位从句与职责块、Mapping 内机制解释、道具配对说明括号等 11 类必删项）；同时必须保留身份锁短语与逐角色身份锁句、`Image N:` 标签与优先级语义、单帧声明、TEXT POLICY 禁字幕块、AVOID 负面清单与背景人物降权句。完整规则见 `phase-2-visual-anchors.md` 与 `phase-2-storyboard-images.md` 的「提示词净化规范」节；`validate_task_table.py` 会对残留输出告警。

### visual_anchor（默认）：视觉锚点图

按角色阶段为每场生成视觉锚点图（sequential：场内阶段串行、场间并行），锁定场景空间、氛围基调、人物站位与关键动作神态。有具名角色入场/离场时按阶段拆分（如 1A、1B）；无角色变化时该场仅一张锚点图。同场多阶段锚点图在视频生成阶段由各阶段覆盖的组分别引用。

**身份锁定优先于场景构建**：每个有角色参考图的 `cast` 成员必须逐一绑定对应图片；prompt 的第一项实质内容必须是 `IDENTITY LOCK — HIGHEST PRIORITY`，并在任何场景/动作前升级为 actor continuity lock：`Reference Image N character（中文角色名/职责） must remain recognizable as the same actor/person...`。必须明确脸部身份绝对优先、历史外观冲突时只适配 `wardrobe/hairstyle/setting`、不得改变 facial identity/structure/skin features/body proportions、不得生成相似替代人物或职业原型新人物。首次绑定不得写成 `Shopkeeper ...`，后文如使用 `Shopkeeper (the same referenced person)` 只能作为已绑定参考人物简称。

**visual_anchor Prompt 使用双语分工**：英文只负责段落标题、IDENTITY/continuity hard constraints、Reference priority、单帧/构图/摄影/灯光/材质/画质/风格和负面约束；角色名与关系、场景名和空间内容、动作、站位、神态、台词相关内容、道具内容、时代/剧情事实保留中文，不翻译、不因翻译重写外貌。Prompt 用 English control shell 包裹中文内容，例如 `Reference Image 1 character（掌柜角色）站在右侧柜台后擦拭茶杯。`。Anchor 类型与优先级保持英文，绑定对象名称/描述保持中文。

无参考的无名信使、侍者、路人等不属于 referenced characters，只能作为次要时代背景人物生成，不进 `cast`/`images`；实际 FRAME DETAIL 必须在时代服化和中文动作/站位后加入 `not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`，禁止视觉中心、英雄式特写或抢占主角权重；具名但无参考图必须暂停补图。

**sequential 模式（场内阶段串行、场间并行）**：
- `mode` 为 `"sequential"`
- 每个 task 含 `id` / `scene` / `group`（阶段标识如 1A/1B） / `scene_name` / `shot_range` / `cast`
- 同场阶段按播放顺序 `depends_on` 串行（非首阶段 `images` 含 `{{PREV_OUTPUT}}`，运行时替换为前一阶段锚点成图 URL）；首阶段无 `depends_on`
- 不同场无依赖，可并行
- 无角色阶段拆分时该场仅一个 task（等价旧 batch 单场一张，向后兼容）
- 锚点图须包含完整的角色动作与神态描述（影视级静帧质感）

**质量四条铁律**（详情与模板见 phase-2-visual-anchors）：
1. **在场必引参考**：该场全部组中出场的具名角色都要进 `cast`+`images`
2. **无图龙套时代锚**：具名无图→硬终止补图；无名路人必须锁项目时代服化
3. **单帧画布**：禁 multi-panel / 2×2 / collage / storyboard sheet
4. **禁烧字幕**：禁 subtitle/caption/lower-third/台词条

Agent 直接编写 `视觉锚点_任务表.json` → `validate_task_table.py` 校验 → 加载 art-director 以 sequential 模式执行（场内阶段串行、场间并行）。画面比例固定 `16:9`。

> **按需加载**：参考图收集、出场引用铁律、龙套时代锚、单帧/禁字幕模板、任务表与校验详见 → `references/phase-2-visual-anchors.md`

### storyboard_images：串行分镜图

每镜头一张分镜图，场内帧链串行（参考帧模式）。

**参考帧模式（硬约束，不可降级为 batch）**：
- `mode` 必须为 `"sequential"`
- 每帧一个 task，含 `id` / `scene` / `group` / `cast`；非场首帧必须有 `depends_on`，且 `{{PREV_OUTPUT}}` 在**全部角色参考之后、风格之前**
- **场 = 物理空间连续单元**（与 Phase A/B 一致）。同一 `scene` 内全部帧按播放顺序连成**一条** `depends_on` 链（跨组不断链）
- 前帧生成完成后，其输出 URL 替换 `{{PREV_OUTPUT}}`，作为后帧的**主空间连续参考**（参考帧），再提交后帧
- 不同物理场（不同 `scene`）无依赖，可并行
- 禁止：省略 `depends_on`、用 batch 并发生成同场多帧、同场断链、跨物理场串 `depends_on`

**分镜图质量四条铁律**（详情与模板见 phase-2-storyboard-images；校验器强制部分条目）：
1. **在场必引参考**：局部入画/非焦点/站位被点名的具名角色都要进 `cast`+`images`
2. **无图龙套时代锚**：具名无图→硬终止补图；无名路人必须锁项目时代服化
3. **单帧画布**：禁 multi-panel / 2×2 / collage / storyboard sheet
4. **禁烧字幕**：禁 subtitle/caption/lower-third/台词条

Agent 直接编写 `分镜图_任务表.json` → `validate_task_table.py` 校验（含链完整性、cast、单帧/禁字幕）→ 加载 art-director 以 sequential 模式执行。画面比例固定 `16:9`。

> **按需加载**：参考图收集、出场引用铁律、龙套时代锚、单帧/禁字幕模板、任务表与校验详见 → `references/phase-2-storyboard-images.md`

### none：跳过参考图生成

不生成任何参考图。video-director 仅使用角色/场景/道具参考图作为视频生成的参考素材。

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
    │
    ├── 〔精简模式〕
    │   ├── 分镜脚本.md             ← Phase B 产出（讲戏式 Markdown）
    │   ├── 分组/                   ← Agent 直接写入（组{N}.md）
    │
    ├── 〔reference_image_mode=visual_anchor（默认）〕
    │   ├── 视觉锚点_任务表.json    ← 阶段二产出（sequential：场内阶段串行、场间并行）
    │   └── 视觉锚点/               ← 按阶段生成产物（锚点_场{N}{阶段?}_{场景名}.png）
    │
    ├── 〔reference_image_mode=storyboard_images〕
    │   ├── 分镜图_任务表.json      ← 阶段二产出（sequential 模式，每镜头一张）
    │   └── 分镜图/                 ← 逐帧生成产物（组{N}_镜{M}.png）
    │
    ├── 〔reference_image_mode=none〕
    │   └── （无参考图产出）
```

---

## 参考文档

### Phase B 分支文档（按需加载）
- `references/phase-b-detailed.md` — 详细模式：JSON 格式、16 条硬约束、场级连贯性规则、expand_scenes_to_groups.py
- `references/phase-b-simplified.md` — 精简模式：写作要求、格式规范、示例、组文件直接写入流程

### 阶段二文档（按需加载）
- `references/phase-2-visual-anchors.md` — 视觉锚点图绘制（默认模式）：角色阶段拆分、参考图收集、任务表编写、prompt 模板、校验
- `references/phase-2-storyboard-images.md` — 分镜图绘制（串行模式）：逐帧链式生成、参考图收集、任务表编写、prompt 模板、校验

### 示例
- `references/examples.md` — 详细模式与精简模式的完整示例

### 分镜稿创作（storytelling pipeline）
- `references/storytelling/floobynooby-core.md` — 分镜核心方法论（9 条原则）
- `references/storytelling/workflow.md` — 15 步管线详细说明（精简为 5 步使用）
- `references/storytelling/templates.md` — 10 种产出模板
- `references/storytelling/night-nuo-case-study.md` — 完整案例研究
