# 阶段与状态管理（人读说明）

> **权威声明**：阶段链、label、expected_types 的唯一来源是 `.opencode/mcp-servers/meta-server/src/meta_server/templates.py` 的 `STAGES` 常量。本文仅为人类可读说明，两者不一致时以 templates.py 为准。

## 阶段链（17 阶段，固定顺序）

| idx | name | label | expected_types | 执行子 Agent |
|-----|------|-------|----------------|-------------|
| 0 | `project_init` | 项目初始化 | raw_script | Coordinator |
| 1 | `material_sorting` | 前期素材归类 | — | Coordinator |
| 2 | `supervisor_extraction` | 监制提取设定 | setting, character_design, scene_design, prop_design, script | Producer |
| 3 | `global_character_tasks` | 全局角色参考图任务生成 | — | Character-director |
| 4 | `global_character_art` | 全局角色参考图绘制 | character_ref | Art-director |
| 5 | `global_prop_tasks` | 全局道具参考图任务生成 | — | Prop-maker |
| 6 | `global_prop_art` | 全局道具参考图绘制 | prop_ref | Art-director |
| 7 | `global_scene_tasks` | 全局场景参考图任务生成 | — | Set-designer |
| 8 | `global_scene_art` | 全局场景参考图绘制 | scene_ref | Art-director |
| 9 | `episode_storyboard_script` | 剧集分镜脚本 | storyboard | Storyboard-director |
| 10 | `episode_character_ref` | 剧集级角色妆造匹配清单 | — | Character-director |
| 11 | `episode_prop_ref` | 剧集级道具参考图生成 | prop_ref | Prop-maker → Art-director |
| 12 | `episode_scene_ref` | 剧集级场景参考图生成 | scene_ref | Set-designer → Art-director |
| 13 | `episode_storyboard_images` | 剧集参考图生成 | — | Storyboard-director → Art-director |
| 14 | `asset_sync` | 资产同步 | — | 阶段推进由 Coordinator 负责 |
| 15 | `video_generation` | 视频生成 | video, video_manifest | Video-director |
| 16 | `delivery` | 交付归档 | — | Coordinator |

expected_types 为空（—）的阶段不做产物前置校验。

## 推进语义（meta_advance_stage）

- 只允许逐阶段前进（idx 递增一格），禁止回退与越级；completed 不可逆
- **前置校验**：当前阶段 expected_types 中每个 type 在 artifacts 表须至少有一条 status='final' 记录；不满足时返回 `{error, missing, code: 'invalid'}`，不修改任何状态
- **skip**：skip=true 跳过前置校验，必须提供 skip_reason；事件类型改记 `stage.skip`
- **delivery 终态**：最后一个阶段推进完成后无下一阶段，返回 finished=true；此后再次调用返回错误
- 完成动作：当前阶段置 completed（写 completed_at），下一阶段置 in_progress（写 started_at），projects.current_stage 同步更新，写 stage.transition（或 stage.skip）事件

## 状态流转

`pending` → `in_progress` → `completed`，单向不可逆。项目创建时仅 project_init 为 in_progress，其余 pending。

## 查询

`meta_query`（scope=stages，需 project_id）：返回 17 阶段的 idx / status / started_at / completed_at，按 idx 排序；可用 filters.status 过滤。已删除项目的阶段记录同样可查（审计保留）。
