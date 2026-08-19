# 阶段二：episode_storyboard_images — 分镜图绘制

**独立阶段（仅当 `meta_query(scope=config)` 返回的 `config.reference_image_mode=storyboard_images` 时执行）**：此阶段在 `episode_storyboard_script`、`episode_character_ref`、`episode_prop_ref`、`episode_scene_ref` 之后执行，分镜图可参考剧集级场景/道具变化。`reference_image_mode=visual_anchor`（默认）时跳过此阶段，改为执行视觉锚点图绘制（见 `phase-2-visual-anchors.md`）；`reference_image_mode=none` 时跳过所有参考图生成，video-director 将以角色/场景参考图为主要参考素材。

> **独立 Agent session 执行**：本文档的所有工作必须在 fresh context 中完成。不得继承阶段一（分镜脚本创作）的对话上下文——阶段一的多轮创作思考会稀释对 prompt 模板格式的注意力。Agent 仅从磁盘读取：组{N}.json/md、参考图目录；配置（`reference_image_mode` 等）经 `meta_query(scope=config)` 读取。
>
> **两种模式均支持分镜图绘制**。详细模式从 `组{N}.json` 读取，精简模式从 `组{N}.md` 读取。
>
> **生成方式：参考帧模式（Reference-Frame Sequential）** — 唯一合法模式。
>
> 目标不是「每帧独立出图」，而是：**场内每一帧的成图，成为下一帧的主空间连续参考（参考帧）**，使同物理空间内角色身份、布景几何、光影方向、服装发式在整条链上可继承。
>
> | 规则 | 说明 |
> |------|------|
> | mode | 必须 `"sequential"`，禁止 batch / 省略 mode |
> | 场 | = 物理空间连续单元（与分镜脚本 `场号` 一致） |
> | 场内 | 全部帧（跨组）按播放顺序形成**一条** `depends_on` 链；非首帧 `images` 含 `{{PREV_OUTPUT}}` |
> | 执行 | 前帧 `completed` 拿到 `image_url` → 替换下一帧 `{{PREV_OUTPUT}}` → 再 submit |
> | 场间 | 不同 `scene` 无依赖，首帧可并行 |
>
> **禁止**：同场多帧并行提交、断链（中间帧无 depends_on）、跨物理场串 depends_on、任务表无 id/scene/group、用静态资产冒充前帧。
>
> **目标模型**：`nano-banana-2`，2K 分辨率。画面比例固定 `16:9`。Prompt 使用**英文**生成。

---

## Step 1：收集参考图清单

分镜图绘制前，**Agent 须列出各参考图目录下的具体文件**，供 Step 2 逐帧引用。

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

**Agent 执行**：用 LS 工具列出上述目录中的 `.png` 文件，记录完整路径。

---

## 参考图排序优先级（参考帧模式）

`images` 数组顺序决定模型注意力权重。参考帧模式采用：

1. **角色参考图**（身份锁）— **每个出场角色一张**，按戏剧重要性排序
2. **前帧输出**（空间连续主锚，仅非首帧）— `{{PREV_OUTPUT}}`，紧接角色之后  
   - 职责：布景几何、光影方向、服装发式连续性、人物空间关系的演化起点  
   - **不是**要求复制上一帧构图；景别/机位以 FRAME DETAIL 为准
3. **场景参考图**（环境细节）— 通常一张（本场物理空间的设定图）
4. **道具参考图** — 每个重要道具一张
5. **风格参考图** — 一张，始终在最后（静态资产侧）

> **首帧**（无前帧）：角色 → 场景 → 道具 → 风格  
> **后续帧**：角色 → `{{PREV_OUTPUT}}` → 场景 → 道具 → 风格  
> **多角色示例（后续帧）**：掌柜 → 茶客 → 小二 → `{{PREV_OUTPUT}}` → 茶馆场景 → 道具… → 风格

**硬约束**：
- 角色参考必须在前帧与风格之前（锁脸优先于锁构图）
- `{{PREV_OUTPUT}}` 必须在风格参考之前（连续参考权重大于风格采样）
- 禁止把 `{{PREV_OUTPUT}}` 省略或放到与 depends_on 不一致的位置
- **禁止**把 `{{PREV_OUTPUT}}` 放在风格参考之后（EP06 旧病：PREV 垫底 → 锁脸失效）

---

## 出场角色引用铁律（EP06 组1 根因闭环）

> **根因**：旧规则写「按需引用 / 未登场不引」，Agent 常只给**焦点角色**挂参考图。  
> 例：组1镜1 只露掌柜执笔手（无正脸）→ 镜2 焦点切到小二、画面仍有掌柜 → 任务只引小二、不引掌柜 → 掌柜造型漂移。  
> 分镜图要的是**可用的单帧参考**，不是「只锁说话的人」。

### 何谓「本帧出场」（必须挂参考）

扫描该镜的 `场景描述`、`站位/调度`、`表演/微表情`、`台词` 后，下列任一成立即算出场：

| 信号 | 示例 | 是否必须 `images` 含其角色参考 |
|------|------|-------------------------------|
| 正脸/侧脸可见 | 「抬眼望小二」 | 是 |
| 身体/半身/背影可见 | 「立于柜台后」 | 是 |
| 仅手/脚/局部入画 | 「执笔手从画右入画」 | **是**（局部也要锁身份与服装） |
| 站位里被点名在场 | 「小二立于掌柜右侧」「眼神看向掌柜」 | **双方都要引** |
| 台词归属角色 | `掌柜："…"` | 若该角同时在画面内则必须引 |
| 纯画外音、完全不在画内 | 画外 trans 音 | 否 |

**禁止**：只按「本镜焦点/说话人」引参考；禁止因「上镜只露手/背影」而省略角色参考。

### 组内在场角色连续引用

