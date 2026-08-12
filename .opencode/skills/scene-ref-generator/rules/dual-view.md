# 内景外景双视图流程（Dual-View）

> 共享定义（参考图遵循原则、缺省值原则、场景间差异化原则、风格类型自适应、视觉风格提取）见 `rules/common.md`。
> 本模式产出任务表 JSON，不直接生图——生图由 Art-director Agent 执行。

## 与全景模式（Panoramic）的区别

| 维度 | 全景模式（common.md + global.md） | 双视图模式（本文件） |
|------|----------------------------------|---------------------|
| 每场景产出 | 1 张（左俯瞰 + 右二宫格） | 2 张（内景 + 外景） |
| 布局 | 复合排版，一张图包含俯瞰 + 正面 + 背面 | 独立单帧，每张图一个完整画面 |
| aspectRatio | 2:1 | 16:9 |
| imageSize | 1K | 4K |
| model | gpt-image-2 | gpt-image-2-vip |
| Prompt 语言 | 纯中文 | 英文控制层 + 中文内容层（参考视觉锚点图模板） |
| 适用场景 | 需要空间布局总览 | 需要高质量内/外景氛围参考 |

## 触发条件

- 阶段：全局视觉资产生成（global_scene_tasks）
- 输入：全局设定 + 场景设定 + 前期采样（场景/风格）
- 产出文件名：`{场景名}_内景.png`、`{场景名}_外景.png`

## 执行步骤

### 步骤 1：收集输入文件

| 文件 | 用途 |
|------|------|
| `project/{项目名}/全局依赖/全局设定.md` | 画风参考、色调色温、视觉语言标准 |
| `project/{项目名}/全局依赖/场景设定/场景设定.md` | 场景索引清单 |
| `project/{项目名}/全局依赖/场景设定/具体设定/{场景名}.md` | 各场景的详细设定 |
| `project/{项目名}/前期采样/场景/{场景名}*.png` | 场景采样图（可选，决定是否作为参考图） |
| `project/{项目名}/前期采样/风格/*.png` | 风格参考图（所有场景共用） |

### 步骤 2：确定场景清单

从 `场景设定/场景设定.md` 的场景清单表中提取所有需要生成的场景。每个场景生成 2 个 task（内景 + 外景），**task 数量 = 场景数量 x 2**。

### 步骤 3：模式判断

与全局模式一致，对每个场景检查 `前期采样/场景/` 下是否存在以该场景名命名的图片文件：

| 模式 | 条件 | 参考图 |
|------|------|--------|
| **模式 A** | `前期采样/场景/{场景名}*.png` 存在 | 场景采样图（images[0]）+ 风格参考图 |
| **模式 B** | `前期采样/场景/{场景名}*.png` 不存在 | 仅风格参考图 |

### 步骤 4：提取视觉风格

按 `rules/common.md` 的「视觉风格提取」规则，从全局设定中提取 `{style_desc}`。

同时从全局设定中提取以下风格参数（用于英文控制层）：

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

### 步骤 5：构建 Prompt

双视图模式使用**英文控制层 + 中文内容层**的双语 Prompt 结构，参考分镜 skill 视觉锚点图模板，但移除角色身份锁定（IDENTITY LOCK），聚焦于场景空间环境本身。

每个场景生成 2 个 prompt：内景 prompt 和外景 prompt。

#### 5.1 内景 Prompt 模板（7 段结构）

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
{景别 + 摄影机角度 → 英文电影语义，如 wide shot, eye-level}

Camera feeling:
{摄影机运动 → 英文电影语义，如 static camera, locked-off}

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
- No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean frame only.
- No anachronistic costumes or elements for the period.
- No character focus; this is a scene environment reference, not a character portrait.
- No empty or lifeless space; every interior must feel lived-in and atmospheric.
```

#### 5.2 外景 Prompt 模板（7 段结构）

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
{景别 + 摄影机角度 → 英文电影语义，如 establishing shot, eye-level}

Camera feeling:
{摄影机运动 → 英文电影语义，如 static camera, slow dolly forward}

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
- No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean frame only.
- No anachronistic costumes or elements for the period.
- No character focus; this is a scene environment reference, not a character portrait.
- No empty or lifeless space; every exterior must feel atmospheric and grounded.
```

