# 阶段二：episode_storyboard_images — 分镜图绘制

**独立阶段（仅当 project_config.json 中 use_storyboard_images=true 时执行）**：此阶段在 `episode_storyboard_script`、`episode_character_ref`、`episode_prop_ref`、`episode_scene_ref` 之后执行，分镜图可参考剧集级场景/道具变化。`use_storyboard_images=false` 或未设置时跳过此阶段，video-director 将以角色/场景参考图为主要参考素材。

> **两种模式均支持分镜图绘制**。详细模式从 `组{N}.json` 读取，精简模式从 `组{N}.md` 读取。
>
> **目标模型**：`nano-banana-pro`，4K 分辨率，16:9 画面比例。Prompt 使用**英文**生成，以获得最佳模型理解效果。
>
> **分辨率策略**：4K + 16:9 + 多格分镜对模型压力较高（每格有效像素被压缩）。生产模式优先 4K 保证人物一致性；若发现多格质量下降（模糊、细节丢失），可回退 2K 生成后超分，以降低单次生成压力。

---

## Step 1：收集参考图清单

分镜图绘制前，**Agent 须列出各参考图目录下的具体文件**，供 Step 2 逐组引用。

| 参考图类型 | 来源路径 | 说明 |
|-----------|---------|------|
| 角色参考图 | `project/{项目名}/全局依赖/角色设定/角色参考图/*.png` | 全局角色参考图（含妆造匹配） |
| 场景参考图 | `project/{项目名}/{剧集号}/场景参考图/*.png` | 剧集级场景参考图（含本集场景变化） |
| 道具参考图 | `project/{项目名}/{剧集号}/道具参考图/*.png` | 剧集级道具参考图（含本集道具状态变化） |
| 风格参考图 | `project/{项目名}/前期采样/风格/*.png` | 全局视觉风格基准（色调、光影氛围、画面质感） |

> 如剧集级参考图目录不存在（无变化场景/道具），回退使用全局基准图：`全局依赖/场景设定/场景参考图/` 和 `全局依赖/道具设定/道具参考图/`。
>
> **道具全局基准文件名含出现场合**：回退引用全局道具基准图时，文件名格式为 `{道具名}_{出现场合}_基准.png`。需读取 `全局依赖/道具设定/具体设定/{道具名}.md` 中的 `出现场合` 字段，匹配正确的基准文件。仅引用该道具 `出现场合` 包含当前剧集号的基准图，**禁止**引用不属于本集的道具资产。

**Agent 执行**：用 LS 工具列出上述目录中的 `.png` 文件，记录完整路径。

---

## 参考图排序优先级

`images` 数组中的参考图按以下优先级排列：

1. **角色参考图**（最高优先级）— 主要角色排首位
2. **场景参考图**（第二优先级）
3. **道具参考图**（第三优先级）
4. **风格参考图**（第四优先级）

**硬约束**：角色和场景参考图必须位于前五个参考中。

---

## Step 2：Agent 直接编写任务表 JSON

Agent 使用 Write 工具直接编写 `分镜图_任务表.json`，保存到 `project/{项目名}/{剧集号}/分镜/分镜图_任务表.json`。

### 2.1 读取分镜内容

读取 `{剧集号}/分镜/分组/` 目录下的组文件：
- **详细模式**：`组{N}.json` — 从 `组叙事概述`、`通用设定`、`组转场`、`镜头列表` 获取组信息
- **精简模式**：`组{N}.md` — 从正文获取叙事概述和分镜描述（一段一镜）

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

Agent 扫描分镜内容，检测画面中可能出现的文字元素。扫描范围：

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

Prompt 使用**英文**生成，由以下 **7 段**按固定顺序组成。TEXT POLICY 为常驻段（默认策略始终存在，精确文字内容条件注入）。

