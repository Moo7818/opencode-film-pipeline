# 阶段二：episode_storyboard_images — 视觉锚点图绘制（visual_anchor 模式）

**默认阶段（当 `meta_query(scope=config)` 返回的 `config.reference_image_mode=visual_anchor` 或未设置时执行）**：此阶段在 `episode_storyboard_script`、`episode_character_ref`、`episode_prop_ref`、`episode_scene_ref` 之后执行，按角色阶段为每场生成视觉锚点图。`reference_image_mode=none` 时跳过此阶段；`storyboard_images` 时改为执行分镜图绘制（见 `phase-2-storyboard-images.md`）。

> 执行前提、参考图收集、排序优先级、出场引用铁律、龙套时代锚、单帧/禁字幕、风格匹配、文字检测、净化规范、七段公共规则、任务表公共字段、执行与校验流程见 **`references/phase-2-common.md`**（两模式单一事实源）。本文档只写锚点模式专属内容。

目标是为每个角色阶段锁定**场景空间、氛围基调、人物站位与关键动作神态**，使该阶段覆盖的镜头在后续视频生成阶段共享该锚点作为空间与视觉一致性参考。锚点图不是「帧级分镜」，而是「阶段级视觉定调」——但仍须保持影视级静帧质感，包含完整的角色动作与神态描述。

| 规则 | 说明 |
|------|------|
| mode | `"sequential"`，场内阶段串行，场间并行 |
| 场 | = 物理空间连续单元（与分镜脚本 `场号` 一致） |
| 数量 | 每个角色阶段一张锚点图；无具名角色入场/离场时每场一张 |
| 依赖 | 同场阶段间 `depends_on` 串行（前阶段输出→后阶段空间参考）；场间无依赖，可并行 |
| 共享 | 同阶段覆盖的镜头在视频生成阶段引用同一张锚点图 |

Prompt 使用 **English control shell + 中文 content layer**（分工见下文）。

---

## 双语 Prompt 分工（visual_anchor 专用）

Prompt 不是"整体英文翻译"，而是用英文结构包裹中文叙事内容。以下分工必须贯穿七段：

- **English control layer**：段落标题、`IDENTITY LOCK`、`Reference priority`、身份/连续性硬约束、优先级关系、单帧声明、构图/摄影/镜头/灯光/材质/画质/风格质感、技术质量要求、负面约束。
- **中文 content layer**：来自分镜和设定的角色名与角色关系、场景名与空间内容、动作、站位、神态、台词相关内容、道具内容、时代事实和剧情事实。不得为了"英文 prompt"翻译这些内容，也不得在翻译时顺便重写角色外貌。
- **绑定写法**：先写参考图，再写职责或角色名；例如 `Reference Image 1 character（掌柜角色）站在右侧柜台后擦拭茶杯。`。这表示动作施加在参考图中的已锁定人物上，不是新建一个 Shopkeeper。
- `Character Identity Anchor`、`Environment Anchor`、`Prop Detail Anchor`、`Visual Style Anchor` 及 `Highest/Second/Third/Fourth priority` 保持英文；Anchor 绑定的对象名称和描述仍使用中文。风格与质量描述使用英文。

**身份必须先于场景的原因**：角色参考图是脸部与人物本体的唯一可复用锚点。若先写场景、职业标签或剧情设定，模型容易把诸如 `Shopkeeper` 之类的通用词当成重新选角条件；先锁定每个有图角色，再描述空间、服饰与动作，文字就只会改变该人物的当前处境，不会生成另一个人。

---

## Step 2：Agent 直接编写任务表 JSON

Agent 使用 Write 工具直接编写 `视觉锚点_任务表.json`，保存到 `project/{项目名}/{剧集号}/分镜/视觉锚点_任务表.json`。

### 2.1 读取分镜内容并提取场清单与角色阶段

