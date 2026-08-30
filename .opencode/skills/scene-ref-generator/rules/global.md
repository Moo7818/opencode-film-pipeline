# 全局双视图参考流程

> 共享定义（Prompt 模板、参数表、校验规则）见 `rules/common.md`。

## 触发条件

- 阶段：全局视觉资产生成（global_character_tasks ~ global_scene_art）
- 输入：全局设定 + 场景设定 + 前期采样（场景/风格）

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

从 `场景设定/场景设定.md` 的**场景清单**表中提取所有需要生成的场景。每个场景生成 2 个 task（内景 + 外景），**task 数量 = 场景数量 x 2**。

### 步骤 3：模式判断

对每个场景，检查 `前期采样/场景/` 下是否存在以该场景名命名的图片文件：

| 模式 | 条件 | 参考图 |
|------|------|--------|
| **模式 A** | `前期采样/场景/{场景名}*.png` 存在 | **场景采样图（必选，放images[0]）** + 风格参考图 |
| **模式 B** | `前期采样/场景/{场景名}*.png` 不存在 | 仅风格参考图 |

### 步骤 3A：分析参考图特征（仅模式 A）

在写入 prompt 前，必须对场景采样图进行分析，提取视觉特征：

```
1. 文件名清单：[场景名-1.jpg, 场景名-2.jpg, ...]
2. 覆盖方位：正面全景、局部特写、不同角度
3. 核心视觉特征提取：
   - 空间风格、色调色温、光线方向、核心元素
4. 将提取特征融入 prompt 的 Scene / Lighting / Atmosphere 段落
```

### 步骤 4：提取视觉风格

按 `rules/common.md` 的「视觉风格提取」规则，从全局设定中提取 `{style_desc}` 和英文风格参数（`{film_context}` / `{production_type}` / `{style_anchor}` 等）。

### 步骤 5：构建 Prompt

使用 `rules/common.md` 的**内景 Prompt 模板**和**外景 Prompt 模板**（7 段双语结构），逐字替换占位符。

**全局模式专属参数定义：**
- 英文风格参数（`{film_context}` / `{production_type}` / `{neg_1~3}` / `{style_anchor}` / `{style_footer}` / `{camera_language}` / `{quality}` / `{style_avoid}`）：按步骤 4 提取
- `{scene_name_zh}`：场景中文名（来自场景设定）
- `{environment_description_zh}`：环境描述（从场景具体设定提取，分为室内/室外）
- `{period_description_zh}`：时代描述（从全局设定提取）
- **Scene 段落**（中文内容层）：从场景具体设定文件提取，按 `rules/common.md` 的「内景与外景的内容划分」规则拆分为室内/室外描述
- **Composition / Camera feeling / Lighting / Atmosphere**：按场景内容填写英文电影语义

> **注意**：提取时跳过所有剧情角色描述（如郑和的服饰、一岛的着装等），仅提取场景空间/环境/建筑/光线等元素。

### 步骤 6：生成任务 JSON

```json
{
  "model": "nano-banana-2",
  "tasks": [
    {
      "prompt": "SCENE REFERENCE FRAME — INTERIOR\n\nCreate a professional cinematic interior scene reference frame for {film_context}.\n\nThis is an interior scene reference image for {scene_name_zh}...",
      "model": "nano-banana-2",
      "imageSize": "4K",
      "aspectRatio": "4:1",
      "filename": "{场景名}_内景.png",
      "images": [
        "project/{项目名}/前期采样/场景/{场景名}.png",
        "project/{项目名}/前期采样/风格/{风格文件}.png"
      ]
    },
    {
      "prompt": "SCENE REFERENCE FRAME — EXTERIOR\n\nCreate a professional cinematic exterior scene reference frame for {film_context}.\n\nThis is an exterior scene reference image for {scene_name_zh}...",
      "model": "nano-banana-2",
      "imageSize": "4K",
      "aspectRatio": "4:1",
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
- [ ] 每个 prompt 包含 7 段结构：DECLARATION / CONTINUITY / MAPPING / FRAME DETAIL / CINEMATIC QUALITY / TEXT POLICY / AVOID
- [ ] prompt 中英文控制层正确，中文内容层保留原始中文（场景名、空间描述、氛围等）
- [ ] **prompt 禁止出现剧情角色描述**（如郑和、一岛等人物外观、服饰、动作）
- [ ] **prompt 包含 "No character focus" 声明**
- [ ] **prompt 包含 "No multi-panel, grid, collage" 禁令**
- [ ] 内景 prompt 聚焦室内空间：建筑结构、家具陈设、材质纹理、室内光线
- [ ] 外景 prompt 聚焦室外空间：建筑外观、周边环境、街道/地形、天际线、天气
- [ ] 内景与外景 prompt 之间存在差异化，不重复相同描述
- [ ] 不同场景之间的 prompt 存在差异化
- [ ] **images 数组中不包含角色参考图或道具参考图**
- [ ] model 固定为 `nano-banana-2`，imageSize 固定为 `4K`，aspectRatio 固定为 `4:1`

### 步骤 7：Schema 校验

1. `validate_top_level(data)` 校验顶层字段
2. `validate_tasks(tasks)` 校验任务列表

两个函数均返回空列表则通过。

### 步骤 8：输出完成提示

使用 `rules/common.md` 中的完成提示。

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