> **编译器铁律**：Prompt 编译器的职责是将分镜内容**翻译**为图像模型可理解的英文描述，**不是编剧**。禁止新增原分镜中不存在的道具、时间、动作、情绪事件、光线条件或场景。仅复述和翻译原分镜已有的视觉信息。违反此规则的 prompt 会导致模型生成与分镜不一致的画面。

```
┌─ 1. OPENING DECLARATION
├─ 2. SCENE CONTINUITY
├─ 3. REFERENCE IMAGE MAPPING
├─ 4. STORYBOARD SEQUENCE
├─ 5. TEXT POLICY
├─ 6. CINEMATIC QUALITY
└─ 7. AVOID
```

---

#### 段落 1：OPENING DECLARATION

```
Create a professional storyboard board for {film_context}.

Generate one storyboard image containing {panel_count_word} sequential cinematic frames.

Each frame is a separate camera shot, not a variation of the same image.
Maintain chronological progression across all frames.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{film_context}` | 通用设定.风格 → 英文 | a historical drama film / a Chinese ink-wash animation film / a 3D animated film |
| `{panel_count_word}` | 该组镜头数 → 英文数字 | one / two / three / ... / nine |
| `{production_type}` | 风格参考文件 | a live-action film pre-production storyboard |
| `{neg_1/2/3}` | 风格参考文件 | concept art / illustration / a fantasy painting |

> **不声明网格布局**——仅声明帧数，布局由模型自由排列。
>
> **多帧分离约束**：必须明确声明每帧是独立镜头而非同一画面的变体，否则模型倾向于生成四张相似画面。

---

#### 段落 2：SCENE CONTINUITY

```
SCENE CONTINUITY:

The {panel_count_word} frames must represent the exact same scene sequence:
{sequence_description}.

Maintain strict continuity:
- same character identity
- same costume
- same hairstyle
- same {environment_description}
- same props
- same lighting atmosphere
- same {period_description}

Source fidelity rule:
Do not introduce visual elements, props, lighting conditions, locations, or actions
that are not explicitly present in the storyboard input.
The prompt compiler translates, does not embellish.
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{sequence_description}` | 组叙事概述 → 英文箭头序列 | establishing the environment → character action → reveal of the key object |
| `{environment_description}` | 通用设定.场景名称 → 英文 | tea house interior / modern family living room |
| `{period_description}` | 项目时代背景 → 英文 | historical period / Tang Dynasty period / modern setting |

> `{sequence_description}` 从组叙事概述提炼核心叙事节拍，用 `→` 连接，呈现戏剧弧线。
>
> **反二次创作约束**：`Source fidelity rule` 段是铁律的 prompt 内体现——编译器仅翻译分镜已有内容，禁止添加原分镜中不存在的视觉元素（如原分镜未提及"夜晚"则不得写入 night，未提及"油灯"则不得写入 oil lamp）。

---

#### 段落 3：REFERENCE IMAGE MAPPING

为 `images` 数组中的每张参考图写一个映射块，**顺序与数组严格一致**。每个映射块必须以 `Image {N}:` 开头，N 从 1 递增，与 `images` 数组索引（0-based）+1 对应。使用 **Anchor 类型**明确告知模型每张参考图的用途。

**角色参考**（可多个，按出场顺序）：
```
Image {N}: Character Identity Anchor
{角色名} — {角色简要英文描述}.
Preserve: facial identity, appearance, costume, hair styling, age, body proportions.
```

**场景参考**：
```
Image {N}: Environment Anchor
{场景名} — {场景简要英文描述}.
Preserve: architecture, spatial layout, materials, atmosphere.
```

**道具参考**（可多个）：
```
Image {N}: Prop Detail Anchor
{道具名} — {道具简要英文描述}.
Preserve: shape, texture, craftsmanship.
```

**风格参考**：
```
Image {N}: Visual Style Anchor
{风格简要英文描述}.
Preserve: color palette, lighting mood, visual style.
```