读取 `{剧集号}/分镜/分组/` 目录下的组文件，提取**场清单**：
- **详细模式**：`组{N}.json` — 从 `场号`、`场名称` 获取场信息，从 `通用设定`、`镜头列表` 获取该场的角色站位、关键动作、氛围信息
- **精简模式**：`组{N}.md` — 从正文获取叙事概述和分镜描述

> **场号 = 物理空间标识**：每个唯一场号对应一个物理空间。同一场号的多个组属于同一场。

**场清单提取规则**：

1. 遍历全部组文件，收集所有唯一 `场号` 及对应 `场名称`
2. 对每场，汇总该场全部组的以下信息：
   - **场景空间描述**：物理空间布局、建筑特征、家具陈设
   - **出场角色清单**：该场全部组中出现过的所有具名角色（去重）
   - **角色站位与调度**：角色在空间中的位置关系、朝向、关键走位
   - **关键动作与神态**：该场中最具代表性的角色动作与表情（选取能体现该场戏核的瞬间）
   - **氛围基调**：光线、色温、情绪氛围
   - **重要道具**：该场中出现的所有重要道具
3. 每场产出一条或多条锚点图任务（取决于角色阶段拆分结果）

### 角色阶段拆分（关键步骤）

对每场执行角色阶段拆分，确定该场需要几张锚点图。

**扫描范围**：该场全部组全部镜头，按播放顺序逐镜头扫描。

**拆分条件**（满足任一即在角色变化点拆分新阶段）：
- 有具名角色（有角色参考图的具名角色）从「不在画面」变为「在画面」（角色入场）
- 有具名角色从「在画面」变为「离开」（角色离场）

**不拆分的情况**：
- 无名背景人物增减（茶客来去、路人经过）— 不触发新阶段
- 同一组角色只换站位/动作 — 不触发新阶段
- 角色短暂出画又入画（如转身取物）— 不触发新阶段

**阶段编号**：同场阶段按播放顺序编号 A、B、C...（如场1拆分为 1A、1B；无拆分时仍为场1，不带字母后缀）。

**每个阶段选定一个锚点镜头**：
- 锚点镜头 = 该阶段中**戏核最匹配、站位最完整**的单个镜头
- 优先选取能体现该阶段戏剧核心的瞬间；站位最完整 = 该阶段在场角色在该镜头中位置关系最清晰
- 不是该阶段的第一个镜头，而是该阶段视觉信息最丰富的瞬间；通常选取该阶段第一个全景/建立镜头的时刻，或角色站位最完整、互动最关键的时刻

**阶段间依赖**：
- 同场阶段按播放顺序串行：阶段 A → 阶段 B → 阶段 C...
- 非首阶段锚点的 `images` 中增加 `{{PREV_OUTPUT}}`（Previous Phase Anchor），引用前一阶段锚点图输出作为空间参考，排在角色参考之后、场景参考之前
- 首阶段锚点无 `{{PREV_OUTPUT}}`；不同场的锚点图之间无依赖，可并行

**阶段内在场角色引用**（配合 common「何谓在场」表）：

1. 编写任务表前，先为**每个角色阶段**确定锚点镜头，再列出该阶段的`阶段在场表`：锚点镜头中在场的、且目录中有参考图的具名角色
2. 阶段出场集合中**每一个**有参考图的角色，都必须进入该 task 的 `images`（角色段）+ `cast` 字段 + Character Identity Anchor
3. **cast 严格等于锚点镜头在场角色**：不在该锚点镜头中的角色不进 `cast`，即使该角色在该阶段的其他镜头中出场

### 2.4 构建 Prompt（锚点版七段模板）

Prompt 使用 **English control shell + 中文 content layer**，七段顺序与公共规则见 common；`OPENING DECLARATION` 的第一段必须是 `IDENTITY LOCK — HIGHEST PRIORITY`，这是 prompt 的第一项实质内容，必须先于任何空间、镜头、动作或氛围描述。