1. 编写任务表前，先为**每一组**列出 `组在场表`：本组所有镜中曾出场的、且目录中有参考图的具名角色。
2. 对每一帧：取「本帧出场集合」= 上表扫描结果。
3. 本帧出场集合中**每一个**有参考图的角色，都必须进入该 task 的 `images`（角色段）+ `cast` 字段 + Character Identity Anchor。
4. 镜1 未露脸、镜2 仍在场 → 镜2 **仍须**引用该角色参考（前帧不能代替角色锁；前帧可能根本没拍到脸）。
5. 仅当该角已明确离场（出画且站位不再提及）才可从后续帧去掉其参考。

### `cast` 字段（任务表必填）

每个 task 增加：

```json
"cast": ["掌柜", "小二"]
```

- 中文名，与角色参考图文件名可匹配（文件名含该名，如 `掌柜_默认妆造.png`）
- `cast` 顺序 = `images` 中角色参考顺序 = REFERENCE IMAGE MAPPING 中 Character Identity Anchor 顺序
- 校验器会核对：`cast` 非空（有人在场时）、每个名字能在 `images` 角色路径中找到、Character Anchor 数量 = 角色图数量

### 无参考图龙套 / 路人（造型漂移与朝代错位闭环）

| 角色类型 | 有无参考图 | 处理 |
|----------|------------|------|
| 具名角色（掌柜/小二/赵胖等） | 有 | 必须引参考；禁止纯文字开脸 |
| 具名角色 | **无** | **硬终止**：不得开写该帧任务；回报 orchestrator 补角色参考或改分镜去掉该角具名出场 |
| 无名龙套/路人（茶客甲、街人） | 通常无 | 允许无图，但必须 **时代锚定描述**；禁止抢戏、禁止特写正脸当主角 |
| 群演占画面主体且无一人有参考 | — | 优先改调度（虚化/背影/远景）；仍不够则硬终止补「群演氛围参考」或具名化+出参考图 |

**时代锚定（无图龙套强制）**：

1. 从 `全局依赖/全局设定.md` 读取时代（如「唐朝/盛唐」），写入 SCENE CONTINUITY 的 `{period_description}` 与 FRAME DETAIL。
2. 每个无图龙套在 FRAME DETAIL / 必要时在 REFERENCE 段用文字写死：`{period} civilian / shop guest` + 服化关键词（唐：圆领袍/襦裙/幞头等；**禁止**清辫、民国长衫、现代T恤等错代）。
3. AVOID 与 SCENE CONTINUITY 必须含：`no anachronistic costumes from other dynasties (Qing, Republican China, modern streetwear)`（按项目时代改写）。
4. 龙套默认：中远景、侧背、虚化；除非分镜明确要求，禁止无参考路人英雄特写。

**为什么**：无参考时模型会「乱串朝代服装库」。文字时代锁 + 避免特写，是目前不补图前提下唯一可靠约束。

---

## 单帧画布铁律（禁多宫格 / 禁烧字幕）

> 目标产物：**一张填满画布的电影单帧**，供后续分镜/视频参考。不是分镜板、不是四宫格、不是带字幕条的宣传图。

| 禁止 | 说明 |
|------|------|
| multi-panel / grid / 2×2 / comic / collage / contact sheet / split-screen | 任一即失败 |
| 画面内字幕/台词条/caption/lower-third/title card | 台词只存在于音频与剧本，不烧进图 |
| 镜头号角标、水印、LOGO、UI 边框 | 参考帧保持干净 |
| prompt 含 `storyboard`、`frame N of M`、序列节拍总览 | 已验证会诱发宫格 |

OPENING / AVOID / TEXT POLICY 三处必须同时写明单帧与禁字幕（见下文模板）。风格文件 `avoid` 已含对应条目；**任务 prompt 仍须显式重复**，不能只靠风格文件。

---

## Step 2：Agent 直接编写任务表 JSON

Agent 使用 Write 工具直接编写 `分镜图_任务表.json`，保存到 `project/{项目名}/{剧集号}/分镜/分镜图_任务表.json`。

### 2.1 读取分镜内容

读取 `{剧集号}/分镜/分组/` 目录下的组文件：
- **详细模式**：`组{N}.json` — 从 `场号`、`场名称` 获取场信息，从 `组叙事概述`、`通用设定`、`镜头列表` 获取组信息
- **精简模式**：`组{N}.md` — 从正文获取叙事概述和分镜描述（一段一镜）

> **场号 = 物理空间串行链 ID**：从组文件读取 `场号` → 写入任务 `scene`。同一物理场的全部组全部帧必须连成**一条** depends_on 链（组1最后一镜 → 组2第一镜）。若发现分镜脚本把同一物理空间拆成多个场号，应在编写任务表前向 orchestrator 回报，而不是默默按错误场号断链。

### 2.2 风格匹配

从通用设定的 `风格` / `风格质感` 字段提取关键词，匹配风格参考文件：

#### 真人/实拍类

| 风格名 | 关键词 | 参考文件 |
|--------|--------|---------|
| LiveAction | 真人实拍、真人摄影、照片级真实、live-action、historical drama、电影级质感、真人影视剧 | `references/styles/LiveAction.md` |

#### 2D 动画类

| 风格名 | 关键词 | 参考文件 |
|--------|--------|---------|
| InkAnimation | 水墨、水墨风、水墨动画、国画、ink-wash、Chinese ink painting、水墨风人物动画 | `references/styles/InkAnimation.md` |
| Anime2D | 日系动漫、二次元、anime、新海诚、京阿尼、吉卜力2D、番剧、日漫、Japanese animation、cel animation | `references/styles/Anime2D.md` |
| Western2D | 欧美卡通、美式动画、Cartoon Network、Adventure Time、Rick and Morty、Western cartoon、2D cartoon、flat cartoon、卡通网络 | `references/styles/Western2D.md` |
| FlatIllustration | 扁平插画、矢量插画、flat design、vector illustration、UI插画、极简插画、flat art、minimalist illustration | `references/styles/FlatIllustration.md` |

#### 3D CGI 类

