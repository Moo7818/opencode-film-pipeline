# 阶段二公共规范（visual_anchor 与 storyboard_images 共用）

本文档是阶段二两种参考图模式的**单一事实源**：收集参考图、排序优先级、出场角色引用、龙套时代锚、单帧/禁字幕、风格匹配、文字检测、提示词净化、七段框架公共规则、任务表公共字段、执行与校验流程。模式专属内容（锚点阶段拆分与双语 prompt / 参考帧链与英文 prompt）见：

- `references/phase-2-visual-anchors.md` — 视觉锚点图（默认模式）
- `references/phase-2-storyboard-images.md` — 串行分镜图

---

## 0. 执行前提（两模式一致）

> **独立 Agent session 执行**：所有工作必须在 fresh context 中完成，不得继承阶段一的对话上下文（创作思考会稀释对 prompt 模板格式的注意力）。Agent 仅从磁盘读取：组{N}.json/md、参考图目录；配置经 `meta_query(scope=config)` 读取。

- 详细模式从 `组{N}.json` 读取，精简模式从 `组{N}.md` 读取
- **sequential 模式**：场内串行（`depends_on` 链，前序输出作为空间连续参考），场间并行
- **场 = 物理空间连续单元**（`场号` 由 `expand_scenes_to_groups.py` 注入组文件，任务 `scene` 必须与之一致）；若发现同一物理空间被拆成多个场号，先向 orchestrator 回报，不默默断链
- **目标模型**：`nano-banana-2`，2K，画面比例固定 `16:9`

---

## 1. Step 1：收集参考图清单

Agent 须用 LS 工具列出各参考图目录下的具体 `.png` 文件，记录完整路径，供逐场/逐帧引用。

| 参考图类型 | 来源路径 | 说明 |
|-----------|---------|------|
| 角色参考图 | `project/{项目名}/全局依赖/角色设定/角色参考图/*.png` | 全局角色参考图（含妆造匹配） |
| 场景参考图 | `project/{项目名}/{剧集号}/场景参考图/*.png` | 剧集级场景参考图（含本集场景变化） |
| 道具参考图 | `project/{项目名}/{剧集号}/道具参考图/*.png` | 剧集级道具参考图（含本集道具状态变化） |
| 风格参考图 | `project/{项目名}/前期采样/风格/*.png` | 全局视觉风格基准（色调、光影氛围、画面质感） |

> 如剧集级参考图目录不存在（无变化场景/道具），回退使用全局基准图：`全局依赖/场景设定/场景参考图/` 和 `全局依赖/道具设定/道具参考图/`。
>
> **道具全局基准文件名含出现场合**：回退引用全局道具基准图时，文件名格式为 `{道具名}_{出现场合}_基准.png`。需读取 `全局依赖/道具设定/具体设定/{道具名}.md` 中的 `出现场合` 字段，匹配正确的基准文件。仅引用该道具 `出现场合` 包含当前剧集号的基准图，**禁止**引用不属于本集的道具资产。
>
> **风格参考图缺失时硬终止**：未找到风格参考图时，不允许跳过风格参考，直接跳出并提示用户补充。

---

## 2. 参考图排序优先级（sequential 模式）

`images` 数组顺序决定模型注意力权重，两种模式共用同一骨架：

1. **Highest priority — 角色参考图**：每个出场角色一张，按戏剧重要性排序
2. **前序输出**（仅非首任务）：`{{PREV_OUTPUT}}` 占位符，紧接全部角色之后、场景参考之前（锚点模式称 Previous Phase Anchor，分镜图模式称 Previous Frame Anchor）
3. **Second priority — 场景参考图**：本场物理空间设定图，通常一张
4. **Third priority — 道具参考图**：每个重要道具一张
5. **Fourth priority — 风格参考图**：一张，**始终最后**

写入顺序：首任务 `角色… → 场景 → 道具… → 风格`；非首任务 `角色… → {{PREV_OUTPUT}} → 场景 → 道具… → 风格`。