### 步骤 6：生成任务表 JSON

```json
{
  "model": "gpt-image-2-vip",
  "tasks": [
    {
      "prompt": "SCENE REFERENCE FRAME — INTERIOR\n\nCreate a professional cinematic interior scene reference frame for {film_context}.\n\nThis is an interior scene reference image for {scene_name_zh}...",
      "model": "gpt-image-2-vip",
      "imageSize": "4K",
      "aspectRatio": "16:9",
      "filename": "{场景名}_内景.png",
      "images": [
        "project/{项目名}/前期采样/场景/{场景名}.png",
        "project/{项目名}/前期采样/风格/{风格文件}.png"
      ]
    },
    {
      "prompt": "SCENE REFERENCE FRAME — EXTERIOR\n\nCreate a professional cinematic exterior scene reference frame for {film_context}.\n\nThis is an exterior scene reference image for {scene_name_zh}...",
      "model": "gpt-image-2-vip",
      "imageSize": "4K",
      "aspectRatio": "16:9",
      "filename": "{场景名}_外景.png",
      "images": [
        "project/{项目名}/前期采样/场景/{场景名}.png",
        "project/{项目名}/前期采样/风格/{风格文件}.png"
      ]
    }
  ],
  "output_path": "project/{项目名}/全局依赖/场景设定/场景参考图/"
}
```

**自检清单：**
- [ ] tasks 数量等于场景数量 x 2（每个场景有内景和外景各 1 个 task）
- [ ] 内景 task 的 filename 为 `{场景名}_内景.png`，外景 task 的 filename 为 `{场景名}_外景.png`
- [ ] style_desc 及英文风格参数已从全局设定和风格参考文件提取
- [ ] 每个 prompt 包含 7 段结构：DECLARATION / CONTINUITY / MAPPING / FRAME DETAIL / TEXT POLICY / CINEMATIC QUALITY / AVOID
- [ ] prompt 中英文控制层正确，中文内容层保留原始中文（场景名、空间描述、氛围等）
- [ ] **prompt 禁止出现剧情角色描述**（如郑和、一岛等人物外观、服饰、动作）
- [ ] **prompt 包含 "No character focus" 声明**
- [ ] **prompt 包含 "No multi-panel, grid, collage" 禁令**
- [ ] 内景 prompt 聚焦室内空间：建筑结构、家具陈设、材质纹理、室内光线
- [ ] 外景 prompt 聚焦室外空间：建筑外观、周边环境、街道/地形、天际线、天气
- [ ] 内景与外景 prompt 之间存在差异化，不重复相同描述
- [ ] 不同场景之间的 prompt 存在差异化
- [ ] **images 数组中不包含角色参考图或道具参考图**
- [ ] model 固定为 `gpt-image-2-vip`，imageSize 固定为 `4K`，aspectRatio 固定为 `16:9`

### 步骤 7：Schema 校验

1. `validate_top_level(data)` 校验顶层字段
2. `validate_tasks_dual_view(tasks)` 校验任务列表

两个函数均返回空列表则通过。

### 步骤 8：输出完成提示

```
双视图场景参考图任务表已生成，等待 Art-director 执行生图
- {N} 个场景，已生成 {N*2} 个 task（内景 {N} + 外景 {N}）
```

## 参考图上传顺序

### 模式 A（有场景采样图）

| 位置 | 内容 |
|------|------|
| images[0] | 场景采样图（`前期采样/场景/{场景名}*.png`） |
| images[1] | 风格参考图（`前期采样/风格/*.png`） |

### 模式 B（无场景采样图）

| 位置 | 内容 |
|------|------|
| images[0] | 风格参考图（`前期采样/风格/*.png`） |

**绝对禁止**加入角色参考图（`角色设定/角色参考图/`）或道具参考图（`道具设定/道具参考图/`）下的任何文件。

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
