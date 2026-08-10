# 项目生产管线（7 阶段）

> 供子 agent（特别是 coordinator）参考的管线定义，orchestrator 无需关心。

| 阶段 | 名称 | 执行子 Agent | 说明 |
|------|------|-------------|------|
| 1 | 项目初始化 | `coordinator` | 创建项目骨架 + 配置（画幅/分辨率/模型等由 coordinator 逐项询问用户填写） |
| 2 | 监制提取设定 | `producer` | 多模态分析采样图（如有）→ 联网检索 → 提取设定（含造型设计、设计参考）→ 生成分集剧本 |
| 3 | 全局视觉资产生成 | `character-director` + `prop-maker` + `set-designer` → `art-director` | 角色资产分两步：选角资产（白T恤）→ 默认定妆（造型设计），详见 `roles-ref-generator` |
| 4 | 拆解分镜 | `storyboard-director` | 分镜脚本（`episode_storyboard_script`，每集独立执行；非默认妆造需标注 `[妆造:名]`） |
| 5 | 剧集级参考图 + 资产同步 | `character-director` + `prop-maker` + `set-designer` → `art-director` → `coordinator` | 剧集级参考图在分镜脚本之后、参考图生成之前生成；参考图可引用剧集级场景/道具变化。由 `coordinator` 将所需资产从 `全局依赖/` 和剧集级目录复制到 `temp/分组素材/{剧集号}/`，供 video-director 使用 |
| 6 | 参考图生成 | `storyboard-director` → `art-director` | **独立 session**（不继承阶段 4 对话上下文）。按 `project_config.json` 的 `reference_image_mode` 分支：`visual_anchor`（默认）→ 每场一张视觉锚点图，锁定场景/氛围/人物站位，同场各组共享；`storyboard_images` → 串行分镜图，每镜头一张，场内帧链串行；`none` → 跳过。模型 `nano-banana-2`，2K 分辨率，16:9 |
| 7 | 视频生成 | `video-director` | 基于分镜组生成视频，引用阶段 6 产出的参考图（视觉锚点/分镜图）作为场景连续性参考；如有下集回到阶段 4，否则项目交付完成 |

参考: https://opencode.ai/docs/permissions