**硬约束**：
- 角色参考必须在前序输出与风格之前（锁脸优先于锁构图/锁风格）
- `{{PREV_OUTPUT}}` 必须在全部角色之后、风格之前（**禁止**垫在风格之后——EP06 旧病：PREV 垫底导致锁脸失效）
- 禁止把 `{{PREV_OUTPUT}}` 省略或放到与 depends_on 不一致的位置
- 锚点模式禁止省略场景参考图（锚点图核心职责之一就是锁定场景空间）

> **映射契约**：`images[N-1]`、提示词中的 `Reference Image N`、`Image N:` 映射块必须指向同一张图。

---

## 3. 出场角色引用铁律

> **根因**：旧规则写「按需引用 / 未登场不引」，Agent 常只给**焦点角色**挂参考图，导致非焦点角色造型漂移。参考图要的是**可用的画面参考**，不是「只锁主角/说话人」。

### 何谓「在场」（必须挂参考）

扫描目标镜头/锚点镜头的 `场景描述`、`站位/调度`、`表演/微表情`、`台词` 后，下列任一成立即算在场：

| 信号 | 示例 | 是否必须 `images` 含其角色参考 |
|------|------|-------------------------------|
| 正脸/侧脸可见 | 「抬眼望小二」 | 是 |
| 身体/半身/背影可见 | 「立于柜台后」 | 是 |
| 仅手/脚/局部入画 | 「执笔手从画右入画」 | **是**（局部也要锁身份与服装） |
| 站位里被点名在场 | 「小二立于掌柜右侧」「眼神看向掌柜」 | **双方都要引** |
| 台词归属角色 | `掌柜："…"` | 若该角同时在画面内则必须引 |
| 纯画外音、完全不在画内 | 画外 trans 音 | 否 |

**禁止**：只按「焦点角色/说话人」引参考；禁止因「只露手/背影」而省略角色参考。

> 「在场」的扫描粒度因模式而异：锚点模式按**阶段锚点镜头**取阶段在场表（见 phase-2-visual-anchors.md）；分镜图模式按**帧**取组在场表（见 phase-2-storyboard-images.md）。

### `cast` 字段（任务表必填）

每个 task 增加：

```json
"cast": ["掌柜", "小二"]
```

- 只列**在场且有对应角色参考图的具名角色**中文名；无参考背景人物不列入；纯空镜/无角色帧可为 `[]`
- 中文名须与角色参考图文件名可匹配（文件名含该名，如 `掌柜_默认妆造.png`）
- `cast` 顺序 = `images` 中角色参考顺序 = REFERENCE IMAGE MAPPING 中 Character Identity Anchor 顺序
- 校验器会核对：`cast` 非空（有人在场时）、每个名字能在 `images` 角色路径中找到、Character Anchor 数量 = 角色图数量 = `cast` 长度

### Referenced 与 unreferenced/background characters

任务表必须把两类角色分开处理，不能用 `ALL characters` 合并。**Referenced characters**：`cast` 中每个具名角色都必须有且仅有一张对应角色参考图，逐一绑定写入角色段、`cast` 和 Character Identity Anchor，不得合并成一个总的「角色参考」。**Unreferenced/background characters**：无名背景人物不进 `cast`、`images`，只能作为远景/侧背/虚化的次要人物，并按下方「时代锚定」加入英文降权硬约束。

### 无参考图龙套 / 路人（造型漂移与朝代错位闭环）

| 角色类型 | 有无参考图 | 处理 |
|----------|------------|------|
| 具名角色（掌柜/小二等） | 有 | 必须引参考；禁止纯文字开脸 |
| 具名角色 | **无** | **硬终止**：不得开写该任务；回报 orchestrator 补角色参考或改分镜去掉该角具名出场。只有「无名的信使/路人」这类背景功能角色允许无图生成 |
| 无名龙套/路人（茶客甲、街人、无名信使） | 通常无 | 允许无图，但必须**时代锚定描述**；禁止抢戏、禁止特写正脸当主角 |
| 群演占画面主体且无一人有参考 | — | 优先改调度（虚化/背影/远景）；仍不够则硬终止补「群演氛围参考」或具名化+出参考图 |

**时代锚定（无图龙套强制）**：

