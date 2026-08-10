# 共享定义

三个定位模式（global / episode / group）共用以下规范。差异点在各自主文件中说明。

## 角色参考图硬约束

- 一个角色 = 一个 task。每个角色只生成 1 个 task，该 task 的 prompt 描述 **一张网格图内包含多个视图**。
- **绝对禁止**为不同角度分别创建独立 task。
- 此约束适用于 global 模式（Tier 1 选角 + Tier 2 定妆/新妆造）。episode 模式不再生成角色参考图，仅做妆造匹配（见 `rules/episode.md`）。群像使用群像模板。

### 构图模式（两选一）

| 模式 | 状态 | 视图数 | aspectRatio | 构图说明 |
|------|------|--------|-------------|---------|
| **竖版三视图（默认）** | 默认 | 3 | **9:16** | 上方 50%：半身近景肖像（头顶至肘部）；下方 50%：全身正面 + 背面两视图并排（无头部） |
| 横版七视图（备选） | 备选 | 7 | 16:9 | 左半侧半身近景 + 右上表情三连图 + 右下全身三视图 |

> 默认使用竖版三视图模式。仅当角色设定或调用方明确要求横版七视图（如需要表情参考）时，才切换为备选模式。

## 缺省值原则（重要）

AI 图像模型对某些视觉属性有统计偏见——如果 prompt 不明确声明，模型会按训练数据"自动填空"（例如男性历史人物默认加胡须、古代人物默认苍老）。**必须对每个可能被默认填充的视觉特征做显式声明**：若不存在则明确否定，若存在则具体描述。

关键防范列表（必需在 prompt 的 `{appearance}` 段中显式声明的属性）：

| 属性 | 风险 | 正确做法 |
|------|------|---------|
| 胡须 | 男性角色易被默认添加胡须 | 无胡须则写"clean-shaven, no facial hair"；有则描述类型（goatee / full beard 等） |
| 皱纹/年龄感 | 年龄未明确时模型默认偏大 | 按角色设定明确写"smooth skin without wrinkles"或相应描述 |
| 发型 | 历史角色易被默认古装发型 | 显式描述发型，不依赖模型默认 |
| 体态 | 男性角色易被默认壮硕 | 按角色设定描述（slim / athletic / sturdy 等）|
| 服装文字 | 模型可能自动在服装上生成文字/logo | 模板末尾已固定追加"text, labels, captions, logos"到 Avoid 段，无需额外处理 |

## 风格参考按需注入规则

角色设定中的「视觉参考风格」字段可能指定具体动画/游戏风格。Agent 应按需判断：

### 判定逻辑

1. 从角色设定文件的「视觉参考风格」或整体描述中提取风格关键词
2. 匹配下表「风格匹配表」中的关键词列
3. 若匹配成功 → 加载 skill 内置 `reference/{风格名}.md` 参考文件
4. 若角色设定未指定视觉参考风格 → 加载 `reference/PhotoRealistic.md`（默认写实风格）

### 风格匹配表

| 风格名 | 关键词 | reference 文件 |
|--------|--------|---------------|
| PhotoRealistic | 真人摄影、写真、真人实拍、照片级真实、live-action、historical drama | `reference/PhotoRealistic.md` |
| 3DCartoon | 3D卡通、皮克斯、迪士尼、Pixar、3D stylized、三维动画 | `reference/3DCartoon.md` |
| Ghibli | 吉卜力、宫崎骏、龙猫、千与千寻、ghibli | `reference/Ghibli.md` |
| GTAV | GTA V、Rockstar、侠盗猎车手、洛圣都、gta_v | `reference/GTAV.md` |

> 无明确关键词匹配时默认使用 `PhotoRealistic`。

### 注入规则

加载参考文件后，按以下规则从 front-matter 提取参数注入 Prompt 模板：

| 模板参数 | 注入来源 | 说明 |
|---------|---------|------|
| `{opening_decl}` | front-matter `opening_decl` | 开篇类型声明 |
| `{opening_type}` | front-matter `opening_type` | 正面类型确认 |
| `{opening_neg_1}` | front-matter `opening_neg_1` | 否定消歧项 1 |
| `{opening_neg_2}` | front-matter `opening_neg_2` | 否定消歧项 2 |
| `{opening_neg_3}` | front-matter `opening_neg_3` | 否定消歧项 3 |
| `{layout_portrait_style}` | front-matter `layout_portrait_style` | 左侧半身照风格定位 |
| `{output_format}` | front-matter `output_format` | 整体输出格式定位 |
| `{photo_style}` | front-matter `photo_style` | 摄影/渲染风格 |
| `{lighting}` | front-matter `lighting` | 光影（Tier 1 固定值优先） |
| `{background}` | front-matter `background` | 背景（Tier 1 固定值优先） |
| `{avoid_style}` | front-matter `avoid_style` | 风格专属否定约束 |
| `{style_injection}` | front-matter `style_injection` | 追加到 `{appearance}` 段末尾 |

