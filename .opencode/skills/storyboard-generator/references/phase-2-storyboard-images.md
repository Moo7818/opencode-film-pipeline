# 阶段二：episode_storyboard_images — 分镜图绘制（storyboard_images 模式）

**独立阶段（仅当 `meta_query(scope=config)` 返回的 `config.reference_image_mode=storyboard_images` 时执行）**：此阶段在 `episode_storyboard_script`、`episode_character_ref`、`episode_prop_ref`、`episode_scene_ref` 之后执行，分镜图可参考剧集级场景/道具变化。`reference_image_mode=visual_anchor`（默认）时改为执行视觉锚点图绘制（见 `phase-2-visual-anchors.md`）；`reference_image_mode=none` 时跳过所有参考图生成。

> 执行前提、参考图收集、排序优先级、出场引用铁律、龙套时代锚、单帧/禁字幕、风格匹配、文字检测、净化规范、七段公共规则、任务表公共字段、执行与校验流程见 **`references/phase-2-common.md`**（两模式单一事实源）。本文档只写分镜图模式专属内容。

## 参考帧模式（Reference-Frame Sequential）— 唯一合法模式

> 目标不是「每帧独立出图」，而是：**场内每一帧的成图，成为下一帧的主空间连续参考（参考帧）**，使同物理空间内角色身份、布景几何、光影方向、服装发式在整条链上可继承。Prompt 使用**英文**生成。

| 规则 | 说明 |
|------|------|
| mode | 必须 `"sequential"`，禁止 batch / 省略 mode |
| 场 | = 物理空间连续单元（与分镜脚本 `场号` 一致） |
| 场内 | 全部帧（跨组）按播放顺序形成**一条** `depends_on` 链；非首帧 `images` 含 `{{PREV_OUTPUT}}` |
| 执行 | 前帧 `completed` 拿到 `image_url` → 替换下一帧 `{{PREV_OUTPUT}}` → 再 submit |
| 场间 | 不同 `scene` 无依赖，首帧可并行 |

**禁止**：同场多帧并行提交、断链（中间帧无 depends_on）、跨物理场串 depends_on、任务表无 id/scene/group、用静态资产冒充前帧。

---

## Step 2：Agent 直接编写任务表 JSON

Agent 使用 Write 工具直接编写 `分镜图_任务表.json`，保存到 `project/{项目名}/{剧集号}/分镜/分镜图_任务表.json`。

### 2.1 读取分镜内容

读取 `{剧集号}/分镜/分组/` 目录下的组文件：
- **详细模式**：`组{N}.json` — 从 `场号`、`场名称` 获取场信息，从 `组叙事概述`、`通用设定`、`镜头列表` 获取组信息
- **精简模式**：`组{N}.md` — 从正文获取叙事概述和分镜描述（一段一镜）

> **场号 = 物理空间串行链 ID**：从组文件读取 `场号` → 写入任务 `scene`。同一物理场的全部组全部帧必须连成**一条** depends_on 链（组1最后一镜 → 组2第一镜）。若发现分镜脚本把同一物理空间拆成多个场号，应在编写任务表前向 orchestrator 回报，而不是默默按错误场号断链。

### 组内在场角色连续引用

> **根因案例（EP06 组1）**：镜1 只露掌柜执笔手（无正脸）→ 镜2 焦点切到小二、画面仍有掌柜 → 任务只引小二、不引掌柜 → 掌柜造型漂移。前帧不能代替角色锁——前帧可能根本没拍到脸。

1. 编写任务表前，先为**每一组**列出`组在场表`：本组所有镜中曾出场的、且目录中有参考图的具名角色
2. 对每一帧：取「本帧出场集合」= 按 common「何谓在场」表扫描该镜的结果
3. 本帧出场集合中**每一个**有参考图的角色，都必须进入该 task 的 `images`（角色段）+ `cast` 字段 + Character Identity Anchor
4. 镜1 未露脸、镜2 仍在场 → 镜2 **仍须**引用该角色参考
5. 仅当该角已明确离场（出画且站位不再提及）才可从后续帧去掉其参考

### 2.4 构建 Prompt（分镜图版七段模板）

Prompt 使用**英文**生成，七段顺序与公共规则见 common。

> **编译器铁律（翻译版）**：Prompt 编译器的职责是将分镜内容**翻译**为图像模型可理解的英文描述，**不是编剧**。禁止新增原分镜中不存在的道具、时间、动作、情绪事件、光线条件或场景。仅复述和翻译原分镜已有的视觉信息。净化规则（11 类必删项）见 common「提示词净化规范」；本模式特有残留示例：`The immediately preceding frame ... (may be prior group)`（占位符机制解释，删机制留 `Image N: Previous Frame Anchor` 标签）。