| 风格名 | 关键词 | 参考文件 |
|--------|--------|---------|
| 3DCartoon | 3D卡通、皮克斯、迪士尼、Pixar、Disney、3D动画、3D拟人化、3D喜剧 | `references/styles/3DCartoon.md` |
| Realistic3DCGI | 写实3D、电影特效、CGI、realistic 3D、VFX、photoreal CGI、3D写实、电影级3D、3D特效 | `references/styles/Realistic3DCGI.md` |
| Stylized3DCGI | 风格化3D、蜘蛛侠平行宇宙、Spider-Verse、3D混合2D、hybrid 3D、stylized CGI、美漫风3D、3D漫画风 | `references/styles/Stylized3DCGI.md` |
| GameCinematic | 游戏CG、游戏过场、最终幻想、GTA、Rockstar、FF、game cinematic、game cutscene、游戏预告片、3A游戏、AAA game | `references/styles/GameCinematic.md` |

> 无明确匹配时默认使用 `LiveAction.md`。

#### 风格区分指南

| 对比 | 区别 |
|------|------|
| LiveAction vs Realistic3DCGI | LiveAction 是真人演员实拍；Realistic3DCGI 是 3D 渲染达到照片级真实 |
| 3DCartoon vs Realistic3DCGI | 3DCartoon 是皮克斯风格化 3D（角色夸张卡通化）；Realistic3DCGI 追求照片级真实感 |
| 3DCartoon vs Stylized3DCGI | 3DCartoon 是标准风格化 3D 动画；Stylized3DCGI 混合 2D 漫画元素（如蜘蛛侠平行宇宙） |
| InkAnimation vs Anime2D | InkAnimation 是中国水墨动画（笔墨晕染、留白）；Anime2D 是日系赛璐璐动画（干净线条、扁平色彩） |
| Anime2D vs Western2D | Anime2D 是日系动漫（赛璐璐、细腻表情）；Western2D 是欧美卡通（粗描边、夸张造型） |
| GameCinematic vs Realistic3DCGI | GameCinematic 偏游戏过场风格（含后处理美感）；Realistic3DCGI 偏电影 VFX 级写实 |

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

### 2.3 文字元素检测

Agent 扫描**当前帧**对应的分镜内容，检测画面中可能出现的文字元素。扫描范围：

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

### 2.4 构建 Prompt

Prompt 使用**英文**生成，由以下 **7 段**按固定顺序组成。每帧一个独立的 prompt，生成一张图。

> **编译器铁律**：Prompt 编译器的职责是将分镜内容**翻译**为图像模型可理解的英文描述，**不是编剧**。禁止新增原分镜中不存在的道具、时间、动作、情绪事件、光线条件或场景。仅复述和翻译原分镜已有的视觉信息。违反此规则的 prompt 会导致模型生成与分镜不一致的画面。

### 提示词净化规范（元约束净化 · 硬规则）

> 所有最终写入 `prompt` 字段、提交给生图模型的文本必须为**纯画面描述语言**。
> 凡是"本应属于智能体编写规范、而非最终发送给生图模型的内容"（元约束/元语言）禁止出现在 prompt 中——它们会稀释画面权重、降低生成质量（EP11 实测：删除后生成质量正常）。
> 净化在**组装 prompt 时**由编写 Agent 完成；文档中的编写指引/注释/校验说明是给 Agent 阅读的材料，**不属于** prompt 内容。
> 完整 11 类必删项与保留项清单见 `phase-2-visual-anchors.md`「提示词净化规范」节（两种模式同一套规则）。本模式（英文 prompt）的典型残留与处理：

| # | 类别 | 示例（本模式原文） | 处理 |
|---|------|-------------------|------|
| 1 | 段落放置/编排指令 | `write this block after the heading and before any SCENE...`、`in cast/images order` | 删除整句，保留其后的实质约束 |
| 2 | Decision rule 决策说明 | `Decision rule: facial identity and actor continuity take priority over...` | 删除（已由身份锁覆盖） |
| 5 | 编译器/流水线说明 | `The prompt compiler translates, does not embellish.`、`Source fidelity rule:` 整块 | 删除 |
| 6 | 中文事实保留指令 | `Keep Chinese character names... in Chinese. Do not translate or rewrite them.` | 删除（翻译/改写风险在编写环节） |
| 7 | 占位符机制解释 | `The PREV_OUTPUT placeholder — ...`、`The immediately preceding frame ... (may be prior group)` | 删除机制解释；仅保留 `Image N: Previous Frame Anchor — PRIMARY SPATIAL CONTINUITY REFERENCE` 及其使用语义 |
| 8 | 锚点职责定位从句 | `This is a visual anchor frame for {场景名} — a single establishing image that locks the scene's spatial layout...` | 保留 `This is a visual anchor frame for {场景名}.`，删职责从句 |
| 9 | 锚点职责块 | `Anchor frame responsibilities:` 整块 | 删除 |
| 10 | Mapping 内机制解释 | `The Chinese role name describes duty and source content only.` | 删除 |
| 11 | 道具配对说明括号 | `same props (every prop must match its reference image)` | 仅保留 `same props` |

**必须保留（禁止因净化误删）**：全部画面描述、`Image N:` 标签与 Anchor 语义、单帧声明（`exactly one image` / `fills the entire canvas`）、TEXT POLICY 禁字幕块、AVOID 负面清单、`{{PREV_OUTPUT}}` 对应的 Previous Frame Anchor 使用语义（锁身份/布景/光影、按 FRAME DETAIL 演化，不得忽略参考帧重抽）。

```
┌─ 1. OPENING DECLARATION
├─ 2. SCENE CONTINUITY
├─ 3. REFERENCE IMAGE MAPPING
├─ 4. FRAME DETAIL
├─ 5. TEXT POLICY
├─ 6. CINEMATIC QUALITY
└─ 7. AVOID
```

---

#### 段落 1：OPENING DECLARATION

> **禁用 "storyboard" 一词**：生图 prompt 中严禁出现 "storyboard"。图像模型将这个词理解为多格分镜板布局，即使有单帧指令也会生成宫格图。使用 "cinematic film frame" 替代。