> **编译器铁律（双语版）**：Prompt 编译器的职责是把英文模型控制层与中文分镜内容组装起来，**不是编剧，也不是翻译器**。角色名、角色关系、场景空间、动作、站位、神态、台词相关内容、道具内容、时代/剧情事实必须保留原中文；只复述原分镜已有的视觉信息，禁止新增道具、时间、动作、情绪事件、光线条件或场景。净化规则（11 类必删项）见 common「提示词净化规范」。

#### 段落 1：OPENING DECLARATION（IDENTITY LOCK）

```
IDENTITY LOCK — HIGHEST PRIORITY:
Reference priority (highest to lowest): Highest priority = referenced character identity and actor continuity; Second priority = environment; Third priority = props; Fourth priority = visual style. Identity wins every conflict: environment, props, style, historical appearance, and occupational archetype may serve the locked person, but may never replace that person's face or actor identity.

Actor continuity lock — for each referenced character:
Reference Image {N} character（{role_name_zh}角色） must remain recognizable as the same actor/person after all costume, hairstyle, pose, lighting, and environment changes.
Reference Image {N} character（{role_name_zh}角色） is the sole identity source for this referenced person; it is the same specific person shown in the image, not a newly generated interpretation.
Do not generate a generic {period_role_archetype}; do not use a historical or occupational archetype as a replacement casting.
If historical appearance conflicts with reference identity, preserve the reference identity and modify only wardrobe, hairstyle, and setting.
The face identity has absolute priority over role archetype, age description, or historical styling.
Referenced characters must look like the same people from the reference images, not similar-looking replacements.
Do not alter facial identity, facial structure, skin features, or body proportions.
Change only clothing and hairstyle required by the historical setting; wardrobe, hairstyle, and environment changes must not create a new person.

Create a professional cinematic film frame for {film_context}.

This is a visual anchor frame for {scene_name_zh}.
Generate exactly one image for this single frame only.
One single photographic still that fills the entire canvas.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.
```

> **具体示例（仅用于理解，写入实际 prompt 时要按任务替换）**：如果 `images[0]` 是掌柜参考图，身份/动作/站位第一次绑定应写成 `Reference Image 1 character（掌柜角色）...`，而不是以 `Shopkeeper` 开头。唐代掌柜场景须在逐角色身份锁后写入 `Do not generate a generic Tang Dynasty female shopkeeper.`（`{period_role_archetype}` 按角色替换）；该句是防止职业原型重新选角的硬约束，不是新角色描述。

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{film_context}` | 通用设定.风格 → English control term | a historical drama film / a Chinese ink-wash animation film |
| `{scene_name_zh}` | 场名称原文 | 春生茶肆·日/内 / 现代厨房 |
| `{role_name_zh}` | `cast` 中的角色名、角色职责和关系原文 | 掌柜 / 小二 |
| `{period_role_archetype}` | 为防止重新选角而使用的 English generic archetype；不是角色命名 | Tang Dynasty female shopkeeper |
| `{production_type}` | 风格参考文件 | a live-action film pre-production cinematic frame |
| `{neg_1/2/3}` | 风格参考文件 | concept art / illustration / a fantasy painting |

> **实际编写要求**：`{N}` 必须替换为 `images` 中的实际序号，`{role_name_zh}` 必须保留角色中文名。每个有参考角色都先写 `Reference Image N character（中文角色名/职责）` 的绑定式句子，再写动作、站位或神态；不得把 `Shopkeeper`、`Waiter` 等职业词作为首次选角标签。若本场 `cast=[]`，省略角色身份锁的逐角色行，但仍保留场景/风格参考和单帧声明。

#### 段落 2：SCENE CONTINUITY

```
SCENE CONTINUITY:

This is a visual anchor for {scene_name_zh} — the definitive spatial and atmospheric reference for this physical location.

