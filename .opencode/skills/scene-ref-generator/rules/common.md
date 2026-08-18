# 共享定义

以下规范适用于双视图模式（默认）。

> 备选全景模式（左俯瞰+右二宫格）见 `rules/common_panoramic.md`。

## 参考图严格遵循原则

当 `前期采样/场景/{场景名}*.png` 参考图存在时，Agent **必须**严格遵守以下规则：

### 参考图的权威地位

| 层级 | 优先级 | 说明 |
|------|--------|------|
| **P0 — 强制遵守** | 最高 | 场景的空间布局、建筑风格、色调色温、环境基调，必须以采样图为**唯一基准**，不得偏离或自由发挥 |
| **P1 — 尽量跟随** | 高 | 采样的光影方向、天气条件、植被/水域特征、镜头构图，必须在 prompt 中声明"严格遵循参考图" |
| **P2 — 允许补充** | 中 | 参考图未覆盖的方位视角（如背面、右侧）可基于正面/左侧图合理推断 |
| **P3 — 可补充细节** | 低 | 仅参考图完全无法提供的视觉信息（如特定时间段的事件动作），可额外补充 |

### 参考图分析步骤

在构建 prompt 之前，**必须**先执行以下分析：

```
1. 列出所有匹配的场景采样图文件（文件名、路径）
2. 根据文件名推断覆盖的方位/视角
3. 提取核心视觉特征：建筑风格、色调色温、空间尺度、光线方向
4. 将提取的特征融入 prompt 的 Scene / Lighting / Atmosphere 段落
```

## 场景参考图布局约束（双视图）

- 一个场景 = 两个 task（内景 + 外景）。每个场景生成 2 张独立超宽全景单帧图。
- **内景**（`{场景名}_内景.png`）：聚焦室内空间——建筑结构、家具陈设、材质纹理、室内光线氛围。
- **外景**（`{场景名}_外景.png`）：聚焦室外空间——建筑外观、周边环境、街道/地形、天际线、天气光线。
- 每张图为**独立单帧**，充满整个画布。**禁止**多面板、拼贴、二宫格等复合排版。
- **aspectRatio 固定为 4:1**（超宽全景画幅），**imageSize 固定为 4K**，**model 固定为 nano-banana-2**。
- Prompt 采用**英文控制层 + 中文内容层**的双语结构（7 段结构，参考分镜 skill 视觉锚点图模板），移除角色身份锁定（IDENTITY LOCK），聚焦于场景空间环境本身。
- **绝对禁止**在 prompt 中描述剧情角色（如郑和、一岛等人物外观、服饰、动作）。仅聚焦场景空间环境本身。若需要人物提供尺度参照，使用"群众角色"等泛化描述。
- **images 数组中严禁**包含角色参考图或道具参考图。

## 单场景图文对应

全局依赖的 `场景设定/具体设定/` 下每个 `.md` 文件代表一个独立场景。双视图模式为每个场景生成 2 张场景参考图（内景 + 外景），因此 task 数量 = 场景数量 x 2。

| 场景设定文件 | 对应的 task 数 |
|-------------|--------|
| 每个 `.md` 文件 | 2 个 task（内景 + 外景） |

## 缺省值原则（重要）

AI 图像模型对某些环境属性有统计偏见——如果 prompt 不明确声明，模型会按训练数据"自动填空"。**必须对每个可能被默认填充的视觉属性做显式声明**：若不存在则明确否定，若存在则具体描述。

关键防范列表（必需在 prompt 中显式声明的属性）：

| 属性 | 风险 | 正确做法 |
|------|------|---------|
| 视觉风格 | 默认输出概念图风格 | 从全局设定提取实际风格，如影视级写实摄影/卡通/3D渲染等 |
| 色调/色温 | 历史场景默认偏暗偏黄 | 按场景设定明确写暖金/冷白/清冷等 |
| 天气/光线 | 默认晴天正午 | 描述晨光/黄昏/阴雨/雾霭/风暴等 |
| 建筑风格 | 古代默认中式古典 | 具体描述建筑风格与历史时期 |
| 植被/环境 | 忽略季节/地域 | 描述植被、水域、地域环境 |
| 人群密度 | 空无一人或过度拥挤 | 按设定明确多少人或无人 |
| 剧情人物 | 默认引入角色人物 | **场景参考图严禁出现剧情角色**。Prompt 中不得描述任何角色人物的外观、动作、服饰，仅聚焦场景空间环境本身。若需要人物提供尺度参照，使用"群众角色"等泛化描述 |
| 参考图范围 | 默认添加角色/道具参考图来辅助风格一致性 | **images 数组中严禁包含角色参考图和道具参考图**。场景参考图仅需场景采样图和风格参考图作为视觉参考 |