**首帧**：
```
Create a professional cinematic film frame for {film_context}.

This is the first frame of {group_name}.
Generate exactly one image for this single frame only.
One single photographic still that fills the entire canvas — not a multi-panel layout, not a grid, not a collage, not a comic strip, not a storyboard sheet, not a contact sheet, not a split-screen.
No borders or gutters dividing the image into tiles.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.
```

**后续帧**（有 `depends_on`，参考帧模式）：
```
Create a professional cinematic film frame for {film_context}.

This is a subsequent frame in the same continuous physical scene, directly following the previous frame.
The previous frame is provided as the PRIMARY spatial continuity reference (Previous Frame Anchor).
Evolve the shot from that reference; do not restart the scene from scratch.
Generate exactly one image for this single frame only.
One single photographic still that fills the entire canvas — not a multi-panel layout, not a grid, not a collage, not a comic strip, not a storyboard sheet, not a contact sheet, not a split-screen.
No borders or gutters dividing the image into tiles.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{film_context}` | 通用设定.风格 → 英文 | a historical drama film / a Chinese ink-wash animation film |
| `{group_name}` | 组名 → 英文 | Group 1 / Sequence A |
| `{production_type}` | 风格参考文件 | a live-action film pre-production cinematic frame |
| `{neg_1/2/3}` | 风格参考文件 | concept art / illustration / a fantasy painting |

> **禁止声明帧数**：不要在 prompt 中写 "frame 1 of 3" 或 "frame 2 of 4" 等包含总帧数的表述。这会导致模型生成多帧宫格图。仅声明当前帧是首帧还是后续帧。

---

#### 段落 2：SCENE CONTINUITY

**首帧**：
```
SCENE CONTINUITY:

This is the first frame of {group_name}.

Maintain strict continuity with reference materials:
- same character identities for ALL characters appearing in this frame (including non-focus and partially visible characters)
- same costume for each character
- same hairstyle for each character
- same {environment_description}
- same props
- same lighting atmosphere
- same {period_description}
- no anachronistic costumes from other eras or dynasties
```

**后续帧**（有 `depends_on`，参考帧模式）：
```
SCENE CONTINUITY (REFERENCE-FRAME MODE):

This frame continues the same physical scene as the Previous Frame Anchor.
Treat the previous frame as the live set: same room, same dressing, same bodies in space.

Inherit from the previous frame (mandatory):
- character facial identity and body proportions for EVERY returning character (including non-focus and partially visible)
- costume, fabric color, accessories, hairstyle
- environment geometry, architecture, furniture layout, materials
- lighting direction and color temperature (unless FRAME DETAIL specifies a motivated change)
- period and visual grade
- no anachronistic costumes from other eras or dynasties

Evolve from the previous frame (allowed / required when FRAME DETAIL says so):
- camera size and angle may change (wide → close-up, eye-level → low angle, etc.)
- character pose, gesture, eyeline, and blocking may advance one beat
- props may enter, leave, or change state if the shot description requires it

Do NOT:
- redesign faces, costumes, or the room from static refs alone while ignoring the previous frame
- copy the previous frame's exact composition when FRAME DETAIL requests a different shot
- teleport characters or reset spatial relationships without a motivated move
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{environment_description}` | 通用设定.场景名称 → 英文 | tea house interior / modern family living room |
| `{period_description}` | 项目时代背景 → 英文 | historical period / Tang Dynasty period / modern setting |

> **反二次创作约束（编写环节）**：禁止添加分镜中不存在的视觉元素、禁止在翻译时重写角色外貌——这些约束由编写 Agent 在组装 prompt 时执行，属于**编写规范**，不是 prompt 内容（见「提示词净化规范」；原 `Source fidelity rule` 段已从模板移除，不得再写回 prompt）。
>
> **禁止序列描述**：不要在 prompt 中包含组叙事概述或序列节拍（如 "establishing → action → reveal"）。这类描述会让模型尝试在单帧中呈现整个序列，导致宫格图生成。每帧的叙事上下文已由 FRAME DETAIL 段的 Purpose 字段充分提供。

---

#### 段落 3：REFERENCE IMAGE MAPPING

为 `images` 数组中的每张参考图写一个映射块，**顺序与数组严格一致**。每个映射块必须以 `Image {N}:` 开头，N 从 1 递增。使用 **Anchor 类型**明确告知模型每张参考图的用途。

> **全部使用英文名称**：映射块中的角色名、场景名、道具名必须翻译为英文（如"掌柜"→"Shopkeeper"、"茶馆"→"Tea House"）。Prompt 整体使用英文生成，中文名称会干扰模型理解。

> **多角色多道具是常态**：一帧中出场多个角色、使用多个道具是正常情况。**每个在场角色（含非焦点、局部入画、站位被点名）都必须有独立的 Character Identity Anchor 映射块**，每个重要道具都必须有独立的 Prop Detail Anchor 映射块。遗漏角色参考会导致该角色面目模糊、消失或换装换代。

**角色参考**（**每个 `cast` 成员一个映射块**，顺序与 `cast`/`images` 一致，主要角色在前）：
```
Image {N}: Character Identity Anchor
{character_name (English)} — {detailed English description: identity, clothing, hair, age, body type, and role in this frame; if only hands/back visible, still describe full identity from the reference sheet}.
Preserve: facial identity, appearance, costume, hair styling, age, body proportions.
Even if only a hand, shoulder, or back is visible in this frame, match the reference identity and costume exactly.
```