Maintain strict continuity with reference materials:
- same identity for each referenced `cast` member, bound one-to-one to its paired character reference image
- the explicit current-scene costume and period context for each referenced person, without changing that person's identity
- same {environment_description_zh}
- same props
- same lighting atmosphere
- same {period_description_zh}
- no anachronistic costumes from other eras or dynasties
- unreferenced/background people remain unnamed, secondary, and period-appropriate; they are not identity anchors
- every unreferenced/background character is not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{scene_name_zh}` | 场名称原文 | 春生茶肆·日/内 |
| `{environment_description_zh}` | 通用设定.场景名称与空间内容原文 | 茶肆内，木柜台靠右，后墙为层架 |
| `{period_description_zh}` | 项目时代背景、时代/剧情事实原文 | 唐朝盛世 / 现代城市 |

> 非首阶段锚点须说明空间继承自前一阶段锚点（Previous Phase Anchor）。

#### 段落 3：REFERENCE IMAGE MAPPING（双语版）

> **双语映射规则**：映射块的 Anchor 类型和优先级保持英文；角色名、角色关系、场景名、空间描述、道具名、道具状态和剧情用途使用中文原文。中文绑定对象不是新选角标签，英文只包裹模型控制要求。
>
> **多角色多道具是常态**：**每个 `cast` 成员（含非焦点、局部入画、站位被点名）都必须有独立的 Character Identity Anchor 映射块**；无参考背景人物不写 Character Identity Anchor。每个重要道具都必须有独立的 Prop Detail Anchor 映射块。

**角色参考**（每个 `cast` 成员一个映射块，顺序与 `cast`/`images` 一致，主要角色在前）：
```
Image {N}: Character Identity Anchor — Highest priority
Reference Image {N} character（{role_name_zh}角色） is the sole identity source for this referenced person. This is the same specific person shown in the image, not a new casting.
Identity comes from the image only. Preserve facial identity, facial structure, skin features, and body proportions; do not add a text-derived replacement face.
Apply only the current-scene clothing, hairstyle, blocking, and action, without changing identity.
Even if only a hand, shoulder, or back is visible, keep the same referenced person; do not substitute a newly invented character.
```

> **不要写外貌重述段**：不要把 `Shopkeeper`、`Waiter` 等英文职业词，或年龄、脸型、发型、微笑、"现代穿越者"等通用语义扩写成新人物。只写参考图绑定、中文来源明确要求的服饰/职责/动作、关系，以及可见部位（`full body` / `face` / `hands only`）。后文若为可读性使用 `Shopkeeper (the same referenced person)`，必须明确它只是已绑定参考人物的简称，不能重新选角。

**场景参考**（通常一个，组内场景切换时可多个）：
```
Image {N}: Environment Anchor — Second priority
{scene_name_zh} — {场景空间中文描述：建筑、家具、材质、氛围与空间关系}。
Preserve: architecture, spatial layout, materials, atmosphere.
```

**道具参考**（每个重要道具一个映射块，按剧情重要性排序）：
```
Image {N}: Prop Detail Anchor — Third priority
{prop_name_zh} — {道具内容中文描述：材质、形状、纹理、工艺、当前状态与剧情用途}。
Preserve: shape, texture, craftsmanship, material.
```

**风格参考**：
```
Image {N}: Visual Style Anchor — Fourth priority
{brief English style description}.
Preserve: color palette, lighting mood, visual style.
```

**前阶段参考**（仅非首阶段，对应 `images` 中紧接角色之后的 `{{PREV_OUTPUT}}`）：
```
Image {N}: Previous Phase Anchor
Inherit the spatial layout, lighting direction, and set dressing established in the previous phase anchor; evolve only the blocking and action described in FRAME DETAIL.
```

#### 段落 4：FRAME DETAIL（双语版）

单帧描述。**必须包含 Purpose 和 Feeling 字段**。

> **影视级静帧质感要求**：锚点图虽为场级定调，但仍须包含完整的角色动作与神态描述。缺乏角色动作和神态的锚点图会对后续视频生成流程造成不良影响——视频导演依赖锚点图理解角色的表演基调和空间关系。
>
> **身份不在此处重建**：`IDENTITY LOCK` 已先锁定有参考角色。`Scene`、`Action`、`Performance` 只补充原分镜明确的中文空间、当前服饰、动作、站位、关系和表演；不得新增年龄、脸型、发型、微笑或"现代穿越者"等外貌/身份设定。无参考背景人物只写为无名、次要、符合时代的背景人物，并附英文视觉权重硬约束。

```
FRAME DETAIL:

Purpose:
{锚点图戏剧功能 → 中文，一句话说明此锚点图存在的理由}
{如：建立茶肆空间布局并锁定掌柜与茶客的站位。}

Feeling:
{情绪氛围与剧情感受 → 中文，一句话描述观众应感受到的情绪}
{如：重要消息宣布前短暂而安静的期待。}

Scene:
{场景空间描述 + 角色站位/调度 → 中文叙事，仅复述原分镜内容}
{必须描述完整的物理空间布局：建筑结构、家具陈设、道具摆放位置}
{必须描述每个 referenced cast 成员在空间中的位置关系：谁站在哪里、朝向谁、与其他角色的距离}
{每个 unreferenced/background character 除中文时代服化与动作/站位外，必须追加：not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus。无名侍者/信使等不得成为视觉中心、英雄式特写或主角权重。}
{这是锚点图的核心职责——锁定空间关系}

Action:
{角色动作 → 中文叙事；第一次出现角色时先写 Reference Image N character（中文角色名/职责）}
{多角色场景须按 cast 分角色描述动作，格式：Reference Image N character（角色名/职责）: 中文动作描述；无参考背景人物只写必要的远景/侧背动作，并附 not a referenced character... 硬约束}
{选取该场最具代表性的时刻的动作——能体现戏核的瞬间}
{禁止留空或仅写"站着"——须有具体中文动作姿态}

Performance:
{表演/微表情 → 中文叙事}
{多角色场景须按 cast 分角色描述表演；只使用原分镜明确的表演信息}
{必须为每个 referenced cast 成员写明源自分镜的表演状态；无参考背景人物不写主角式表情}
{禁止留空或仅写"面无表情"——须有具体且有来源的中文情绪状态}

Composition:
{景别 + 摄影机角度 → 英文电影语义}
{锚点图通常采用全景或中景，以展示完整空间和角色站位}

Camera feeling:
{摄影机运动 → 英文电影语义}
{锚点图通常为固定机位或缓慢推进}

Lighting:
{光线 → 英文}
{锚点图须锁定该场的光线基调}

Atmosphere:
{场级氛围与剧情感受 → 中文}
{如：重要但仍扎根于日常街市生活的仪式性揭示。}
```

> 景别/运镜/角度转换表见 common。**禁止焦距参数**。
>
> **Action 段不可省略**：即使角色处于"等待"状态，也要用中文描述具体身体语言（如"靠在柜台边、双臂交叠"而非"站着"）。**Performance 段不可省略**：每个在场角色都必须有神态描述——缺乏神态描述的锚点图会导致后续视频生成中角色表情空洞。

##### 精简模式（MD）处理

精简模式下镜头信息融入叙事段落（一段一镜）。Agent 需要：

1. 将同一物理场的全部叙事段落汇总为一条锚点图任务
2. 从散文中提取该场的空间布局、角色站位、关键动作、神态、光线等关键词
3. 叙事内容继续使用中文；仅将景别、机位、运镜等摄影控制词按转换表写成英文电影语义
4. 选取该场最具代表性的瞬间作为锚点图的"定格时刻"

#### 段落 5-7

TEXT POLICY、CINEMATIC QUALITY 模板与骨架见 common（CINEMATIC QUALITY 中间三行在锚点模式不翻译内容事实，中文内容留在前面内容段）。

**段落 7：AVOID（锚点版）** — 从风格文件提取 `avoid`，去重后只保留与单帧布局、时代、背景人物权重和空洞姿态相关的必要项，过滤字幕/烧字类条目，放在 prompt 末尾：

```
AVOID:

{style_avoid}