1. 从 `全局依赖/全局设定.md` 读取时代（如「唐朝/盛唐」），写入 SCENE CONTINUITY 的 `{period_description}` 与 FRAME DETAIL（锚点模式保留中文原文；分镜图模式译为英文）。
2. 每个无图龙套写死时代、服化、动作和站位（唐：圆领袍/襦裙/幞头等；**禁止**清辫、民国长衫、现代T恤等错代），随后追加英文权重锁：`not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`。
3. AVOID 与 SCENE CONTINUITY 必须含：`no anachronistic costumes from other dynasties (Qing, Republican China, modern streetwear)`（按项目时代改写）。
4. 龙套默认：中远景、侧背、虚化；除非分镜明确要求，禁止无参考路人英雄特写。

**为什么**：无参考时模型会「乱串朝代服装库」。文字时代锁 + 避免特写，是目前不补图前提下唯一可靠约束。

### 角色增减（修订）

- 完全不在画内且站位未提及 → 不引
- 在场（含局部/背景/被点名）→ **必须引**
- 已离场 → 后续可不引
- 新登场 → 从该任务起引角色参考锁脸；空间连续靠前序输出

---

## 4. 单帧画布铁律（禁多宫格 / 禁烧字幕）

> 目标产物：**一张填满画布的电影单帧**。不是分镜板、不是四宫格、不是带字幕条的宣传图。

| 禁止 | 说明 |
|------|------|
| multi-panel / grid / 2×2 / comic / collage / contact sheet / split-screen | 任一即失败 |
| 画面内字幕/台词条/caption/lower-third/title card | 台词只存在于音频与剧本，不烧进图 |
| 镜头号角标、水印、LOGO、UI 边框 | 参考帧保持干净 |
| prompt 含 `storyboard`、`frame N of M`、序列节拍总览 | 已验证会诱发宫格 |

- OPENING 负责单帧画布声明；TEXT POLICY 负责烧字/字幕策略；AVOID 保留末尾必要禁令。三段不得复制同一长串禁词；字幕禁令只在 TEXT POLICY 中表达。
- 风格文件 `avoid` 已含对应条目，但**任务 prompt 仍须显式重复**最小明确约束，不能只靠风格文件。

---

## 5. 风格匹配

从通用设定的 `风格` / `风格质感` 字段提取关键词，匹配风格参考文件（**两模式共用此表，唯一一份**）：

| 类别 | 风格名 | 关键词 | 参考文件 |
|------|--------|--------|---------|
| 真人/实拍 | LiveAction | 真人实拍、真人摄影、照片级真实、live-action、historical drama、电影级质感、真人影视剧 | `references/styles/LiveAction.md` |
| 2D 动画 | InkAnimation | 水墨、水墨风、水墨动画、国画、ink-wash、Chinese ink painting、水墨风人物动画 | `references/styles/InkAnimation.md` |
| 2D 动画 | Anime2D | 日系动漫、二次元、anime、新海诚、京阿尼、吉卜力2D、番剧、日漫、Japanese animation、cel animation | `references/styles/Anime2D.md` |
| 2D 动画 | Western2D | 欧美卡通、美式动画、Cartoon Network、Adventure Time、Rick and Morty、Western cartoon、2D cartoon、flat cartoon、卡通网络 | `references/styles/Western2D.md` |
| 2D 动画 | FlatIllustration | 扁平插画、矢量插画、flat design、vector illustration、UI插画、极简插画、flat art、minimalist illustration | `references/styles/FlatIllustration.md` |
| 3D CGI | 3DCartoon | 3D卡通、皮克斯、迪士尼、Pixar、Disney、3D动画、3D拟人化、3D喜剧 | `references/styles/3DCartoon.md` |
| 3D CGI | Realistic3DCGI | 写实3D、电影特效、CGI、realistic 3D、VFX、photoreal CGI、3D写实、电影级3D、3D特效 | `references/styles/Realistic3DCGI.md` |
| 3D CGI | Stylized3DCGI | 风格化3D、蜘蛛侠平行宇宙、Spider-Verse、3D混合2D、hybrid 3D、stylized CGI、美漫风3D、3D漫画风 | `references/styles/Stylized3DCGI.md` |
| 3D CGI | GameCinematic | 游戏CG、游戏过场、最终幻想、GTA、Rockstar、FF、game cinematic、game cutscene、游戏预告片、3A游戏、AAA game | `references/styles/GameCinematic.md` |