## 场景间描述差异化原则（重要）

多个场景可能共用相同的地理位置，**必须防止不同场景的 prompt 中出现重复的短语或句式**：

| 风险 | 错误做法 | 正确做法 |
|------|---------|---------|
| 地理描述重复 | 所有场景都写相同的地理特征 | 每个场景只提取其**独有的**地理/时代特征 |
| 句式结构雷同 | 所有场景都用相同句式开头 | 每个场景的开篇从不同角度切入——空间、时代、光线、氛围各选其一 |
| 关键元素复制 | 将场景设定中的关键元素表逐条翻译进 prompt | 从关键元素中提取最高优先级的 1-2 个核心特征深入描述 |

### 风格类型自适应规则

根据从 全局设定.md 提取的 style_desc 判断视觉风格类型：

| 风格类型 | 判断依据（style_desc 包含以下关键字） | 参考图遵循策略 |
|---------|-----------------------------------|--------------|
| 写实风格 | 写实、真实、影视级、照片级、超清、8K、写实摄影、电影级 | 严格遵循参考图的**构图、空间布局、建筑风格、色调色温**所有维度 |
| 非写实风格 | Q版、Chibi、卡通、乙烯基玩具、哑光塑料、可爱、3D渲染、手绘、赛璐璐、水墨 | 仅参考**构图与空间布局**（空间关系），视觉风格（色调、色温、渲染质感）遵从 style_desc |

**判断逻辑**：检查 style_desc 中是否包含以上关键字。不含任何关键字时默认写实风格。

## 视觉风格提取

Prompt 构建前，从全局设定中提取视觉风格描述：

1. 读取 `project/{项目名}/全局依赖/全局设定.md`
2. 提取**视觉风格关键字**：如"影视级写实摄影"、"手绘赛璐璐卡通"、"3D 渲染皮克斯风格"、"水墨淡彩"等
3. 将提取到的风格描述记为 `{style_desc}`，用于模板中

> **无全局设定时**：退而求其次从 `前期采样/风格/` 中的参考图文件名判断风格倾向。仍无法判断时使用"超写实影视级画面"。

### 英文风格参数提取

同时从全局设定和风格参考文件中提取以下英文风格参数（用于英文控制层）：

| 参数 | 来源 | 示例 |
|------|------|------|
| `{film_context}` | 全局设定.通用设定.风格 -> 英文 | a historical drama film |
| `{production_type}` | 风格参考文件 front-matter | cinematic photorealistic frame |
| `{neg_1}` / `{neg_2}` / `{neg_3}` | 风格参考文件 front-matter | anime / cartoon / watercolor |
| `{style_anchor}` | 风格参考文件 front-matter | Photorealistic cinematic quality... |
| `{style_footer}` | 风格参考文件 front-matter | Film grain, natural color science... |
| `{camera_language}` | 风格参考文件 front-matter | Composed framing... |
| `{quality}` | 风格参考文件 front-matter | 4K, high dynamic range... |
| `{style_avoid}` | 风格参考文件 front-matter | No stylization... |

> 若项目无风格参考文件（`.opencode/skills/storyboard-generator/references/styles/*.md`），则从 `{style_desc}` 推导合理的英文等价描述。

## 内景与外景的内容划分

从场景具体设定文件（`具体设定/{场景名}.md`）中提取内容时，按以下规则划分内/外景：

| 内容类型 | 内景 | 外景 |
|---------|------|------|
| 建筑结构（室内） | 斗拱、房梁、木柱、门窗内饰 | 屋顶、檐角、外墙、门面 |
| 家具陈设 | 桌椅、茶案、器皿、帘幕 | 门外摊位、灯笼、招牌 |
| 空间纵深 | 室内纵深、隔间层次 | 街道纵深、建筑群天际线 |
| 光线 | 室内光源（烛光、油灯、天窗） | 自然光（阳光、月光、阴雨漫射） |
| 天气/氛围 | 雨滴从房梁滴落、潮湿空气 | 街面雨水、远山雾气、天空 |
| 人群 | 室内茶客（泛化群众） | 街上行人（泛化群众） |

