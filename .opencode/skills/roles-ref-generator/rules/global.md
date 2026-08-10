# 全局基础参考流程

> 共享定义（Prompt 模板、参数表、校验规则）见 `rules/common.md`。

## 触发条件

- 阶段：全局视觉资产生成（global_character_tasks ~ global_scene_art）
- 输入：全局设定 + 角色设定（含造型设计、设计参考）+ 前期采样（人物/风格）
- 两个阶段：Tier 1 选角资产 → Tier 2 默认定妆
- 也可由 orchestrator 单独触发生成新妆造（Tier 2）

## 步骤 1：收集输入文件

定位并读取以下文件：

| 文件 | 用途 |
|------|------|
| `project/{项目名}/全局依赖/全局设定.md` | 画风参考、色调色温、视觉语言标准 |
| `project/{项目名}/全局依赖/角色设定/角色设定.md` | 角色清单 |
| `project/{项目名}/全局依赖/角色设定/具体设定/{角色名}.md` | 角色详细设定（含造型设计、设计参考） |
| `project/{项目名}/前期采样/人物/{角色名}*.png` | 角色采样图（可选，决定模式 A/B） |
| `project/{项目名}/前期采样/风格/*.png` | 风格参考图（所有角色共用） |

## 步骤 2：模式判断 + 风格匹配

### 模式判断

| 模式 | 条件 | 参考图 | 说明 |
|------|------|--------|------|
| **模式 A** | `前期采样/人物/{角色名}*.png` 存在 | 人物采样图 + 风格参考图 | 有采样图时，Agent 以采样图人物特征为基准 |
| **模式 B** | `前期采样/人物/{角色名}*.png` 不存在 | 仅风格参考图 | 无采样图时，Agent 仅依据角色设定文字描述 |

### 风格匹配

1. 从角色设定文件的「视觉参考风格」或整体描述中提取风格关键词
2. 匹配 `rules/common.md` 中的「风格匹配表」
3. 若匹配成功 → 加载 `reference/{风格名}.md`，提取 front-matter 参数
4. 若未匹配 → 加载 `reference/PhotoRealistic.md`（默认写实风格）

## 步骤 3a：生成 Tier 1 选角资产

加载 `rules/vertical-template.md`（默认）中的 **竖版三视图 Prompt 模板**逐字替换占位符。如角色设定或调用方明确要求横版七视图，则加载 `rules/horizontal-template.md` 使用横版模板。

**Tier 1 参数取值来源：**

| 参数 | 来源 |
|------|------|
| `{opening_decl}` | reference 文件 front-matter |
| `{opening_type}` | reference 文件 front-matter |
| `{opening_neg_1~3}` | reference 文件 front-matter |
| `{identity_ref}` | 模式 A：`"Character features strictly reference Image 1 through Image N."`；模式 B：空字符串 |
| `{layout_portrait_style}` | reference 文件 front-matter |
| `{output_format}` | reference 文件 front-matter |
| `{character}` | 从 `角色设定.md` 提取身份、时代、定位 |
| `{appearance}` | 从 `角色设定.md` 详细扩展 + `{style_injection}` 追加末尾。需含缺省值防范（胡须/皱纹/发型/体态） |
| `{hair_costume}` | **固定值：`"Plain white short-sleeve T-shirt, minimal, no patterns, no text. Natural hairstyle as described in character setting."`** |
| `{photo_style}` | reference 文件 front-matter |
| `{lighting}` | **固定值：`"Soft studio lighting with even illumination, no color cast, minimal shadows."`** |
| `{background}` | **固定值：`"Industrial mid-grey seamless backdrop, clean neutral studio environment, minimal visual elements."`** |
| `{avoid_style}` | reference 文件 front-matter |
| `{style_injection}` | reference 文件 front-matter，追加到 `{appearance}` 末尾 |

> **固定项不可覆盖**：`{hair_costume}`、`{lighting}`、`{background}` 在 Tier 1 选角资产中固定为上述值。选角资产的目的是排除服装与环境干扰，聚焦角色本体的面部特征、表情表现力和体型轮廓。

**Tier 1 产出：**
- filename: `{角色名}_选角.png`
- output_path: `project/{项目名}/全局依赖/角色设定/角色参考图/`

## 步骤 3b：生成 Tier 2 默认定妆

使用同一模板（默认竖版三视图，见 `rules/vertical-template.md`；横版见 `rules/horizontal-template.md`），但 `{hair_costume}`、`{lighting}`、`{background}` 不再固定，从角色设定「造型设计」和 reference 文件提取。

**Tier 2 参数取值来源：**

| 参数 | 来源 |
|------|------|
| `{opening_decl}` | 同 Tier 1 |
| `{opening_type}` | 同 Tier 1 |
| `{opening_neg_1~3}` | 同 Tier 1 |
| `{identity_ref}` | 固定为 `"Character features strictly reference Image 1."` |
| `{layout_portrait_style}` | 同 Tier 1 |
| `{output_format}` | 同 Tier 1 |
| `{character}` | 同 Tier 1 |
| `{appearance}` | 同 Tier 1 |
| `{hair_costume}` | 从「造型设计」默认妆造提取发型和服装描述 |
| `{photo_style}` | 同 Tier 1 |
| `{lighting}` | 从 reference 文件 front-matter 提取（非固定值） |
| `{background}` | 从 reference 文件 front-matter 提取（非固定值） |
| `{avoid_style}` | 同 Tier 1 |
| `{style_injection}` | 同 Tier 1 |

**Tier 2 产出：**
- filename: `{角色名}_默认.png`
- output_path: `project/{项目名}/全局依赖/角色设定/角色参考图/`