> 无明确匹配时默认使用 `LiveAction.md`。

**风格区分指南**：LiveAction=真人实拍，Realistic3DCGI=照片级 3D 渲染，GameCinematic=游戏过场美感；3DCartoon=皮克斯式卡通 3D，Stylized3DCGI=混合 2D 漫画元素（蜘蛛侠平行宇宙）；InkAnimation=水墨晕染留白，Anime2D=日系赛璐璐，Western2D=欧美粗描边夸张造型，FlatIllustration=矢量扁平。

匹配后读取风格参考文件的 front-matter，提取以下参数用于 prompt 构建：

| 参数 | 注入段落 |
|------|---------|
| `production_type` | OPENING DECLARATION |
| `neg_1` / `neg_2` / `neg_3` | OPENING DECLARATION |
| `style_anchor` | CINEMATIC QUALITY 段头部 |
| `style_footer` | CINEMATIC QUALITY 段尾部 |
| `camera_language` | CINEMATIC QUALITY 段（摄影原则子段） |
| `quality` | CINEMATIC QUALITY 段（画质要求子段） |
| `avoid` | AVOID 段 |

---

## 6. 文字元素检测

Agent 扫描当前任务对应的分镜内容，检测画面中可能出现的文字元素：

| 扫描字段 | 关注信号 |
|---------|---------|
| `场景描述` | 招牌、门匾、墙面文字、屏幕界面 |
| `站位/调度` | 角色走向写有文字的物体 |
| 道具设定 | 会员牌、书信、票据、包装、容器标签 |
| `台词` | 角色在阅读/书写时，台词内容需出现在画面中 |

检测到文字后，按三层分类法处理：

| 类型 | 判定条件 | 处理方式 |
|------|---------|---------|
| **A：必须准确的文字** | 招牌、品牌名、票据、书信、手机界面、产品包装 | 显式指定中文字符，要求准确呈现 |
| **B：装饰性文字** | 远处店铺招牌、背景书法、环境文字 | 不指定内容，仅描述质感和时代感 |
| **C：道具文字** | 会员牌、木牌、容器标签 | 按剧情重要性分级：决定剧情则保留，纯视觉元素则仅生成材质 |

> **关键风险**：模型常将中文字符替换为拼音或拉丁字母（如"春生"→"chunsheng"）。类型 A 和类型 C（重要道具文字）必须显式约束 `Do not replace Chinese characters with Latin letters or pinyin.`

未检测到特定文字元素时，TEXT POLICY 段仍保留默认策略（防止模型自行生成假汉字/拼音），仅省略精确文字内容。

---

## 7. 提示词净化规范（元约束净化 · 硬规则）

> 所有最终写入 `prompt` 字段、提交给生图模型的文本必须为**纯画面描述语言**。
> 凡是"本应属于智能体编写规范、而非最终发送给生图模型的内容"（元约束/元语言）一律禁止出现在 prompt 中——它们会稀释画面描述权重、降低生成质量（EP11 实测：删除此类内容后生成质量正常）。
> 净化在**组装 prompt 时**由编写 Agent 完成；文档中的编写指引、注释、校验说明是给 Agent 阅读的材料，**不属于** prompt 内容。

**必删 11 类（prompt 中出现即违规，两模式同一套规则）**：

| # | 类别 | 示例 | 处理 |
|---|------|------|------|
| 1 | 段落放置/编排指令 | `write this block after...`、`in cast/images order` | 删除整句，保留其后的实质约束 |
| 2 | Decision rule 决策说明 | `Decision rule: facial identity ... take priority over...` | 删除（已由身份锁语义覆盖） |
| 3 | 括号标签机制解释 | `...are binding content labels, not casting instructions` | 删除 |
| 4 | 编写者脑补禁令 | `Do not let the role labels ... infer new faces...` | 删除（编写环节约束，模型不接收） |
| 5 | 编译器/流水线说明 | `The prompt compiler...`、`Source fidelity rule:` 整块 | 删除 |
| 6 | 中文事实保留指令 | `Keep Chinese character names... in Chinese...` | 删除（风险在编写环节控制） |
| 7 | 占位符机制解释 | `The PREV_OUTPUT placeholder — ... serves as...` | 删除；仅保留 `Image N: Previous Phase/Frame Anchor` 标签及使用语义 |
| 8 | 锚点职责定位从句 | `This is a visual anchor frame for {场景名} — a single establishing image that locks...` | 保留定位句，删职责从句 |
| 9 | 锚点职责块 | `Anchor frame responsibilities:` 整块 | 删除 |
| 10 | Mapping 内机制解释 | `The Chinese role name describes duty and source content only.` | 删除；可保留具体绑定内容 |
| 11 | 道具配对说明括号 | `same props (每个道具必须匹配对应参考图；...)` | 仅保留 `same props` |