#### 段落 1：OPENING DECLARATION

两版共用首尾（`Create a professional cinematic film frame for {film_context}.` 起头；`Generate exactly one image for this single frame only.` + 单帧画布长声明 `One single photographic still that fills the entire canvas — not a multi-panel layout, not a grid, not a collage, not a comic strip, not a storyboard sheet, not a contact sheet, not a split-screen.` + `No borders or gutters dividing the image into tiles.` + `This is {production_type}, not {neg_1}, not {neg_2}, not {neg_3}.` 收尾），差异仅在中段定位：

**首帧**中段：
```
This is the first frame of {group_name}.
```

**后续帧**（有 `depends_on`，参考帧模式）中段：
```
This is a subsequent frame in the same continuous physical scene, directly following the previous frame.
The previous frame is provided as the PRIMARY spatial continuity reference (Previous Frame Anchor).
Evolve the shot from that reference; do not restart the scene from scratch.
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{film_context}` | 通用设定.风格 → 英文 | a historical drama film / a Chinese ink-wash animation film |
| `{group_name}` | 组名 → 英文 | Group 1 / Sequence A |
| `{production_type}` | 风格参考文件 | a live-action film pre-production cinematic frame |
| `{neg_1/2/3}` | 风格参考文件 | concept art / illustration / a fantasy painting |

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

> 每帧的叙事上下文由 FRAME DETAIL 段的 Purpose 字段充分提供，禁止序列节拍描述（公共规则见 common）。

#### 段落 3：REFERENCE IMAGE MAPPING（英文版）

> **全部使用英文名称**：映射块中的角色名、场景名、道具名必须翻译为英文（如"掌柜"→"Shopkeeper"、"茶馆"→"Tea House"）。中文名称会干扰模型理解。

**角色参考**（每个 `cast` 成员一个映射块，顺序与 `cast`/`images` 一致，主要角色在前）：
```
Image {N}: Character Identity Anchor
{character_name (English)} — {detailed English description: identity, clothing, hair, age, body type, and role in this frame; if only hands/back visible, still describe full identity from the reference sheet}.
Preserve: facial identity, appearance, costume, hair styling, age, body proportions.
Even if only a hand, shoulder, or back is visible in this frame, match the reference identity and costume exactly.
```

> **描述要具体**：不要只写 "The shopkeeper"，要写出可见的外观特征（性别、年龄段、服装款式与颜色、发型、体型），并写明本帧可见部位（full body / face / hands only）。
>
> **非焦点也要锚**：小二是说话焦点、掌柜在画内被注视 → 仍须两个 Anchor。
>
> **多角色示例**：
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

**道具参考**（每个重要道具一个映射块，按剧情重要性排序）：
```
Image {N}: Prop Detail Anchor
{prop_name (English)} — {detailed English description: material, shape, texture, craftsmanship, and role in the scene}.
Preserve: shape, texture, craftsmanship, material.
```

> **描述要具体**：不要只写 "A tea canister"，要写出材质、颜色、形状、表面纹理、工艺风格。
>
> **多道具示例**：
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

#### 段落 4：FRAME DETAIL（英文版）

单帧描述。**必须包含 Purpose 和 Feeling 字段**。