**Tier 2 参考图上传顺序：**

| 位置 | 内容 |
|------|------|
| images[0] | Tier 1 选角资产（`全局依赖/角色设定/角色参考图/{角色名}_选角.png`） |
| images[1] | 风格参考图（`前期采样/风格/*.png`） |

> **参考图用途界定**：Tier 1 选角资产提供面部骨相、五官、体型、气质。**禁止从参考图推断服装**——服装从「造型设计」提取。

## 步骤 3c：生成新妆造（orchestrator 触发时）

当 orchestrator 报告"发现新妆造需求"时，按以下步骤生成：

1. 从角色设定「造型设计」中找到对应妆造名的描述
2. 使用默认模板（竖版三视图，见 `rules/vertical-template.md`；横版见 `rules/horizontal-template.md`），`{hair_costume}` 从该妆造名下的发型和服装描述提取
3. `{lighting}` 和 `{background}` 从 reference 文件提取（如有场景特殊色调由 orchestrator 补充）
4. 参考图为 Tier 1 选角资产 + 风格参考图
5. filename: `{角色名}_{妆造名}.png`
6. output_path: `project/{项目名}/全局依赖/角色设定/角色参考图/`

## 步骤 4：生成任务 JSON

将 Tier 1 和 Tier 2 的 tasks 合并到一个 JSON 中（初始生成时）。新妆造单独生成时输出独立 JSON。

输出到 `project/{项目名}/全局依赖/角色设定/角色参考图/角色参考图_任务表.json`

```json
{
  "model": "nano-banana-2",
  "tasks": [
    {
      "prompt": "Create a live-action historical drama actor continuity reference image...",
      "imageSize": "4K",
      "aspectRatio": "9:16",
      "filename": "{角色名}_选角.png",
      "images": ["project/{项目名}/前期采样/人物/{角色名}.png", "project/{项目名}/前期采样/风格/{风格文件}.png"]
    },
    {
      "prompt": "Create a live-action historical drama actor continuity reference image...",
      "imageSize": "4K",
      "aspectRatio": "9:16",
      "filename": "{角色名}_默认.png",
      "images": ["project/{项目名}/全局依赖/角色设定/角色参考图/{角色名}_选角.png", "project/{项目名}/前期采样/风格/{风格文件}.png"]
    }
  ],
  "output_path": "project/{项目名}/全局依赖/角色设定/角色参考图/"
}
```

> **注意**：Tier 2 的 images[0] 引用 Tier 1 产出物。Art-director 执行时 Tier 1 必须已生成，否则路径不存在。orchestrator 应确保 Tier 1 先执行完成再执行 Tier 2。

**自检清单（每一项必须通过）：**
- □ 每个角色生成 2 个 task（Tier 1 选角 + Tier 2 默认定妆）
- □ aspectRatio 为 `9:16`（竖版三视图，默认）；仅当明确要求横版七视图时才为 `16:9`
- □ Tier 1 的 prompt 中 `{hair_costume}` 包含"Plain white short-sleeve T-shirt"
- □ Tier 1 的 prompt 中 `{lighting}` 包含"even illumination, no color cast"
- □ Tier 1 的 prompt 中 `{background}` 包含"mid-grey seamless backdrop"
- □ Tier 2 的 prompt 中 `{hair_costume}`/`{lighting}`/`{background}` 从「造型设计」和 reference 文件提取，不包含白T恤和灰墙
- □ `{appearance}` 段已包含缺省值防范（胡须/皱纹/发型/体态显式声明）
- □ `{appearance}` 段末尾已追加 `{style_injection}`
- □ prompt 中无 `{}` 占位符残留
- □ Tier 2 的 images[0] 指向 Tier 1 产出物路径
- □ prompt 末尾 Avoid 段包含"text, labels, captions, logos, watermarks, frames, decorative elements, graphic layout, beauty retouching, perfect symmetry"

## 步骤 5：初始化妆造衣橱

生成完成后，创建 `project/{项目名}/全局依赖/角色设定/妆造衣橱.md`：

```markdown
# 妆造衣橱

## {角色名}

| 妆造名 | 造型描述 | 参考图文件 | 生成状态 | 首次使用 |
|--------|---------|-----------|---------|---------|
| 默认 | {从造型设计提取} | {角色名}_默认.png | ✅ 已生成 | — |
```

> 衣橱由 global 模式初始化，后续由 orchestrator 维护。新妆造生成后由 orchestrator 更新衣橱。

## 步骤 6：Schema 校验

按 `rules/common.md` 中 **Schema 校验** 说明执行：

1. 先调用 `validate_top_level(data)` 校验顶层字段
2. 再调用 `validate_tasks(tasks, "global")` 校验任务列表

两个函数均返回空列表则校验通过。

## 步骤 7：输出完成提示

使用 `rules/common.md` 中的完成提示。

## 参考图上传顺序

### Tier 1 选角资产

**模式 A（有人物采样图）：**

| 位置 | 内容 |
|------|------|
| images[0] | 人物采样图（`前期采样/人物/{角色名}*.png`） |
| images[1] | 风格参考图（`前期采样/风格/*.png`） |

**模式 B（无人物采样图）：**

| 位置 | 内容 |
|------|------|
| images[0] | 风格参考图（`前期采样/风格/*.png`） |

### Tier 2 定妆资产 / 新妆造

| 位置 | 内容 |
|------|------|
| images[0] | Tier 1 选角资产（`全局依赖/角色设定/角色参考图/{角色名}_选角.png`） |
| images[1] | 风格参考图（`前期采样/风格/*.png`） |