> **描述要具体**：不要只写 "The shopkeeper"，要写出可见的外观特征，让模型能精确关联参考图与角色。例如：性别、年龄段、服装款式与颜色、发型、体型；并写明本帧可见部位（full body / face / hands only）。
>
> **非焦点也要锚**：小二是说话焦点、掌柜在画内被注视 → 仍须 Shopkeeper + Waiter 两个 Anchor。
>
> **多角色示例**：一帧中有掌柜和茶客两个角色出场时，必须写两个映射块：
> ```
> Image 1: Character Identity Anchor
> Shopkeeper — A woman in her thirties, wearing a form-fitting Tang Dynasty ruqun in muted amber silk, hair in a high bun with a single jade pin, standing behind the counter.
> Preserve: facial identity, appearance, costume, hair styling, age, body proportions.
>
> Image 2: Character Identity Anchor
> Tea Guest — A male scholar in his forties, wearing a dark blue round-collared robe, a cloth cap, neatly trimmed beard, seated at the tea table with a relaxed posture.
> Preserve: facial identity, appearance, costume, hair styling, age, body proportions.
> ```

**场景参考**（通常一个，组内场景切换时可多个）：
```
Image {N}: Environment Anchor
{scene_name (English)} — {detailed English description: architecture, furniture, materials, and atmosphere}.
Preserve: architecture, spatial layout, materials, atmosphere.
```

**道具参考**（**每个重要道具一个映射块**，按剧情重要性排序）：
```
Image {N}: Prop Detail Anchor
{prop_name (English)} — {detailed English description: material, shape, texture, craftsmanship, and role in the scene}.
Preserve: shape, texture, craftsmanship, material.
```

> **描述要具体**：不要只写 "A tea canister"，要写出可见的材质和工艺特征。例如：材质、颜色、形状、表面纹理、工艺风格。
>
> **多道具示例**：一帧中出现茶罐和账簿两个道具时：
> ```
> Image 5: Prop Detail Anchor
> Tea Caddy — A round porcelain canister with celadon glaze, fitted lid, subtle crackle texture on the surface, resting on a wooden shelf.
> Preserve: shape, texture, craftsmanship, material.
>
> Image 6: Prop Detail Anchor
> Account Book — A hand-stitched ledger with a dark blue fabric cover, worn cotton thread binding, yellowed paper edges, resting open on the counter.
> Preserve: shape, texture, craftsmanship, material.
> ```

**风格参考**：
```
Image {N}: Visual Style Anchor
{brief English style description}.
Preserve: color palette, lighting mood, visual style.
```

**前帧参考**（仅非首帧，对应 `images` 中紧接角色之后的 `{{PREV_OUTPUT}}`）：
```
Image {N}: Previous Frame Anchor — PRIMARY SPATIAL CONTINUITY REFERENCE
Use as the live-set baseline for this shot:
- Match environment geometry, set dressing, and lighting direction to this frame
- Returning characters must look like the same people a moment later, not new castings
- Advance pose/blocking one beat toward the Action described in FRAME DETAIL
- Change framing only as FRAME DETAIL Composition/Camera feeling specify
Preserve: facial identity, costume, hair, room layout, light direction, period grade.
```

> **硬约束**：每个映射块的 `Image {N}:` 编号必须与 `images` 数组位置严格一一对应（Image 1 = images[0]，Image 2 = images[1]，...）。`{{PREV_OUTPUT}}` 在数组中占一个位置，对应一个 Previous Frame Anchor 映射块。编号不连续或顺序错乱将导致模型无法正确关联参考图。
>
> **角色映射块数量 = `images` 中角色参考图数量**：如果该帧有 3 个角色出场，`images` 数组中就有 3 张角色参考图，REFERENCE IMAGE MAPPING 段就有 3 个 Character Identity Anchor 映射块。不得合并或省略。

---

#### 段落 4：FRAME DETAIL

单帧描述。**必须包含 Purpose 和 Feeling 字段**——Purpose 告诉模型这个镜头为什么存在，Feeling 告诉模型这个镜头应该让观众感受到什么情绪：

```
FRAME DETAIL:

Purpose:
{镜头戏剧功能 → 英文，一句话说明此镜头存在的理由}

Feeling:
{情绪氛围 → 英文，一句话描述观众应感受到的情绪}
{如：A quiet moment before an important announcement.}

Scene:
{场景描述 + 站位/调度 → 英文叙事，仅复述原分镜内容}
{多角色场景须描述每个角色在画面中的位置关系}

Action:
{角色动作 → 英文叙事，可使用自然句式}
{多角色场景须分角色描述动作，格式：角色名: 动作描述}

Performance:
{表演/微表情 → 英文叙事，可使用自然句式}
{多角色场景须分角色描述表演，格式：角色名: 表演描述}

Composition:
{景别 + 摄影机角度 → 英文电影语义}

Camera feeling:
{摄影机运动 → 英文电影语义}

Lighting:
{光线 → 英文}

Atmosphere:
{帧级氛围 → 英文，可选，仅当该帧有特殊氛围需要强调时填写}
{如：A ritual-like reveal, important but grounded in everyday street life.}
```

> **Purpose 字段**回答"这个镜头为什么存在"（如"Establish the environment"/"Reveal character decision"/"Show reaction"）。**Feeling 字段**回答"观众应该感受到什么"（如"A quiet moment before an important announcement"/"A small business owner presenting a revolutionary new idea"）。两者互补，缺一不可。
>
> **禁止焦距参数**：不写入 35mm / 50mm / 85mm 等焦距数值。仅保留景别（wide shot / close-up 等）和角度（eye-level / low angle 等）。
>
> **叙事句式允许**：Action 和 Performance 段允许使用自然叙事句式（如 "She looks around the room, observing the customers before announcing her new idea."），不必拘泥于标签式短句。但仅限复述原分镜内容，禁止二次创作。
>
> **多角色场景编写指引**：当一帧中有 2 个及以上角色时，Action 和 Performance 段**必须为每个角色分别描述**。遗漏任一角色的动作/表演描述会导致该角色在画面中无动作或表情僵硬。
>
> **多角色 Action 示例**：
> ```
> Action:
> Shopkeeper: Arranging tea canisters on the shelf, then turns toward the entrance.
> Tea Guest: Seated at the tea table, lifting a tea cup to drink, pauses mid-sip.
> ```
>
> **多角色 Performance 示例**：
> ```
> Performance:
> Shopkeeper: Calm and focused expression, transitioning to mild curiosity.
> Tea Guest: Relaxed posture, slight surprise at the shopkeeper's sudden movement.
> ```