**必须保留（禁止因净化误删）**：全部画面描述；身份锁短语与逐角色身份锁句（锚点模式：`Reference priority`、`identity wins every conflict`、`actor continuity`、`recognizable as the same actor/person`、`sole identity source`、`face identity has absolute priority`、`Do not alter facial identity/structure/skin features/body proportions`、`modify only wardrobe, hairstyle, and setting`）；`Image N:` 标签与优先级语义（校验器按此计数）；Previous Phase/Frame Anchor 使用语义；单帧声明（`exactly one image` / `single frame only` / `fills the entire canvas`）；TEXT POLICY 禁字幕块、AVOID 负面清单、背景人物降权句；场景名（保留在定位句内）。

---

## 8. Prompt 七段框架（公共规则）

两种模式的 prompt 均由以下 **7 段**按固定顺序组成，每个任务一个独立 prompt：

```
┌─ 1. OPENING DECLARATION（锚点模式第一行先写 IDENTITY LOCK）
├─ 2. SCENE CONTINUITY
├─ 3. REFERENCE IMAGE MAPPING
├─ 4. FRAME DETAIL
├─ 5. TEXT POLICY
├─ 6. CINEMATIC QUALITY
└─ 7. AVOID
```

**公共硬规则**（语言分工与各段完整模板见模式专属文档）：

- **禁用 "storyboard" 一词**：图像模型将这个词理解为多格分镜板布局，即使有单帧指令也会生成宫格图。使用 "cinematic film frame" 替代
- **禁止声明帧数**：不写 "frame 1 of 3" 等总帧数表述（会诱发多帧宫格）；仅声明当前任务是首任务还是后续任务
- **禁止序列描述**：不包含组叙事概述或序列节拍（如 "establishing → action → reveal"）——会让模型在单帧中呈现整个序列
- **REFERENCE IMAGE MAPPING**：为 `images` 数组每张图写一个映射块，顺序与数组严格一致，`Image {N}:` 从 1 连续递增；映射块数量 = images 长度（含前序输出占位）；Character Identity Anchor 数 = 角色图数 = `cast` 长度，不得合并或省略
- **FRAME DETAIL 必含 Purpose 与 Feeling**：Purpose 回答"这个画面为什么存在"，Feeling 回答"观众应感受到什么"，互补且缺一不可
- **禁止焦距参数**：不写 35mm / 50mm / 85mm 等焦距数值，仅保留景别和角度
- **多角色场景**：一帧/一锚中 2 个及以上角色时，Action 与 Performance 段**必须为每个角色分别描述**，遗漏会导致该角色无动作或表情僵硬
- **叙事句式允许**：Action/Performance 可用自然叙事句式，但仅限复述原分镜内容，禁止二次创作
- **反二次创作约束（编写环节）**：禁止添加分镜中不存在的视觉元素、禁止在翻译时重写角色外貌——这些是编写规范，不是 prompt 内容（原 `Source fidelity rule` 段已从模板移除，不得写回）
- **编译器铁律**：Prompt 编译器的职责是组装控制语言与源内容（锚点模式）或将分镜内容**翻译**为英文描述（分镜图模式），**不是编剧，也不是翻译重写器**。仅复述原分镜已有的视觉信息，禁止新增道具、时间、动作、情绪事件、光线条件或场景

### 景别转换表