> **硬约束**：每个映射块的 `Image {N}:` 编号必须与 `images` 数组位置严格一一对应（Image 1 = images[0]，Image 2 = images[1]，...）。映射块数量必须与 `images` 数组长度一致。编号不连续或顺序错乱将导致模型无法正确关联参考图。
>
> **Anchor 类型的作用**：模型通过 Anchor 类型名（Character Identity / Environment / Prop Detail / Visual Style）直接理解每张图的用途，而非仅靠描述文本猜测。这对多图输入的参考图绑定至关重要。

---

#### 段落 4：STORYBOARD SEQUENCE

逐镜头转换。每个镜头一个 FRAME 块。**必须包含 Purpose 字段**——告诉模型这个镜头为什么存在：

```
FRAME {序号} — {dramatic_label}

Purpose:
{镜头戏剧功能 → 英文，一句话说明此镜头存在的理由}

Scene:
{场景描述 + 站位/调度 → 英文叙事，仅复述原分镜内容}

Action:
{角色动作 → 英文}

Performance:
{表演/微表情 → 英文}

Composition:
{景别 + 摄影机角度 → 英文电影语义}

Camera feeling:
{摄影机运动 → 英文电影语义}

Lighting:
{光线 → 英文}
```

> **Purpose 字段**是本段最重要的新增。模型需要知道每个镜头的戏剧目的（如"Establish the environment"/"Reveal character decision"/"Show reaction"），否则会将所有帧渲染为相似画面。
>
> **禁止焦距参数**：不再写入 35mm / 50mm / 85mm 等焦距数值。这些参数对图像模型无实际意义，且会导致模型将注意力分散到"摄影参数展示"而非画面内容。仅保留景别（wide shot / close-up 等）和角度（eye-level / low angle 等）。

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

1. 将每个叙事段落对应一个 FRAME
2. 从散文中提取景别、运镜、光线等关键词（如"全景缓推"→ wide shot, slow push-in）
3. 按转换表转为英文电影语义
4. 台词以 `角色名："台词"` 形式出现时，台词通常不需要出现在画面中（除非角色在阅读/书写）

---

#### 段落 5：TEXT POLICY

**常驻段**——无论是否检测到特定文字元素，此段始终存在。默认策略防止模型自行生成假汉字/拼音；精确文字内容根据 2.3 检测结果条件注入。

**默认策略（无特定文字时）**：
```
TEXT POLICY:

If readable Chinese text appears in the scene:
- Preserve original Chinese characters.
- Do not translate into English.
- Do not generate pinyin.
- Do not replace Chinese characters with Latin letters.

If exact typography cannot be guaranteed, preserve material and visual shape.
Leave text for post-production.
```

**类型 A — 必须准确出现的文字**（在默认策略后追加）：
```
Required readable text: "{中文文字内容}"
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
Prop text — {道具名}:
Exact text: "{中文文字}"
Do not replace Chinese characters with English letters or pinyin.
```

文字仅为视觉元素时：
```
Prop text — {道具名}:
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
> **关键词精简原则**：避免在 quality 中反复堆砌 cinematic / film / professional / realistic 等词。模型已通过 `production_type` 和 `style_anchor` 理解风格基调，重复关键词会稀释注意力。保持画质描述简洁有力，每项品质特征仅出现一次。

---

#### 段落 7：AVOID

从风格参考文件 front-matter 提取 `avoid`，直接注入。

---

### 2.5 逐组匹配参考图

对每个组，根据该组的角色出场、场景位置、道具使用，从 Step 1 收集的参考图清单中选取具体文件：

1. **角色**：该组出场的角色，每人一张参考图
2. **场景**：该组发生的场景，选对应场景参考图
3. **道具**：该组出现的道具，选对应道具参考图（无道具可省略）。优先使用剧集级道具参考图，无剧集级时回退全局基准图（需确认 `出现场合` 包含当前剧集号）
4. **风格**：统一引用全局风格参考图

将选中的文件**完整路径**写入 `images` 数组，按 角色 → 场景 → 道具 → 风格 排序。prompt 中 REFERENCE IMAGE MAPPING 段的映射块顺序与 images 数组一一对应。

> **按需引用**：仅引用该组实际涉及的角色/场景/道具，不引入无关参考图。

---

### 2.6 完整示例

以下为 1 个组的任务表示例（LiveAction 风格，3 镜）：

**Prompt 展开视图**（供参考结构，实际写入 JSON 时用 `\n` 转义换行）：

```
Create a professional storyboard board for a historical drama film.