### 项目级覆盖

若项目根目录存在 `卡通风格提示词模板.md`，**优先**从该文件匹配同名风格模板提取参数，注入对应模板占位符。该文件中的模板可完全替代 skill 内置 `reference/` 的同名风格。

### 双语并列规则

`{photo_style}`、`{lighting}`、`{background}` 段落中的风格关键词推荐使用 `{中文描述} {English keyword}` 双语格式，以中英文逗号分隔不同词组。双语并列有助于模型同时理解语义和风格指向，提升生成一致性。

正确示例：
```
柔光全局照明 soft global illumination，电影级影棚布光 cinematic studio lighting
```

> reference 文件中的参数值已内置双语关键词，Agent 直接使用即可。仅在 Agent 自行补充描述时需注意双语格式。

### 风格关键词成组使用规则

- 从 reference 文件提取的参数值**必须整组注入**，不允许拆分或删减
- 保持模板原文的词汇关联性，不重新排列顺序
- 如需额外补充，追加在末尾而非插入中间

## Prompt 模板（按需加载）

两种构图模板已拆分至独立文件，按需加载：

| 模板文件 | 模式 | aspectRatio | 视图数 | 加载时机 |
|---------|------|-------------|--------|---------|
| `rules/vertical-template.md` | 竖版三视图 | `9:16` | 3 | **默认**，global 模式始终加载此文件 |
| `rules/horizontal-template.md` | 横版七视图 | `16:9` | 7 | 仅当角色设定或调用方明确要求横版（如需要表情参考）时加载 |

> 两个模板共用相同的占位符体系和参数取值规则（见下方「参数说明」段）。模板内禁止自行编写新格式或改为单视图描述。

## 群像专用 Prompt 模板

群像模式使用独立模板，不适用上述角色参考图模板（竖版三视图/横版七视图）。模板如下：

```
{string0}，
{string1}，8K中超清，极致细节，影视级质感，{string2}角色群像设定图，团队阵容展示。
画面呈现{群组-角色数量}位角色并排站立于纯{群组-背景色}背景前，全身入镜，从左至右依次为：{群组-角色列表及特征}。角色间保持合理间距，主次分明，{群组-C位描述}，角色比例协调，服装发饰风格统一，高端{string6}角色群像设定海报质感。
主体为{群组-整体定位描述}。
{string11}，
{string12}，
所有服装上没有任何文字、logos、标签或文字标识，no text，no logo.
```

> 群像模板暂不纳入本次改造，仍使用原有 string 参数体系。

## 参数说明

### 角色参考图参数

global 模式（Tier 1 选角 + Tier 2 定妆/新妆造）使用以下参数。Tier 1 与 Tier 2 对参数的取值来源有差异，见 `rules/global.md`。

| 参数 | 含义 | 说明 |
|------|------|------|
| `{opening_decl}` | 开篇类型声明 | 从 reference 文件 front-matter 提取 |
| `{opening_type}` | 正面类型确认 | 从 reference 文件 front-matter 提取 |
| `{opening_neg_1~3}` | 三个否定消歧项 | 从 reference 文件 front-matter 提取 |
| `{identity_ref}` | 参考图一致性引导 | 由 global.md 定义（模式 A/B、Tier 1/2） |
| `{layout_portrait_style}` | 半身近景风格定位 | 从 reference 文件 front-matter 提取。竖版三视图为上方半身近景（头顶至肘部）；横版七视图为左侧半身近景（头顶至肚脐上方），均展示面部、肩部及上半身。模板详见 `rules/vertical-template.md` / `rules/horizontal-template.md` |
| `{output_format}` | 整体输出格式定位 | 从 reference 文件 front-matter 提取 |
| `{character}` | 身份/时代/定位 | 从角色设定提取，如"A Chinese woman living in the Tang Dynasty, a noblewoman from the prosperous Tang period" |
| `{appearance}` | 面部特征/皮肤质感 | 从角色设定提取，含缺省值防范（胡须/皱纹/发型/体态），末尾追加 `{style_injection}` |
| `{hair_costume}` | 发型与服装 | Tier 1 固定为白T恤描述；Tier 2 从「造型设计」提取发型和服装描述 |
| `{photo_style}` | 摄影/渲染风格 | 从 reference 文件 front-matter 提取。模板已固定追加 85mm f4 适度景深约束，Agent 无需额外处理 |
| `{lighting}` | 光影 | Tier 1 固定值；Tier 2 从 reference 文件提取 |
| `{background}` | 背景 | Tier 1 固定值；Tier 2 从 reference 文件提取 |
| `{avoid_style}` | 风格专属否定约束 | 从 reference 文件 front-matter 提取 |
| `{style_injection}` | 风格化造型注入 | 从 reference 文件 front-matter 提取，追加到 `{appearance}` 段末尾 |