| 中文 | 英文电影语义 |
|------|------------|
| 大全景 | extreme wide shot |
| 全景 | wide shot / establishing shot |
| 中景 | medium shot |
| 近景 | medium close-up |
| 特写 | close-up |
| 大特写 | extreme close-up |

### 运镜转换表

| 中文 | 英文电影语义 |
|------|------------|
| 固定 | static camera, locked-off |
| 缓慢推镜头 | slow push-in |
| 快速推镜头 | fast push-in |
| 缓慢拉镜头 | slow pull-out |
| 横摇 | pan / horizontal sweep |
| 竖摇 | tilt |
| 跟拍 | tracking shot |
| 环绕 | orbit shot |
| 手持 | handheld |
| 升降 | crane shot |

### 角度转换表

| 中文 | 英文电影语义 |
|------|------------|
| 平视 | eye-level |
| 微仰视 | low angle |
| 微俯视 | high angle |
| 俯视 | top-down / bird's eye view |
| 仰视 | extreme low angle |

### TEXT POLICY 模板（两模式逐字共用；占位符语言随模式）

**常驻段**——无论是否检测到文字元素始终存在：

```
TEXT POLICY:

Hard ban on burned-in graphics (non-negotiable):
- No subtitles, captions, lower-thirds, or title cards
- No on-screen dialogue text or lyric text
- No watermarks, logos, shot numbers, timecode, or UI chrome
- Spoken lines exist only as audio in the final edit — never as text painted onto this frame

Diegetic in-world text only (shop signs, book pages, packaging) when the scene itself contains them:
- Preserve original Chinese characters
- Do not translate into English
- Do not generate pinyin
- Do not replace Chinese characters with Latin letters

If exact typography cannot be guaranteed, preserve material and visual shape only.
Leave all editorial text for post-production.
```

**类型 A — 必须准确出现的文字**（默认策略后追加）：

```
Required readable text: "{Chinese text content}"
Prioritize accurate Chinese typography.
```

**类型 B — 装饰性文字**：

```
Decorative text: traditional Chinese handwritten signs, unreadable but authentic.
Do not specify exact text content.
```

**类型 C — 道具文字**（文字决定剧情时 / 仅为视觉元素时）：

```
Prop text — {prop_name}:
Exact text: "{Chinese text content}"
Do not replace Chinese characters with English letters or pinyin.
```

```
Prop text — {prop_name}:
Generate material texture only. Do not render readable characters.
```

> 多种类型同时存在时，在同一个 TEXT POLICY 段内分列，共享默认策略头部。`{prop_name}` 在锚点模式用中文名、分镜图模式用英文名。

### CINEMATIC QUALITY 骨架（两模式共用）

```
CINEMATIC QUALITY:

{style_anchor}

{全局氛围基调 / 全局色彩调性 / 全局光线基调}

{style_footer}

Camera principles:
{camera_language}

{quality}
```

> 中间三行的语言随模式：锚点模式不在此段翻译内容事实（中文内容留在前面内容段）；分镜图模式将通用设定的中文描述转为英文电影语义。
>
> **关键词精简原则**：避免在 quality 中反复堆砌 cinematic / film / professional / realistic 等词。模型已通过 `production_type` 和 `style_anchor` 理解风格基调，重复关键词会稀释注意力。

### AVOID 公共规则

- 从风格参考文件 front-matter 提取 `avoid`，放在 prompt **末尾**
- 不要把长篇负面清单放在身份锁/画布声明前，不要在 AVOID 重复身份锁；字幕/烧字禁令由 TEXT POLICY 负责
- 具体保留策略随模式：锚点模式去重后只保留单帧布局、时代、背景人物权重与空洞姿态必要项（完整模板见 phase-2-visual-anchors.md）；分镜图模式完整注入并追加分镜专用禁令（完整模板见 phase-2-storyboard-images.md）

---

## 9. 任务表 JSON 公共字段

两种模式任务表共用以下字段语义（模式专属字段如 `shot_range`/`scene_name`/`group` 的取值规则见各自文档）：