Generate one storyboard image containing three sequential cinematic frames.

Each frame is a separate camera shot, not a variation of the same image.
Maintain chronological progression across all frames.

This is a live-action film pre-production storyboard,
not concept art,
not illustration,
not a fantasy painting.

SCENE CONTINUITY:

The three frames must represent the exact same scene sequence:
establishing the environment → character action → reveal of the key object.

Maintain strict continuity:
- same character identity
- same costume
- same hairstyle
- same tea house interior
- same props
- same lighting atmosphere
- same historical period

Source fidelity rule:
Do not introduce visual elements, props, lighting conditions, locations, or actions
that are not explicitly present in the storyboard input.
The prompt compiler translates, does not embellish.

REFERENCE IMAGE MAPPING:

Image 1: Character Identity Anchor
掌柜 — The female Tang Dynasty tea shop owner.
Preserve: facial identity, appearance, costume, hair styling, age, body proportions.

Image 2: Environment Anchor
春生茶肆 — Old Tang Dynasty tea house interior.
Preserve: architecture, spatial layout, materials, atmosphere.

Image 3: Prop Detail Anchor
会员牌 — Hand-painted wooden membership board.
Preserve: shape, texture, craftsmanship.

Image 4: Visual Style Anchor
Live-action historical Chinese drama visual style.
Preserve: color palette, lighting mood, visual style.

STORYBOARD SEQUENCE:

FRAME 1 — ESTABLISHING SHOT

Purpose:
Establish the tea house environment and the shopkeeper's position before the announcement.

Scene:
Inside Chunsheng Tea House during daytime.
The female shopkeeper stands behind the counter at the center of the tea house.
She holds several handmade wooden membership boards secretly in her hand.
A tea stove gently boils. Steam rises.
Several customers sit casually in the background.

Action:
She looks around the room,
observing the customers before announcing her new idea.

Performance:
A subtle confident smile.
A sense of excitement mixed with seriousness.

Composition:
Medium shot from the entrance direction.
The tea house environment occupies an important part of the frame.

Camera feeling:
Static camera, observational.

Lighting:
Soft daylight entering from the window,
combined with warm tea stove light.

FRAME 2 — CHARACTER ANNOUNCEMENT SHOT

Purpose:
Show the shopkeeper presenting the membership board to the customers.

Scene:
The shopkeeper raises one wooden membership board
toward the customers.

Action:
She slightly turns her body,
holding the board at chest level.
The customers look toward the board.

Performance:
Her expression becomes more confident.
Her eyes show the enthusiasm of someone introducing a new idea.

Composition:
Medium close-up focusing on the shopkeeper, the wooden board, and the connection between her and the customers.

Camera feeling:
Gentle push-in.

Lighting:
Warm tea stove light creates a strong emotional highlight on her face.

FRAME 3 — SYMBOLIC OBJECT REVEAL

Purpose:
Reveal the carved text on the membership board as the key story object.

Scene:
Close-up of the wooden membership board.
The board fills most of the frame.
Rough wood grain, hand-carved marks, uneven carving depth, aged material texture.
The background becomes a soft warm blur.

Action:
The board remains steady in the shopkeeper's hand.

Performance:
Steady hand, slight reverence.

Composition:
Insert shot, the board dominates the frame.

Camera feeling:
Slow push-in to the carved surface.

Lighting:
A warm directional light reveals the carving texture.

