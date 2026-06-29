# 项目生产管线（6 阶段）

> 供子 agent（特别是 coordinator）参考的管线定义，orchestrator 无需关心。

| 阶段 | 名称 | 执行子 Agent | 说明 |
|------|------|-------------|------|
| 1 | 项目初始化 | `coordinator` | 创建项目骨架 + 配置（画幅/分辨率/模型等由 coordinator 逐项询问用户填写） |
| 2 | 监制提取设定 | `producer` | 多模态分析采样图（如有）→ 联网检索 → 提取设定 → 生成分集剧本 |
| 3 | 全局视觉资产生成 | `character-director` + `prop-maker` + `set-designer` → `art-director` | 三步 agent 先并发生成任务表，最后 `art-director` 批量绘制 |
| 4 | 拆解分镜 | `storyboard-director` | 每集独立执行 |
| 5 | 剧集级参考图 | `character-director` + `prop-maker` + `set-designer` → `art-director` | 模式同阶段 3，但基于剧集分镜而非全局设定 |
| 6 | 视频生成 | `video-director` | 基于分镜组生成视频；如有下集回到阶段 4，否则项目交付完成 |

参考: https://opencode.ai/docs/permissions