> 若场景仅有室内或室外设定（如纯室外场景"长安街市"），仍生成 2 个 task，但外景 task 聚焦街市整体环境，内景 task 聚焦某一标志性建筑的内部空间（如街边茶肆内部）。

## Prompt 双语分工规则

参考分镜 skill 视觉锚点图模板的双语分工原则：

| 语言 | 负责内容 |
|------|---------|
| **英文（控制层）** | 段落标题、场景类型声明、参考图映射标签、单帧声明、构图/摄影/镜头/灯光/材质/画质/风格质感、技术质量要求、负面约束、TEXT POLICY、AVOID |
| **中文（内容层）** | 场景名与空间内容、环境描述、氛围描述、时代事实、建筑细节、家具陈设、光线氛围的具体描述 |

> **关键原则**：中文内容层保留原始设定中的中文描述，不做翻译。英文控制层围绕中文内容组装控制语言，不篡改场景内容本身。

## Prompt 模板

双视图模式使用**英文控制层 + 中文内容层**的双语 Prompt 结构，参考分镜 skill 视觉锚点图模板，但移除角色身份锁定（IDENTITY LOCK），聚焦于场景空间环境本身。

每个场景生成 2 个 prompt：内景 prompt 和外景 prompt。

### 内景 Prompt 模板（7 段结构）

```
SCENE REFERENCE FRAME — INTERIOR

Create a professional cinematic interior scene reference frame for {film_context}.

This is an interior scene reference image for {scene_name_zh} — a single establishing image that locks the scene's interior spatial layout, architecture, furniture, materials, and atmosphere.
Generate exactly one image for this single frame only.
One single photographic still that fills the entire canvas.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.

SCENE CONTINUITY:

This is an interior reference for {scene_name_zh} — the definitive spatial and atmospheric reference for this indoor location.

Maintain strict continuity with reference materials:
- same {environment_description_zh}
- same furniture layout and architectural details
- same lighting atmosphere
- same {period_description_zh}
- no anachronistic elements from other eras or dynasties

REFERENCE IMAGE MAPPING:
Image {N}: Environment Anchor — Highest priority
{scene_name_zh} — {场景室内空间中文描述：建筑结构、家具陈设、材质纹理、装饰细节与空间关系}。
Preserve: architecture, spatial layout, materials, atmosphere.

Image {N}: Visual Style Anchor — Second priority
{brief English style description}.
Preserve: color palette, lighting mood, visual style.

FRAME DETAIL:

Scene:
{场景室内空间完整描述 → 中文叙事，包含建筑结构、家具陈设、材质纹理、装饰细节、空间纵深}

Composition:
{景别 + 摄影机角度 → 英文电影语义，如 ultra-wide panoramic shot, eye-level, showing the full interior space from entrance to back wall}

Camera feeling:
{摄影机运动 → 英文电影语义，如 static camera, locked-off, establishing framing with subtle atmospheric depth}

Lighting:
{光线描述 → 英文，如 warm candlelight as key, soft ambient fill from windows}

Atmosphere:
{场级氛围与感受 → 中文}

CINEMATIC QUALITY:

{style_anchor}

{全局风格氛围基调 → English}
{全局色彩调性 → English}
{全局光线基调 → English}

{style_footer}

Camera principles:
{camera_language}

{quality}

TEXT POLICY:

Hard ban on burned-in graphics (non-negotiable):
- No subtitles, captions, lower-thirds, or title cards
- No on-screen dialogue text or lyric text
- No watermarks, logos, shot numbers, timecode, or UI chrome

Diegetic in-world text only (shop signs, book pages, packaging) when the scene itself contains them:
- Preserve original Chinese characters
- Do not translate into English

AVOID:

{style_avoid}

Compact final bans:
- No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean panoramic frame only.
- No anachronistic costumes or elements for the period.
- No character focus; this is a scene environment reference, not a character portrait.
- No empty or lifeless space; every interior must feel lived-in and atmospheric.
```

### 外景 Prompt 模板（7 段结构）