TEXT POLICY:

If readable Chinese text appears in the scene:
- Preserve original Chinese characters.
- Do not translate into English.
- Do not generate pinyin.
- Do not replace Chinese characters with Latin letters.

Prop text — 会员牌:
Exact text: "会员·喝十送一"
Do not replace Chinese characters with English letters or pinyin.

If exact typography cannot be guaranteed, preserve material and visual shape.
Leave text for post-production.

CINEMATIC QUALITY:

Live-action film.
Real human actors.
High-end cinema production quality.
Historical realism combined with subtle artistic expression.

Warm tea-colored palette, low saturation, aged wood brown, linen gray, dark bronze.
Soft natural daylight mixed with warm tea stove light.

The image should feel like a frame from a high-budget live-action production.

Camera principles:
Use intentional composition, realistic depth, natural camera perspective.
Subtle focus transition, authentic actor performance.
Do not make the frames look like separate illustrations.
They must look like consecutive shots photographed by the same film crew.

Natural skin texture.
Real fabric folds.
Authentic material textures.
Subtle film grain.
Natural high dynamic range.

AVOID:

AI generated appearance.
Digital painting.
Concept art.
3D render.
Game cinematic style.
Anime.
Fantasy costume.
Modern objects.
Inconsistent character identity.
Different clothing.
Different locations.
Plastic skin.
Overly perfect faces.
Artificial lighting.
Excessive visual effects.
Watermarks.
Logos.
Unwanted text.
```

**对应的 task JSON**：

```json
{
  "tasks": [
    {
      "prompt": "Create a professional storyboard board for a historical drama film.\n\nGenerate one storyboard image containing three sequential cinematic frames.\n\nEach frame is a separate camera shot, not a variation of the same image.\nMaintain chronological progression across all frames.\n\nThis is a live-action film pre-production storyboard,\nnot concept art,\nnot illustration,\nnot a fantasy painting.\n\nSCENE CONTINUITY:\n\nThe three frames must represent the exact same scene sequence:\nestablishing the environment → character action → reveal of the key object.\n\nMaintain strict continuity:\n- same character identity\n- same costume\n- same hairstyle\n- same tea house interior\n- same props\n- same lighting atmosphere\n- same historical period\n\nSource fidelity rule:\nDo not introduce visual elements, props, lighting conditions, locations, or actions\nthat are not explicitly present in the storyboard input.\nThe prompt compiler translates, does not embellish.\n\nREFERENCE IMAGE MAPPING:\n\nImage 1: Character Identity Anchor\n掌柜 — The female Tang Dynasty tea shop owner.\nPreserve: facial identity, appearance, costume, hair styling, age, body proportions.\n\nImage 2: Environment Anchor\n春生茶肆 — Old Tang Dynasty tea house interior.\nPreserve: architecture, spatial layout, materials, atmosphere.\n\nImage 3: Prop Detail Anchor\n会员牌 — Hand-painted wooden membership board.\nPreserve: shape, texture, craftsmanship.\n\nImage 4: Visual Style Anchor\nLive-action historical Chinese drama visual style.\nPreserve: color palette, lighting mood, visual style.\n\nSTORYBOARD SEQUENCE:\n\nFRAME 1 — ESTABLISHING SHOT\n\nPurpose:\nEstablish the tea house environment and the shopkeeper's position before the announcement.\n\nScene:\nInside Chunsheng Tea House during daytime.\nThe female shopkeeper stands behind the counter at the center of the tea house.\nShe holds several handmade wooden membership boards secretly in her hand.\nA tea stove gently boils. Steam rises.\nSeveral customers sit casually in the background.\n\nAction:\nShe looks around the room,\nobserving the customers before announcing her new idea.\n\nPerformance:\nA subtle confident smile.\nA sense of excitement mixed with seriousness.\n\nComposition:\nMedium shot from the entrance direction.\nThe tea house environment occupies an important part of the frame.\n\nCamera feeling:\nStatic camera, observational.\n\nLighting:\nSoft daylight entering from the window,\ncombined with warm tea stove light.\n\nFRAME 2 — CHARACTER ANNOUNCEMENT SHOT\n\nPurpose:\nShow the shopkeeper presenting the membership board to the customers.\n\nScene:\nThe shopkeeper raises one wooden membership board\ntoward the customers.\n\nAction:\nShe slightly turns her body,\nholding the board at chest level.\nThe customers look toward the board.\n\nPerformance:\nHer expression becomes more confident.\nHer eyes show the enthusiasm of someone introducing a new idea.\n\nComposition:\nMedium close-up focusing on the shopkeeper, the wooden board, and the connection between her and the customers.\n\nCamera feeling:\nGentle push-in.\n\nLighting:\nWarm tea stove light creates a strong emotional highlight on her face.\n\nFRAME 3 — SYMBOLIC OBJECT REVEAL\n\nPurpose:\nReveal the carved text on the membership board as the key story object.\n\nScene:\nClose-up of the wooden membership board.\nThe board fills most of the frame.\nRough wood grain, hand-carved marks, uneven carving depth, aged material texture.\nThe background becomes a soft warm blur.\n\nAction:\nThe board remains steady in the shopkeeper's hand.\n\nPerformance:\nSteady hand, slight reverence.\n\nComposition:\nInsert shot, the board dominates the frame.\n\nCamera feeling:\nSlow push-in to the carved surface.\n\nLighting:\nA warm directional light reveals the carving texture.\n\nTEXT POLICY:\n\nIf readable Chinese text appears in the scene:\n- Preserve original Chinese characters.\n- Do not translate into English.\n- Do not generate pinyin.\n- Do not replace Chinese characters with Latin letters.\n\nProp text — 会员牌:\nExact text: \"会员·喝十送一\"\nDo not replace Chinese characters with English letters or pinyin.\n\nIf exact typography cannot be guaranteed, preserve material and visual shape.\nLeave text for post-production.\n\nCINEMATIC QUALITY:\n\nLive-action film.\nReal human actors.\nHigh-end cinema production quality.\nHistorical realism combined with subtle artistic expression.\n\nWarm tea-colored palette, low saturation, aged wood brown, linen gray, dark bronze.\nSoft natural daylight mixed with warm tea stove light.\n\nThe image should feel like a frame from a high-budget live-action production.\n\nCamera principles:\nUse intentional composition, realistic depth, natural camera perspective.\nSubtle focus transition, authentic actor performance.\nDo not make the frames look like separate illustrations.\nThey must look like consecutive shots photographed by the same film crew.\n\nNatural skin texture.\nReal fabric folds.\nAuthentic material textures.\nSubtle film grain.\nNatural high dynamic range.\n\nAVOID:\n\nAI generated appearance.\nDigital painting.\nConcept art.\n3D render.\nGame cinematic style.\nAnime.\nFantasy costume.\nModern objects.\nInconsistent character identity.\nDifferent clothing.\nDifferent locations.\nPlastic skin.\nOverly perfect faces.\nArtificial lighting.\nExcessive visual effects.\nWatermarks.\nLogos.\nUnwanted text.",
      "model": "nano-banana-pro",
      "imageSize": "4K",
      "aspectRatio": "16:9",
      "filename": "组1.png",
      "images": [
        "project/荼荼茶叶/全局依赖/角色设定/角色参考图/掌柜.png",
        "project/荼荼茶叶/EP01/场景参考图/春生茶肆_破败.png",
        "project/荼荼茶叶/EP01/道具参考图/会员牌.png",
        "project/荼荼茶叶/前期采样/风格/真人实拍基准.png"
      ]
    }
  ],
  "model": "nano-banana-pro",
  "output_path": "project/荼荼茶叶/EP01/分镜"
}
```

### 2.7 硬约束汇总

- `model` 必须为 `nano-banana-pro`
- `imageSize` 必须为 `4K`
- `aspectRatio` 必须为 `16:9` 或 `9:16`
- `images` 数组**不得为空**——分镜图必须引用角色/场景参考图
- `images` 中的路径必须为**具体文件**（含扩展名 `.png`/`.jpg`），禁止目录路径
- 角色和场景参考图必须位于**前五个**参考中
- `images` 按 角色 → 场景 → 道具 → 风格 排序
- prompt 中 REFERENCE IMAGE MAPPING 段的每个映射块必须以 `Image {N}:` 开头，使用 **Anchor 类型**（Character Identity Anchor / Environment Anchor / Prop Detail Anchor / Visual Style Anchor）
- 映射块编号 N 从 1 递增，与 `images` 数组索引（0-based）+1 **严格一一对应**，编号必须**连续**
- prompt 严格遵循**七段式结构**：OPENING DECLARATION → SCENE CONTINUITY → REFERENCE IMAGE MAPPING → STORYBOARD SEQUENCE → TEXT POLICY → CINEMATIC QUALITY → AVOID
- **编译器铁律**：禁止新增原分镜中不存在的道具、时间、动作、情绪事件、光线条件或场景。仅复述和翻译原分镜已有的视觉信息
- 每个 FRAME 必须包含 **Purpose** 字段，说明该镜头的戏剧功能
- **禁止焦距参数**（35mm / 50mm / 85mm 等），仅保留景别和角度
- TEXT POLICY 为**常驻段**，无论是否检测到特定文字元素始终存在
- prompt 使用**英文**生成（TEXT POLICY 段中的中文文字内容除外）
- 台词、音效、剪辑转场、后期特效、时间码等字段**不写入** prompt

---

## Step 3：校验

编写完成后，运行校验脚本审核语法和引用一致性：

```bash
python ".opencode/skills/storyboard-generator/scripts/validate_task_table.py" \
  --check "project/{项目名}/{剧集号}/分镜/分镜图_任务表.json" --verbose