```
FRAME DETAIL:

Purpose:
{镜头戏剧功能 → 英文，一句话说明此镜头存在的理由}

Feeling:
{情绪氛围 → 英文，一句话描述观众应感受到情绪}
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

> 景别/运镜/角度转换表见 common。**禁止焦距参数**。
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

#### 段落 5-6

TEXT POLICY、CINEMATIC QUALITY 模板见 common（本模式将通用设定中文描述转为英文电影语义；`{prop_name}` 用英文名）。

#### 段落 7：AVOID（分镜图版）

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

### 2.5 逐帧匹配参考图

对每个组的每个镜头（帧），按 common「出场角色引用铁律」与道具/场景规则，从参考图清单选取文件：

1. **建组在场表**：读完整组全部镜头 → 列出本组出现过的具名角色 → 与 `角色参考图/` 文件名匹配。缺参考的具名角色 → **硬终止**（common 龙套表）
2. **逐帧 `cast`**：按「何谓在场」表对本帧扫描得到 `cast`（中文名列表）；不是「焦点角色列表」——站位里提到的在场角色、只露手的角色全部计入
3. **组装 `images`**：`cast` 角色图（戏剧重要性排序，局部入画也要挂）→ `{{PREV_OUTPUT}}`（仅非首帧，紧接全部角色之后）→ 本场物理空间场景图（同场全帧共用）→ 本帧重要道具（优先剧集级，否则全局基准且 `出现场合` 含本集）→ 风格图（始终最后）
4. **无图龙套**：按 common 处理；无名路人不进 `cast`/`images`，在 FRAME DETAIL 用时代锚定英文描写，受 AVOID 错代禁令约束

prompt 中 REFERENCE IMAGE MAPPING 与 `images` **一一对应**；Character Identity Anchor 个数 = 角色图个数 = `cast` 长度。同一 `scene` 内所有帧引用同一场景参考图。

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

### 2.6 任务表 JSON 格式（分镜图版）

每帧一个 task；顶层为 `mode`/`model`/`output_path`/`tasks`（同 common）。完整结构见下方 2.7 示例（首帧去掉 `depends_on` 与 `{{PREV_OUTPUT}}`，顺序为角色→场景→道具→风格）。

分镜图专属字段（公共字段见 common）：

| 字段 | 必填 | 说明 |
|------|------|------|
| `tasks[].id` | 是 | `"{组号}-{镜号}"`，如 `"1-1"`、`"1-2"`、`"2-1"` |
| `tasks[].group` | 是 | 组号字符串 |
| `tasks[].depends_on` | 场首帧省略 | 必须指向**同场播放顺序上的直接前一帧** id |
| `tasks[].filename` | 是 | `"组{N}_镜{M}.png"` |
| `tasks[].prompt` | 是 | 单帧英文 prompt（7 段；含单帧画布声明、禁字幕 TEXT POLICY、强化 AVOID） |
| `tasks[].images` | 是 | 非首帧必须含 `"{{PREV_OUTPUT}}"` 且位于**全部角色之后、风格之前** |

> **场级参考帧链（完整）**：
> 1. 按 `scene` 分组；组内按组号、镜号排序
> 2. 每场排序后第 1 个 task：无 `depends_on`，无 `{{PREV_OUTPUT}}`
> 3. 第 2..N 个 task：`depends_on` = 排序后前一个 task 的 `id`，且 `images` 含 `{{PREV_OUTPUT}}`
> 4. 跨组不断链：组2镜1 的 `depends_on` = 组1最后一镜
> 5. 不同 `scene` 之间禁止 `depends_on`

### 2.7 完整示例

1 场（含 1 个组、2 帧）的任务表（LiveAction，16:9），展示多角色（2 角色）+ 多道具（2 道具）场景：

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
      "prompt": "(完整 7 段英文 prompt：OPENING 含单帧画布声明；TEXT POLICY 含 Hard ban on burned-in graphics；AVOID 含 multi-panel + subtitle；REFERENCE 含 2 个 Character Identity Anchor…)",
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

> **示例要点**：首帧（1-1）`cast` 2 人 + 角色图 2 + 场景 + 道具 + 风格，无 `{{PREV_OUTPUT}}`；后续帧（1-2）`cast` 仍含在场两人，顺序 角色… → `{{PREV_OUTPUT}}` → 场景 → 道具… → 风格；**不得**因镜2 焦点切到茶客而丢掉掌柜参考（EP06 反例）；1-2 把 1-1 成图当 live set，在景别/动作上演化而不是重抽；若还有组2，下一镜 `depends_on` 必须是组1最后一镜 id；cast 长度 = 角色图数 = Character Identity Anchor 数，MAPPING 总数 = images 长度（含 Previous Frame Anchor）。

---

## Step 3/4：执行与校验

公共流程见 common（Step 3 执行 / Step 4 校验）。分镜图模式要点：

- 校验命令：`python validate_task_table.py --check "分镜图_任务表.json" --mode storyboard`
- 执行时**场内串行**：同场下一帧必须等上一帧 `completed` 且拿到可访问的 `image_url`（COS）后，**字面替换** `images` 里的 `{{PREV_OUTPUT}}` 为该 URL 再 submit；替换后调用 MCP 前仍须把其余本地路径解析为绝对路径
- **场间并行**：不同 `scene` 的首帧可交叉提交
- 任一帧 `failed`：**停止该场后续链**，记录事件；不跳过失败帧继续（否则参考帧断裂）

分镜图专属校验项（公共项见 common）：

1. 每个任务 `id`（`{组号}-{镜号}`）、`group`、`scene` 必填；不得含 `shot_range`/`scene_name`（属于锚点表字段）
2. 场级链完整：同 `scene` 按组号/镜号排序后，第1帧无 depends_on，其后每一帧 depends_on 等于直接前帧 id（跨组不断链）
3. `{{PREV_OUTPUT}}` 不得在风格之后、不得在全部角色之前
4. 后续帧 SCENE CONTINUITY 应体现参考帧/previous frame 语义