##### 景别转换表

| 中文 | 英文电影语义 |
|------|------------|
| 大全景 | extreme wide shot |
| 全景 | wide shot / establishing shot |
| 中景 | medium shot |
| 近景 | medium close-up |
| 特写 | close-up |
| 大特写 | extreme close-up |

##### 运镜转换表

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

##### 角度转换表

| 中文 | 英文电影语义 |
|------|------------|
| 平视 | eye-level |
| 微仰视 | low angle |
| 微俯视 | high angle |
| 俯视 | top-down / bird's eye view |
| 仰视 | extreme low angle |

##### 戏剧标签选择指南

根据镜头的景别和戏剧功能选择标签：

| 戏剧功能 | 标签 |
|---------|------|
| 交代环境 | ESTABLISHING SHOT |
| 角色登场 | CHARACTER ENTRANCE |
| 反应镜头 | REACTION SHOT |
| 对话场景 | DIALOGUE SHOT |
| 动作场景 | ACTION SHOT |
| 物品/细节 | INSERT SHOT |
| 象征揭示 | SYMBOLIC REVEAL |
| 情感特写 | EMOTIONAL CLOSE-UP |
| 主观视角 | POV SHOT |
| 过肩镜头 | OVER-THE-SHOULDER |
| 双人镜头 | TWO-SHOT |
| 群像镜头 | GROUP SHOT |

##### 精简模式（MD）处理

精简模式下镜头信息融入叙事段落（一段一镜）。Agent 需要：

1. 将每个叙事段落对应一个帧任务
2. 从散文中提取景别、运镜、光线等关键词（如"全景缓推"→ wide shot, slow push-in）
3. 按转换表转为英文电影语义
4. 台词以 `角色名："台词"` 形式出现时，台词通常不需要出现在画面中（除非角色在阅读/书写）

---

#### 段落 5：TEXT POLICY

**常驻段**——无论是否检测到特定文字元素，此段始终存在。默认策略防止模型自行生成假汉字/拼音；精确文字内容根据 2.3 检测结果条件注入。

**默认策略（无特定文字时）**——**始终包含禁字幕块**：
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

**类型 A — 必须准确出现的文字**（在默认策略后追加）：
```
Required readable text: "{Chinese text content}"
Prioritize accurate Chinese typography.
```

**类型 B — 装饰性文字**（在默认策略后追加）：
```
Decorative text: traditional Chinese handwritten signs, unreadable but authentic.
Do not specify exact text content.
```

**类型 C — 道具文字**（在默认策略后追加）：

文字决定剧情时：
```
Prop text — {prop_name (English)}:
Exact text: "{Chinese text content}"
Do not replace Chinese characters with English letters or pinyin.
```

文字仅为视觉元素时：
```
Prop text — {prop_name (English)}:
Generate material texture only. Do not render readable characters.
```

> 多种类型同时存在时，在同一个 TEXT POLICY 段内分列，共享默认策略头部。

---

#### 段落 6：CINEMATIC QUALITY

合并视觉风格、摄影语言原则和画质要求为单段。从风格参考文件提取 `style_anchor`、`style_footer`、`camera_language`、`quality`，中间填入通用设定的氛围/色调/光线描述（转英文）：

```
CINEMATIC QUALITY:

{style_anchor}

{通用设定.全局氛围基调 → 英文}
{通用设定.全局色彩调性 → 英文}
{通用设定.全局光线基调 → 英文}

{style_footer}

Camera principles:
{camera_language}

{quality}
```

> 通用设定中的中文描述需转为英文电影语义。各风格参考文件附带翻译指引表。
>
> **关键词精简原则**：避免在 quality 中反复堆砌 cinematic / film / professional / realistic 等词。模型已通过 `production_type` 和 `style_anchor` 理解风格基调，重复关键词会稀释注意力。

---

#### 段落 7：AVOID

从风格参考文件 front-matter 提取 `avoid`，**完整注入**，并**必须在末尾追加**下列分镜专用禁令（即使风格文件已含同类条目，也再写一遍，强化模型注意力）：

```
AVOID:

{style_avoid}

Single-frame layout violations:
Multi-panel layout.
Comic grid or manga panels.
Collage or contact sheet.
2x2 grid or any tiled grid of shots.
Split-screen.
Storyboard sheet.
Borders or gutters dividing the canvas into multiple shots.

Burned-in text violations:
Subtitles.
Captions.
Lower-thirds.
Title cards.
On-screen dialogue text.
Watermarks.
Logos.
Shot numbers painted on the image.

Period / cast violations:
Anachronistic costumes from wrong dynasties or eras.
Invented face for a named character who has a reference image.
Dropping a character reference when the character is still in frame.
```

---

### 2.5 逐帧匹配参考图

对每个组的每个镜头（帧），按「出场角色引用铁律」与道具/场景规则，从 Step 1 清单选取文件：

#### 步骤 A：建组在场表

读完整组全部镜头 → 列出本组出现过的具名角色 → 与 `角色参考图/` 文件名匹配。  
缺参考的具名角色 → **硬终止**（见上节龙套表）。

#### 步骤 B：逐帧 `cast`

对本帧用「何谓出场」表得到 `cast`（中文名列表）。  
**不是**「焦点角色列表」——站位里提到的在场角色、只露手的角色全部计入。

#### 步骤 C：组装 `images`

1. **角色**：`cast` 中每个有参考图的角色各一张，戏剧重要性排序。局部入画也要挂。
2. **前帧**（仅非首帧）：`{{PREV_OUTPUT}}`，**紧接全部角色之后**（不得垫在风格后）
3. **场景**：本场物理空间场景图（同场全帧共用）
4. **道具**：本帧重要道具。优先剧集级，否则全局基准（`出现场合` 含本集）
5. **风格**：一张，**始终最后**

写入顺序：
- 首帧：`角色… → 场景 → 道具… → 风格`
- 后续帧：`角色… → {{PREV_OUTPUT}} → 场景 → 道具… → 风格`