> **模板固定 Avoid**：模板末尾已硬编码 `text, labels, captions, logos, watermarks, frames, decorative elements, graphic layout, beauty retouching, perfect symmetry.`，所有风格共用，Agent 无需额外处理。`{avoid_style}` 仅提供风格专属的否定项。

### `{appearance}` 段构建规则

Agent 在构建 `{appearance}` 时必须遵守以下结构：

```
{面部特征描述}。
{皮肤质感描述}。
{发型描述}。
{体态描述}。
{胡须状态}（男性角色必填，女性角色可省略）。
{style_injection}
```

示例（写实风格，唐代贵族女性）：
```
Natural Chinese facial features, soft oval face, gentle but expressive eyes, natural facial proportions.
Real human skin texture with subtle imperfections.
Traditional Tang Dynasty hairstyle, elaborate but historically grounded hair arrangement, natural black hair.
Elegant and confident posture with refined temperament.
{style_injection 从 reference 文件提取}
```

### `{character}` 段构建规则

从角色设定提取身份、时代、定位信息，用英文描述。格式：

```
A {性别+年龄} {身份/职业} {时代/背景}, {角色定位描述}.
```

示例：
```
A Chinese woman living in the Tang Dynasty, a noblewoman from the prosperous Tang period. She has an elegant, confident, and intelligent presence, with the refined temperament of a historical figure from the Tang era.
```

### 群像专属参数

| 参数 | 含义 | 说明 |
|------|------|------|
| 群组-角色数量 | 群组成员总数 | 从群组设定文件读取 |
| 群组-背景色 | 纯色背景颜色 | 默认"浅灰色"，可由群组设定覆盖 |
| 群组-角色列表及特征 | 每位角色的排布顺序 + 关键特征 | 格式：左起依次为「角色A：蓝色连体工装，戴护目镜丨角色B：蓝色工装，戴降噪耳机」 |
| 群组-C位描述 | C位角色及其视觉突出描述 | 如"女主角居中，服装颜色略深于其他队员以突出主理人身份" |
| 群组-整体定位描述 | 群组的身份 / 角色定位 | 如"现代卫浴工厂操作员与街舞舞者融合的年轻团队" |

> **注意**：群像模式使用「群像专用 Prompt 模板」，不适用角色参考图模板（竖版三视图/横版七视图）。上述角色参考图参数表中的参数在群像模式中不适用（由 `{群组-` 前缀占位符替代）。

## Schema 校验

调用 `scripts/validators.py` 的两个函数进行校验。

> **适用范围**：Schema 校验仅适用于 **global 模式**和 **group 模式**（生成 task JSON 的模式）。episode 模式产出妆造匹配清单 JSON，不调用 validators。

**任务级校验** — `validate_tasks(tasks, mode)`：

| 校验项 | 说明 |
|--------|------|
| 基础字段 | 每个 task 必须包含：prompt, imageSize, aspectRatio, filename, images |
| 类型检查 | imageSize **必须固定为** `4K`，aspectRatio **必须为** `9:16`（竖版三视图，默认）或 `16:9`（横版七视图，备选） |
| images/模式一致性 | 由 mode 参数决定：`global`（Tier 1 选角 + Tier 2 定妆）、`group`（群像） |
| prompt 完整性 | 无模板占位符残留，长度 ≥ 50 字符 |
| filename 合法性 | 必须以 .png 结尾 |

**顶层校验** — `validate_top_level(data)`：

| 校验项 | 说明 |
|--------|------|
| model | **必须固定为** `"nano-banana-2"` |
| output_path | 如果提供，必须为非空字符串 |
| tasks | 顶层必须包含 tasks 字段 |

校验通过标准：两个函数均返回空列表。

## 输出完成提示

global 模式和 group 模式使用以下提示：

```
任务 JSON 已生成，等待 Art-director 执行生图
```

> episode 模式的完成提示见 `rules/episode.md`。