| 字段 | 必填 | 说明 |
|------|------|------|
| `mode` | 是 | 固定 `"sequential"`；缺省或 `batch` 视为错误 |
| `model` | 是 | 固定 `"nano-banana-2"` |
| `output_path` | 是 | 输出目录 |
| `tasks[].id` | 是 | 任务唯一标识（命名规则随模式） |
| `tasks[].scene` | 是 | **物理场**号字符串。同场 = 同连续物理空间 |
| `tasks[].depends_on` | 首任务省略 | 必须指向**同场播放顺序上的直接前一任务** id；跨场禁止 |
| `tasks[].filename` | 是 | 输出文件名（命名规则随模式） |
| `tasks[].cast` | 是* | 在场具名角色中文名列表（*纯空镜可为 `[]`）；顺序=角色参考顺序 |
| `tasks[].prompt` | 是 | 七段单帧 prompt（含单帧画布声明、禁字幕 TEXT POLICY） |
| `tasks[].aspectRatio` | 是 | 固定 `"16:9"` |
| `tasks[].imageSize` | 是 | `"2K"` |
| `tasks[].images` | 是 | 见排序规则；非首任务必须含 `"{{PREV_OUTPUT}}"` 且位于全部角色之后、风格之前 |

### sequential 链公共规则

1. 按 `scene` 分组；同场全部任务（跨组）按播放顺序形成**一条** `depends_on` 链
2. 每场排序后第 1 个任务：无 `depends_on`，无 `{{PREV_OUTPUT}}`
3. 第 2..N 个任务：`depends_on` = 排序后前一任务 id，且 `images` 含 `{{PREV_OUTPUT}}`
4. 跨组不断链（分镜图模式）；跨阶段串行（锚点模式）
5. 不同 `scene` 之间禁止 `depends_on`；场间可并行
6. 有 `depends_on` ⇔ `images` 含 `{{PREV_OUTPUT}}`（双向一致）

**禁止**：省略 `depends_on`、同场并行提交多任务、同场断链、跨物理场串 `depends_on`、用静态资产冒充前序输出。

---

## 10. Step 3/4：执行生成与校验（公共流程）

1. **校验**：`python .opencode/skills/storyboard-generator/scripts/validate_task_table.py --check 任务表.json --mode {anchor|storyboard}`（`--mode auto` 默认按任务是否含 `shot_range`/`scene_name` 自动识别；显式指定防两套规则互窜）。校验器末尾输出一行式摘要 `[SUMMARY] type=… | tasks=N | scenes=M | errors=E | warnings=W | result=PASS/FAIL`，会话无需回读全量报告。**错误阻塞**（结构/模型/比例/mode、必填字段、链完整性、映射块一致、必需段落与 Purpose/Feeling、禁词、cast 匹配、单帧声明、禁字幕、AVOID、锚点身份锁）；**告警不阻塞但须修正重提**（元约束残留）
2. **路径解析**：`images` 相对路径在调用 MCP tool 前必须解析为绝对路径；URL 原样传递
3. **执行（加载 art-director，sequential，不可降级为 batch）**：场间并行（不同 `scene` 首任务可交叉提交）；场内串行（前一任务 `completed` 且拿到 `image_url` 后，字面替换下一任务 `{{PREV_OUTPUT}}` 为该 URL 再提交）；失败处理随模式（锚点：记录事件继续其他场；分镜图：停止该场后续链）
4. **下载**：每帧下载到 `output_path`，文件名与 `filename` 一致，供人工验收链连续性

> 详细策略见 art-director「执行模式 > 模式二：sequential」；模式专属执行要点与校验项清单见各自文档末尾。

### 质量四条铁律（两模式通用，提交前自检）

| # | 缺陷 | 规范堵点 | 校验堵点 |
|---|------|----------|----------|
| 1 | 无参考龙套朝代漂移 | 龙套时代锚定 + 具名无图硬终止 | 文字质量无法静态全检；具名无图靠 Agent 硬终止 |
| 2 | 在场角色漏引参考 | 出场定义 + 在场表 + `cast` | `cast`↔角色路径↔Anchor 数量 |
| 3 | 多宫格/2×2 | OPENING 单帧声明 + AVOID + 风格 avoid | 宫格词/缺单帧声明失败 |
| 4 | 烧字幕 | TEXT POLICY 硬禁 + AVOID | 缺禁字幕块失败 |