#### 步骤 D：无图龙套

`cast` 只列有参考的具名角色。无名路人**不进** `cast`/`images`，但必须在 FRAME DETAIL 用时代锚定英文描写，并受 AVOID 错代禁令约束。

prompt 中 REFERENCE IMAGE MAPPING 与 `images` **一一对应**；Character Identity Anchor 个数 = 角色图个数 = `cast` 长度。

> **同场场景一致**：同一 `scene` 内所有帧引用同一场景参考图。
>
> **角色增减（修订）**：
> - 完全不在画内且站位未提及 → 不引
> - 在场（含局部/背景/被点名）→ **必须引**
> - 已离场 → 后续可不引
> - 新登场 → 从该帧起引角色参考锁脸；空间靠前帧
>
> **错误（EP06 组1 镜2）**：镜1 引掌柜；镜2 只引小二、不引掌柜，但站位写「小二望掌柜」→ 掌柜失真。  
> **正确**：镜2 `cast: ["小二","掌柜"]`，两张角色参考都在，`{{PREV_OUTPUT}}` 在角色之后、场景之前。
>
> **后续帧完整示例**：
> ```
> "cast": ["掌柜", "茶客"],
> "images": [
>   "project/.../角色参考图/掌柜_默认妆造.png",
>   "project/.../角色参考图/茶客_默认妆造.png",
>   "{{PREV_OUTPUT}}",
>   "project/.../场景参考图/茶馆.png",
>   "project/.../道具参考图/茶壶.png",
>   "project/.../风格/风格参考-繁花.png"
> ]
> ```
---

### 2.6 任务表 JSON 格式

任务表使用 sequential 模式，每帧一个 task：

```json
{
  "mode": "sequential",
  "model": "nano-banana-2",
  "output_path": "project/{项目名}/{剧集号}/分镜/分镜图",
  "tasks": [
    {
      "id": "{组号}-{镜号}",
      "scene": "{场号}",
      "group": "{组号}",
      "depends_on": "{前序任务ID}",
      "filename": "组{N}_镜{M}.png",
      "cast": ["角色A", "角色B"],
      "prompt": "...",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/.../角色参考图/角色A_默认妆造.png",
        "project/.../角色参考图/角色B_默认妆造.png",
        "{{PREV_OUTPUT}}",
        "project/.../场景参考图/场景.png",
        "project/.../道具参考图/道具A.png",
        "project/.../道具参考图/道具B.png",
        "project/.../风格/风格参考.png"
      ]
    }
  ]
}
```

> 上例为**非首帧**（含参考帧）。首帧去掉 `depends_on` 与 `{{PREV_OUTPUT}}`，顺序为角色→场景→道具→风格。

| 字段 | 必填 | 说明 |
|------|------|------|
| `mode` | 是 | 固定 `"sequential"`（参考帧模式）；缺省或 batch 视为错误 |
| `model` | 是 | 固定 `"nano-banana-2"` |
| `output_path` | 是 | 输出目录 |
| `tasks[].id` | 是 | `"{组号}-{镜号}"`，如 `"1-1"`、`"1-2"`、`"2-1"` |
| `tasks[].scene` | 是 | **物理场**号字符串。同场 = 同连续物理空间 |
| `tasks[].group` | 是 | 组号字符串 |
| `tasks[].depends_on` | 场首帧省略 | 必须指向**同场播放顺序上的直接前一帧** id |
| `tasks[].filename` | 是 | `"组{N}_镜{M}.png"` |
| `tasks[].cast` | 是* | 本帧在场具名角色中文名列表（*纯空镜/无角色帧可为 `[]`）；顺序=角色参考顺序 |
| `tasks[].prompt` | 是 | 单帧 prompt（7段；含单帧画布声明、禁字幕 TEXT POLICY、强化 AVOID） |
| `tasks[].aspectRatio` | 是 | 固定 `"16:9"` |
| `tasks[].imageSize` | 是 | `"2K"` |
| `tasks[].images` | 是 | 见排序规则；非首帧必须含 `"{{PREV_OUTPUT}}"` 且位于**全部角色之后、风格之前** |

> **场级参考帧链（完整）**：
> 1. 按 `scene` 分组；组内按组号、镜号排序
> 2. 每场排序后第 1 个 task：无 `depends_on`，无 `{{PREV_OUTPUT}}`
> 3. 第 2..N 个 task：`depends_on` = 排序后前一个 task 的 `id`，且 `images` 含 `{{PREV_OUTPUT}}`
> 4. 跨组不断链：组2镜1 的 `depends_on` = 组1最后一镜
> 5. 不同 `scene` 之间禁止 `depends_on`
>
> **组文件场号**：`expand_scenes_to_groups.py` 注入 `场号`/`场名称`；`scene` 必须与之一致。
---

### 2.7 完整示例

以下为 1 场（含 1 个组、2 帧）的任务表示例（LiveAction 风格，16:9）。**本示例展示多角色（2 角色）+ 多道具（2 道具）场景**：

```json
{
  "mode": "sequential",
  "model": "nano-banana-2",
  "output_path": "project/荼荼茶业-古装/EP04/分镜/分镜图",
  "tasks": [
    {
      "id": "1-1",
      "scene": "1",
      "group": "1",
      "filename": "组1_镜1.png",
      "cast": ["掌柜", "茶客"],
      "prompt": "(完整 7 段 prompt：OPENING 含单帧画布声明；TEXT POLICY 含 Hard ban on burned-in graphics；AVOID 含 multi-panel + subtitle；REFERENCE 含 2 个 Character Identity Anchor…)",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/茶客_默认妆造.png",
        "project/荼荼茶业-古装/EP04/场景参考图/茶馆.png",
        "project/荼荼茶业-古装/EP04/道具参考图/茶罐.png",
        "project/荼荼茶业-古装/EP04/道具参考图/账簿.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    },
    {
      "id": "1-2",
      "scene": "1",
      "group": "1",
      "depends_on": "1-1",
      "filename": "组1_镜2.png",
      "cast": ["掌柜", "茶客"],
      "prompt": "(后续帧：OPENING 单帧声明 + SCENE CONTINUITY REFERENCE-FRAME MODE + 角色 Anchors + Previous Frame Anchor + TEXT POLICY 禁字幕 + AVOID 宫格/字幕…)",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/茶客_默认妆造.png",
        "{{PREV_OUTPUT}}",
        "project/荼荼茶业-古装/EP04/场景参考图/茶馆.png",
        "project/荼荼茶业-古装/EP04/道具参考图/账簿.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    }
  ]
}
```

