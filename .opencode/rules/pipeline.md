# 项目生产管线（6 阶段）

> 供子 agent（特别是 coordinator）参考的管线定义，orchestrator 无需关心。

| 阶段 | 名称 | 执行子 Agent | 说明 |
|------|------|-------------|------|
| 1 | 项目初始化 | `coordinator` | 创建项目骨架 + 配置（画幅/分辨率/模型等由 coordinator 逐项询问用户填写） |
| 2 | 监制提取设定 | `producer` | 多模态分析采样图（如有）→ 联网检索 → 提取设定（含造型设计、设计参考）→ 生成分集剧本 |
| 3 | 全局视觉资产生成 | `character-director` + `prop-maker` + `set-designer` → `art-director` | 角色资产分两步：选角资产（白T恤）→ 默认定妆（造型设计），详见 `roles-ref-generator` |
| 4 | 拆解分镜 | `storyboard-director` | 每集独立执行；非默认妆造需标注 `[妆造:名]` |
| 5 | 剧集级参考图 + 资产同步 | `character-director` + `prop-maker` + `set-designer` → `art-director` → `coordinator` | 参考图生成后，由 `coordinator` 将所需妆造资产从 `全局依赖/角色设定/角色参考图/` 复制到 `temp/分组素材/{剧集号}/角色参考/`，供 video-director 使用 |
| 6 | 视频生成 | `video-director` | 基于分镜组生成视频；如有下集回到阶段 4，否则项目交付完成 |

参考: https://opencode.ai/docs/permissions