```

校验项：
1. JSON 语法正确性
2. 模型必须为 `nano-banana-pro`
3. 分辨率必须为 `4K`
4. 画面比例必须为 `16:9` 或 `9:16`
5. `images` 数组不得为空
6. `images` 路径必须为具体文件（非目录）
7. prompt 中 `Image N:` 映射块数量与 `images` 数组一致
8. `Image N:` 编号必须从 1 开始连续递增
9. 参考图优先级排序：角色 → 场景 → 道具 → 风格
10. 角色和场景参考图必须在前五个参考中
11. prompt 包含必需的七段标题
12. 每个 FRAME 包含 Purpose 字段

> **校验未通过时禁止进入 Step 4**。根据错误信息修正 JSON 后重新校验。

---

## Step 4：交美术指导执行批量生图

将 `分镜图_任务表.json` 交 art-director 执行批量生图，分镜图存入 `project/{项目名}/{剧集号}/分镜/分镜图_*.png`。

---

## 可选辅助：generate_task_table.py

如需快速生成骨架再手动修改，可使用 `generate_task_table.py` 生成初始任务表。但**推荐直接手写**——Agent 已掌握分镜内容和参考图清单，直接编写可避免骨架→修改的两步开销。

```bash
# 自动检测参考图目录
python ".opencode/skills/storyboard-generator/scripts/generate_task_table.py" \
  --groups-dir "project/{项目名}/{剧集号}/分镜/分组/" \
  --output-dir "project/{项目名}/{剧集号}/分镜/" \
  --output-name "分镜图_任务表.json" \
  --aspect-ratio 16:9 \
  --project-dir "project/{项目名}" \
  --episode "{剧集号}" \
  --model nano-banana-pro \
  --image-size 4K
```

> 脚本生成的骨架使用旧版 prompt 格式，仅提供 images 路径和基础结构。需手动改写为七段式电影摄影执行模板后方可校验。