Compact final bans:
- No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean frame only.
- No anachronistic costumes for the period or background people.
- No unreferenced/background character becomes a main character or focal point.
- No empty or lifeless character poses; every referenced character needs a source-backed action and expression.
```

### 2.5 逐场匹配参考图

对每场，按 common「出场角色引用铁律」与道具/场景规则，从参考图清单选取文件：

1. **建场在场表**：读完整场全部组全部镜头 → 列出本场出现过的具名角色 → 与 `角色参考图/` 文件名匹配。缺参考的具名角色 → **硬终止**（common 龙套表）
2. **逐阶段 `cast`**：按「角色阶段拆分」对每阶段锚点镜头取在场有参考图角色；不是「焦点角色列表」——站位里提到的在场角色、只露手的角色全部计入
3. **组装 `images`**：`cast` 角色图（戏剧重要性排序，局部入画也要挂）→ `{{PREV_OUTPUT}}`（仅非首阶段）→ 本场物理空间场景图 → 重要道具（优先剧集级，否则全局基准且 `出现场合` 含本集）→ 风格图（始终最后）
4. **无图龙套**：按 common 处理；具名但无参考的角色硬终止

prompt 中 REFERENCE IMAGE MAPPING 与 `images` **一一对应**；Character Identity Anchor 个数 = 角色图个数 = `cast` 长度。锚点图引用本场场景参考图（同场一致）。

### 2.6 任务表 JSON 格式（锚点版）

一场一个或多个 task（取决于角色阶段拆分结果）；顶层为 `mode`/`model`/`output_path`/`tasks`（同 common）。完整结构见下方 2.7 示例。

锚点专属字段（公共字段见 common）：

| 字段 | 必填 | 说明 |
|------|------|------|
| `tasks[].id` | 是 | `"anchor-{场号}{阶段}"`，如 `"anchor-1A"`、`"anchor-2"` |
| `tasks[].group` | 是 | 阶段标识：同场阶段按播放顺序编号 A、B、C...（如 `"1A"`）；无阶段拆分时等于场号（如 `"2"`） |
| `tasks[].scene_name` | 是 | 场名称（中文，用于文件名和记录） |
| `tasks[].shot_range` | 是 | 该阶段锚点覆盖的镜头范围，如 `"1-3"`；同场各阶段范围不得重叠、按播放顺序递增 |
| `tasks[].depends_on` | 否* | 同场前一阶段任务 id（*首阶段无；非首阶段必填）。运行时其成图 URL 替换 `images` 中的 `{{PREV_OUTPUT}}` |
| `tasks[].filename` | 是 | `"锚点_场{场号}{阶段}_{阶段名/场景名}.png"`，如 `"锚点_场1A_断供报信.png"` |
| `tasks[].prompt` | 是 | 七段双语单帧 prompt：OPENING 第一项为 actor continuity `IDENTITY LOCK`，随后才是场景/动作 |

> 1. 每场按角色阶段拆分生成一条或多条 task
> 2. 同场阶段按播放顺序 `depends_on` 串行；场间无依赖可并行提交
> 3. 无阶段拆分时该场仅一个 task（等价旧 batch 单场一张，向后兼容）

### 2.7 完整示例

2 场任务表（LiveAction，16:9）：场1 拆分双阶段（1A、1B 串行，非首阶段含 `{{PREV_OUTPUT}}`），场2 无拆分：

```json
{
  "mode": "sequential",
  "model": "nano-banana-2",
  "output_path": "project/荼荼茶业-古装/EP04/分镜/视觉锚点",
  "tasks": [
    {
      "id": "anchor-1A",
      "scene": "1",
      "group": "1A",
      "scene_name": "春生茶肆·日/内",
      "shot_range": "1-3",
      "filename": "锚点_场1A_断供报信.png",
      "cast": ["掌柜", "茶客"],
      "prompt": "<双语 7 段 prompt：须包含 actor continuity lock 与下方示例的绑定式角色写法>",
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
      "id": "anchor-1B",
      "scene": "1",
      "group": "1B",
      "scene_name": "春生茶肆·日/内",
      "shot_range": "4-7",
      "depends_on": "anchor-1A",
      "filename": "锚点_场1B_立规交锋.png",
      "cast": ["掌柜"],
      "prompt": "<双语 7 段 prompt：先锁 Reference Image 1 character（掌柜角色），再写中文场景/动作/神态；SCENE CONTINUITY 说明空间继承自前一阶段锚点>",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "{{PREV_OUTPUT}}",
        "project/荼荼茶业-古装/EP04/场景参考图/茶馆.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    },
    {
      "id": "anchor-2",
      "scene": "2",
      "group": "2",
      "scene_name": "春生茶肆门口·日/外",
      "shot_range": "1-2",
      "filename": "锚点_场2_茶肆门口.png",
      "cast": ["掌柜"],
      "prompt": "<双语 7 段 prompt：先锁 Reference Image 1 character（掌柜角色），再写中文场景/动作/神态>",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "project/荼荼茶业-古装/EP04/场景参考图/茶肆门口.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    }
  ]
}
```

**双语占位 prompt 示例（仅展示编写结构，不可原样提交）**：

```text
IDENTITY LOCK — HIGHEST PRIORITY:
Reference priority (highest to lowest): Highest priority = referenced character identity and actor continuity; Second priority = environment; Third priority = props; Fourth priority = visual style. Identity wins every conflict: environment, props, style, historical appearance, and occupational archetype serve the locked person and never replace the face.
Reference Image 1 character（掌柜角色） must remain recognizable as the same actor/person after all costume, hairstyle, pose, lighting, and environment changes.
Reference Image 1 character（掌柜角色） is the sole identity source for this referenced person; it is the same specific person shown in the image, not a newly generated interpretation.
Reference Image 2 character（茶客角色） must remain recognizable as the same actor/person after all costume, hairstyle, pose, lighting, and environment changes.
Reference Image 2 character（茶客角色） is the sole identity source for this referenced person; it is the same specific person shown in the image, not a newly generated interpretation.
Do not generate a generic Tang Dynasty female shopkeeper. Do not use a historical or occupational archetype as a replacement casting.
For Reference Image 2 character（茶客角色）, do not generate a generic Tang Dynasty tea guest; use the referenced person instead.
（……其余身份锁句同段落 1 模板：historical appearance conflicts / face identity has absolute priority / not similar-looking replacements / Do not alter facial identity, facial structure, skin features, or body proportions / must not create a new person……）
Create a professional cinematic film frame for a historical drama film.
This is a visual anchor frame for 春生茶肆·日/内. Generate exactly one image for this single frame only. One single photographic still that fills the entire canvas.

SCENE CONTINUITY:
This is a visual anchor for 春生茶肆·日/内 — the definitive spatial and atmospheric reference for this physical location.
Maintain strict continuity with reference materials: same identity for the referenced cast member; same 茶肆内、右侧木柜台和后墙层架; same props; same lighting atmosphere; same 唐朝盛世. Every unreferenced/background character is not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus.

REFERENCE IMAGE MAPPING:
Image 1: Character Identity Anchor — Highest priority
Reference Image 1 character（掌柜角色） is the sole identity source.
Image 2: Character Identity Anchor — Highest priority
Reference Image 2 character（茶客角色） is the sole identity source. 茶客坐在左侧茶桌旁。
Image 3: Environment Anchor — Second priority
春生茶肆·日/内 — 茶肆空间，右侧木柜台，茶桌与层架。
Image 4: Prop Detail Anchor — Third priority
茶罐 — 青瓷圆腹罐，釉面裂纹，罐内盛放新茶。
Image 5: Visual Style Anchor — Fourth priority
Live-action historical drama style, controlled cinematic lighting, realistic material texture, high image quality.

FRAME DETAIL:
Purpose:
建立茶肆空间布局并锁定角色站位。
Feeling:
重要消息宣布前短暂而安静的期待。
Scene:
茶肆内，右侧为木柜台，后墙是层架；Reference Image 1 character（掌柜角色）站在右侧柜台后，茶客坐在左侧茶桌旁，两人保持分镜规定的相对位置。
Action:
Reference Image 1 character（掌柜角色）站在右侧柜台后擦拭茶杯。Reference Image 2 character（茶客角色）坐在左侧茶桌旁端起茶杯。
Performance:
Reference Image 1 character（掌柜角色）嘴角带着分镜规定的克制笑意。Reference Image 2 character（茶客角色）抬眼望向掌柜，保持分镜规定的神态。
Composition:
Wide shot, eye-level, balanced spatial blocking.
Camera feeling:
Static camera, locked-off.
Lighting:
Soft directional cinematic lighting, controlled color temperature, realistic material response.
Atmosphere:
茶肆日常中即将发生重要宣布的安静期待。

TEXT POLICY:
Hard ban on burned-in graphics (non-negotiable): No subtitles, captions, lower-thirds, or title cards. No on-screen dialogue text or lyric text. No watermarks, logos, shot numbers, timecode, or UI chrome. Spoken lines exist only as audio in the final edit.
Diegetic in-world text only when the scene itself contains it; preserve original Chinese characters, do not generate pinyin, and do not replace Chinese characters with Latin letters.

CINEMATIC QUALITY:
Live-action historical drama, restrained cinematic color palette, controlled lighting, realistic wood and porcelain material texture, high-resolution image quality.
Camera principles: grounded composition, natural depth, clean photographic detail.

AVOID:
No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean frame only.
No anachronistic costumes for the period or background people.
No unreferenced/background character becomes a main character or focal point.
No empty or lifeless character poses; every referenced character needs a source-backed action and expression.
```

> **示例要点**：1A 为首阶段（无 `depends_on`/`{{PREV_OUTPUT}}`）；1B `depends_on: "anchor-1A"`，`{{PREV_OUTPUT}}` 在角色之后、场景之前；场2 单阶段无依赖；同场 `shot_range`（`1-3`/`4-7`）连续不重叠；cast 长度 = 角色图数 = Character Identity Anchor 数；Action/Performance 必须为每个角色写明动作与神态。

---

## Step 3/4：执行与校验

公共流程见 common（Step 3 执行 / Step 4 校验）。锚点模式要点：

- 校验命令：`python validate_task_table.py --check "视觉锚点_任务表.json" --mode anchor`
- 执行时**场内阶段串行**：同场非首阶段锚点在 `depends_on` 指向的前一阶段成图后提交，其 `{{PREV_OUTPUT}}` 由运行时替换为前阶段成图 URL；**场间并行**；任一帧 `failed` 不影响其他场，记录事件
- 无阶段拆分的单阶段场在 sequential 模式下等价于独立任务，可与其他场并行提交

锚点专属校验项（公共项见 common）：

1. 每个任务 `scene_name`、`group`（阶段标识）、`shot_range` 必填；`shot_range` 同场不重叠、按播放顺序递增
2. `depends_on` 仅限同场阶段链：非首阶段指向同场前一阶段任务 id；首阶段无 `depends_on` 且不得含 `{{PREV_OUTPUT}}`
3. `{{PREV_OUTPUT}}` 排在角色参考之后、场景参考之前；锚点模式禁止省略场景参考图
4. 有角色参考时，`IDENTITY LOCK — HIGHEST PRIORITY` 位于 `SCENE CONTINUITY` 之前，逐一写明 `Reference Image N character（中文角色名/职责）` 是该角色 `sole identity source` 与 actor continuity lock；包含脸部身份绝对优先、历史冲突只改 wardrobe/hairstyle/setting、同一 actor/person 和非替换人物语义；不得用 `ALL characters` 混合 referenced 与 unreferenced/background characters
5. 每个 unreferenced/background character 须含 common 所列英文降权硬约束
6. FRAME DETAIL 的 Action / Performance 段不得为空（每个 cast 角色须有动作与神态描述）
