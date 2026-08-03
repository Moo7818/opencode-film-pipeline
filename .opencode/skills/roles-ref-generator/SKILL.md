---
name: roles-ref-generator
description: 角色参考资产任务生成技能。支持三定位：1) 全局参考（global）— 两阶段生成：Tier 1 选角资产（白T恤七视图，排除服装干扰聚焦角色本体）→ Tier 2 默认定妆（从角色设定「造型设计」提取，七视图），并初始化妆造衣橱；也可由 orchestrator 触发生成新命名妆造。基于角色设定 + 角色采样图（如有）+ 全局风格设定 + 设计参考，生成标准化七视图（半身照 + 表情三连 + 全身三视图）。2) 剧集级参考（episode）— 只读妆造衣橱，从分镜脚本提取 [妆造:名] 标注，匹配衣橱已有资产，输出妆造匹配清单供 coordinator 同步；发现衣橱中不存在的新妆造时向 orchestrator 报告。3) 群像参考（group）— 基于群组角色设定，生成纯色背景并排全身群像展示图。模式：中英双语风格关键词并列注入 + string8 末尾追加风格化造型特征描述 + 高密度成组风格词汇注入。global/group 模式产出 角色参考图_任务表.json 由 Art-director 执行生图；episode 模式产出 妆造匹配清单.json。当任务涉及角色参考图、角色视觉化、角色形象设计、角色基准资产、角色七视图、角色设定图、人物参考图、选角资产、定妆资产、妆造衣橱、妆造匹配、全局参考、剧集级参考、群像参考、群组展示、团队阵容、表情参考、标准化角色参考时务必触发此技能。即使只提到"生成角色图"或"角色任务表"也应触发。
---

# 角色参考生成 Skill

三定位模式：global 生成角色参考资产 task JSON（由 Art-director 执行生图），episode 只读妆造衣橱输出匹配清单（供 coordinator 同步），group 生成群像 task JSON。

**设计原则**：所有智能决策由你（Agent）完成——读取文件、理解设定、构建 Prompt、组装任务表/匹配清单、判定新妆造需求。Python 脚本仅做无状态的 Schema 校验。

## 路径约定

所有项目文件位于 `project/{项目名}/` 下：

```
project/{项目名}/
├── 全局依赖/
│   ├── 角色设定/角色设定.md                    ← 入口索引
│   ├── 角色设定/具体设定/{角色名}.md            ← 独立角色文件（含造型设计、设计参考）
│   ├── 角色设定/妆造衣橱.md                    ← 妆造衣橱索引（global 初始化，orchestrator 维护）
│   ├── 角色设定/角色参考图/                     ← 角色参考资产（产出物）
│   │   ├── {角色名}_选角.png                   ← Tier 1 选角资产
│   │   ├── {角色名}_默认.png                   ← Tier 2 默认定妆
│   │   ├── {角色名}_{妆造名}.png               ← Tier 2 命名妆造（按需）
│   │   └── 角色参考图_任务表.json              ← global 模式产出
│   ├── 场景设定/场景设定.md
│   ├── 场景设定/具体设定/{场景名}.md
│   ├── 场景设定/场景参考图/                      ← 场景参考图（产出物）
│   ├── 道具设定/道具设定.md
│   ├── 道具设定/具体设定/{道具名}.md
│   └── 道具设定/道具参考图/                      ← 道具参考图（产出物）
├── 前期采样/
│   ├── 人物/{角色名}.png                        ← 角色采样图（可选输入）
│   └── 风格/*.png                               ← 风格参考图
├── 原始剧本.md
└── {剧集号}/
    ├── 剧本.md
    ├── 分镜/分镜脚本.json
    └── 角色参考图/
        └── 妆造匹配清单.json                    ← episode 模式产出
```

## 输出 Schema

产出 `角色参考图_任务表.json` 必须符合 `.opencode/schemas/image-generation.json` 定义。核心字段：

| 字段 | 类型 | 固定值 | 说明 |
|------|------|--------|------|
| `prompt` | string | — | 生图提示词（必填） |
| `model` | string | `"nano-banana-2"` | 固定为 nano-banana-2，不可变 |
| `imageSize` | string | `"4K"` | 固定为 4K，不可变 |
| `aspectRatio` | string | `"16:9"` | 固定为 16:9，不可变 |
| `filename` | string | — | 输出文件名，以 .png 结尾 |
| `images` | string[] | — | 参考图路径列表 |

## 三定位模式

| 模式 | 触发阶段 | 核心输入 | 产出物 | 输出路径 |
|------|---------|---------|--------|---------|
| global | 全局视觉资产生成 / 新妆造时 | 角色设定（含造型设计、设计参考）+ 角色采样图（如有）+ 风格参考 | task JSON（Tier 1 选角 + Tier 2 定妆）+ 妆造衣橱初始化 | `全局依赖/角色设定/角色参考图/角色参考图_任务表.json` |
| episode | 剧集级参考图 + 资产同步（episode_character_ref + asset_sync） | 分镜脚本 + 妆造衣橱 + 角色设定 | 妆造匹配清单 JSON（不生成图片） | `{剧集号}/角色参考图/妆造匹配清单.json` |
| group | 全局视觉资产生成（global_character_tasks ~ global_scene_art，群组阶段） | 群组设定 + 成员设定 + 风格参考 | task JSON（单张并排全身展示） | `全局依赖/角色设定/角色参考图/群像参考图_任务表.json` |

## 入口

- 共享定义（Prompt 模板、参数表、校验规则）：`rules/common.md`
- global 模式（Tier 1 选角 + Tier 2 定妆 + 新妆造 + 衣橱初始化）：`rules/global.md`
- episode 模式（妆造匹配 + 只读衣橱 + 新妆造报告）：`rules/episode.md`
- group 模式（群像参考）：`rules/group.md`

### 风格参考文件

| 风格 | 文件 | 匹配关键词 |
|------|------|-----------|
| 写实影视（默认） | `reference/PhotoRealistic.md` | 真人摄影、写真、live-action、historical drama |
| 3D 卡通 | `reference/3DCartoon.md` | Pixar、迪士尼、3D stylized、三维动画 |
| 吉卜力手绘 | `reference/Ghibli.md` | 吉卜力、宫崎骏、ghibli |
| GTA V 游戏风 | `reference/GTAV.md` | GTA V、Rockstar、侠盗猎车手 |

> 角色设定未指定视觉参考风格时，默认使用 `reference/PhotoRealistic.md`。