```
SCENE REFERENCE FRAME — EXTERIOR

Create a professional cinematic exterior scene reference frame for {film_context}.

This is an exterior scene reference image for {scene_name_zh} — a single establishing image that locks the scene's exterior architecture, surrounding environment, street/landscape, and atmospheric conditions.
Generate exactly one image for this single frame only.
One single photographic still that fills the entire canvas.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.

SCENE CONTINUITY:

This is an exterior reference for {scene_name_zh} — the definitive spatial and atmospheric reference for this outdoor location.

Maintain strict continuity with reference materials:
- same {environment_description_zh}
- same building exterior style and architectural details
- same surrounding landscape and street layout
- same weather and time-of-day atmosphere
- same {period_description_zh}
- no anachronistic elements from other eras or dynasties

REFERENCE IMAGE MAPPING:
Image {N}: Environment Anchor — Highest priority
{scene_name_zh} — {场景室外空间中文描述：建筑外观、周边环境、街道/地形、天际线与空间关系}。
Preserve: architecture, spatial layout, environment, atmosphere.

Image {N}: Visual Style Anchor — Second priority
{brief English style description}.
Preserve: color palette, lighting mood, visual style.

FRAME DETAIL:

Scene:
{场景室外空间完整描述 → 中文叙事，包含建筑外观、周边环境、街道/地形、植被、天际线、空间纵深}

Composition:
{景别 + 摄影机角度 → 英文电影语义，如 ultra-wide panoramic establishing shot, eye-level, showing the building facade and street context with surrounding architecture}

Camera feeling:
{摄影机运动 → 英文电影语义，如 static camera, locked-off, establishing framing with subtle atmospheric depth}

Lighting:
{光线描述 → 英文，如 overcast diffused light, golden hour rim light}

Atmosphere:
{场级氛围与感受 → 中文}

CINEMATIC QUALITY:

{style_anchor}

{全局风格氛围基调 → English}
{全局色彩调性 → English}
{全局光线基调 → English}

{style_footer}

Camera principles:
{camera_language}

{quality}

TEXT POLICY:

Hard ban on burned-in graphics (non-negotiable):
- No subtitles, captions, lower-thirds, or title cards
- No on-screen dialogue text or lyric text
- No watermarks, logos, shot numbers, timecode, or UI chrome

Diegetic in-world text only (shop signs, street signs, banners) when the scene itself contains them:
- Preserve original Chinese characters
- Do not translate into English

AVOID:

{style_avoid}

Compact final bans:
- No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean panoramic frame only.
- No anachronistic costumes or elements for the period.
- No character focus; this is a scene environment reference, not a character portrait.
- No empty or lifeless space; every exterior must feel atmospheric and grounded.
```

## images 数组约束

images 数组**仅允许**包含以下类型的参考图，**禁止**混入任何角色参考图或道具参考图：

| 允许的类型 | 来源路径 | 说明 |
|-----------|---------|------|
| 场景采样图 | `前期采样/场景/{场景名}*.png` | 模式 A 下必须包含，位于 images[0] |
| 风格参考图 | `前期采样/风格/*.png` | 所有模式必须包含至少 1 张 |

**禁止的类型（无论何种模式，均不得加入 images 数组）：**
- 角色参考图：`全局依赖/角色设定/角色参考图/*.png`
- 道具参考图：`全局依赖/道具设定/道具参考图/*.png`
- 其他项目资产的参考图

**原因**：场景参考图的唯一目的是刻画场景空间环境本身。引入角色或道具的视觉特征会干扰生图模型对场景的独立理解，导致构图偏向于展示角色/道具而非空间环境。

## Schema 校验

调用 `scripts/validators.py` 的两个函数进行校验：

**顶层固定值（不可变）：**
- `model` **必须固定为** `"nano-banana-2"`
- `imageSize` **必须固定为** `"4K"`
- `aspectRatio` **必须固定为** `"4:1"`

**任务级校验** — `validate_tasks(tasks)`：

| 校验项 | 说明 |
|------|------|
| 基础字段 | prompt, model, imageSize, aspectRatio, filename, images |
| 类型 | model **必须固定为** `nano-banana-2`，imageSize **必须固定为** `4K`，aspectRatio **必须固定为** `4:1` |
| images/模式 | 至少 1 张参考图（场景采样图或风格参考图） |
| images/范围 | **images 中不得包含角色参考图路径或道具参考图路径**，仅允许场景采样图和风格参考图 |
| prompt | 无占位符，长度 ≥ 50 |
| filename | 必须以 .png 结尾 |

**顶层校验** — `validate_top_level(data)`：
- `model` **必须固定为** `"nano-banana-2"`
- `output_path` 非空
- `tasks` 存在

> 备选全景模式使用 `validate_tasks_panoramic()` 校验，参数为 gpt-image-2 / 1K / 2:1。

## 输出完成提示

```
双视图场景参考图任务表已生成，等待 Art-director 执行生图
- {N} 个场景，已生成 {N*2} 个 task（内景 {N} + 外景 {N}）
```