> **示例要点说明**：
> - **首帧（1-1）**：`cast` 2 人 + 角色图 2 + 场景 + 道具 + 风格，无 `{{PREV_OUTPUT}}`
> - **后续帧（1-2）**：`cast` 仍含在场两人；顺序 角色… → `{{PREV_OUTPUT}}` → 场景 → 道具… → 风格；`depends_on: "1-1"`
> - **不得**因镜2 焦点切到茶客而丢掉掌柜参考（EP06 组1 反例）
> - **参考帧语义**：1-2 把 1-1 成图当 live set，在景别/动作上演化，而不是重抽一张无关图
> - **同场跨组**：若还有组2，则下一镜 `depends_on` 必须是组1最后一镜 id
> - **场景一致**：同场保留同一场景参考图
> - **cast 长度 = 角色图数 = Character Identity Anchor 数**；MAPPING 总数 = images 长度（含 Previous Frame Anchor）
---

## Step 3：执行分镜图生成

任务表编写完成后，加载 art-director 技能，以 sequential 模式执行：

1. **校验**：运行 `python validate_task_table.py --check "分镜图_任务表.json"`
2. **路径解析**：任务表中的 `images` 路径为相对路径，Agent 调用 MCP tool 前必须解析为绝对路径（MCP server 的 CWD 与 Agent 不同，相对路径无法解析）
3. **执行（参考帧模式，不可降级）**：按 art-director sequential 执行
   - 场间并行：不同 `scene` 的**首帧**可交叉提交
   - 场内串行：同场下一帧必须等上一帧 `completed` 且拿到可访问的 `image_url`（COS）后，**字面替换** `images` 里的 `{{PREV_OUTPUT}}` 为该 URL，再 submit
   - 替换后调用 MCP 前仍须把其余本地路径解析为绝对路径；URL 与已替换的参考帧 URL 原样传递
   - 任一帧 `failed`：停止该场后续链，记录事件；不跳过失败帧继续（否则参考帧断裂）
4. **下载**：每帧完成后下载到 `output_path`，文件名与 `filename` 一致，供人工验收链连续性

> 详细策略见 art-director「执行模式 > 模式二：sequential（参考帧模式）」。
---

## Step 4：校验

运行校验器确保任务表格式正确：

```bash
python .opencode/skills/storyboard-generator/scripts/validate_task_table.py \
  --check "project/{项目名}/{剧集号}/分镜/分镜图_任务表.json" --verbose
```

校验项：
1. JSON 语法正确性
2. 模型必须在允许集合内（`nano-banana-2` / `nano-banana-pro`）
3. 分辨率必须在允许集合内（`2K` / `4K`）
4. 画面比例必须为 `16:9`
5. `mode` 必须为 `sequential`（参考帧模式）
6. 每个任务 `id`、`group`、`scene` 必填
7. **场级链完整**：同 `scene` 按组号/镜号排序后，第1帧无 depends_on，其后每一帧 depends_on 等于直接前帧 id
8. `depends_on` 必须同场且存在
9. 有 `depends_on` ⇔ `images` 含 `{{PREV_OUTPUT}}`
10. 参考图顺序：首帧 角色→场景→道具→风格；后续帧 角色→前帧→场景→道具→风格
11. `{{PREV_OUTPUT}}` 不得在风格之后，不得在全部角色之前（须在角色锁之后）
12. images 为具体文件或 `{{PREV_OUTPUT}}`
13. Image N: 映射块数量与 images 一致
14. 必需段落标题齐全；后续帧 SCENE CONTINUITY 应体现参考帧/previous frame
15. FRAME DETAIL 含 Purpose 与 Feeling
16. 禁止焦距 / storyboard / frame N of M / 宫格·拼贴词 / 未解析 `{...}`
17. **`cast` 必填**（可为 `[]`）；每个 cast 名必须出现在对应角色参考路径文件名中
18. 角色参考图数量 = Character Identity Anchor 数量 = `cast` 长度
19. prompt 必须含单帧画布声明（`single` + `fills the entire canvas` 或等价 `exactly one image` + 禁 multi-panel）
20. TEXT POLICY 必须含禁字幕（`subtitle`/`No subtitles` 等）
21. AVOID 必须含 multi-panel 与 subtitle 类禁令
22. 元约束净化：prompt 不得含「提示词净化规范」11 类必删元约束残留（段落放置/编排指令、Decision rule、编译器/流水线说明、中文事实保留指令、占位符机制解释、锚点职责从句与职责块、Mapping 内机制解释、道具配对说明括号等）；校验器对此类残留输出告警（不阻塞通过，但须修正后重提）

**提交 art-director 前人工/脚本自检（四条用户缺陷）**：

| # | 缺陷 | 规范堵点 | 校验堵点 |
|---|------|----------|----------|
| 1 | 无参考龙套朝代漂移 | 龙套时代锚定 + 具名无图硬终止 | 无法静态全检文字质量；具名无图靠 Agent 硬终止 |
| 2 | 在场角色漏引参考 | 出场定义 + 组在场表 + `cast` | `cast`↔角色路径↔Anchor 数量 |
| 3 | 多宫格/2×2 | OPENING 单帧声明 + AVOID + 风格 avoid | 宫格词/缺单帧声明失败 |
| 4 | 烧字幕 | TEXT POLICY 硬禁 + AVOID | 缺禁字幕块失败 |
