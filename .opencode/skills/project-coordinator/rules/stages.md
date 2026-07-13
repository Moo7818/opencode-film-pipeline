# 阶段与状态管理

## 阶段定义

`stages.json` 中的阶段名称和流转顺序由 `project.json` 中的 `type` 决定。目前支持的项目类型：

| `type` | 阶段链 |
|--------|--------|
| `animation_series` | `project_init` → `material_sorting` → `supervisor_extraction` → `global_character_tasks` → `global_character_art` → `global_prop_tasks` → `global_prop_art` → `global_scene_tasks` → `global_scene_art` → `episode_storyboard` → `episode_character_ref` → `episode_prop_ref` → `episode_scene_ref` → `asset_sync` → `video_generation` → `delivery` |
| `film` | `project_init` → `material_sorting` → `supervisor_extraction` → `global_character_tasks` → `global_character_art` → `global_prop_tasks` → `global_prop_art` → `global_scene_tasks` → `global_scene_art` → `episode_storyboard` → `episode_character_ref` → `episode_prop_ref` → `episode_scene_ref` → `asset_sync` → `video_generation` → `delivery` |

各阶段说明（通用）：

| 阶段 name | label | 说明 | 执行子 Agent |
|-----------|-------|------|-------------|
| `project_init` | 项目初始化 | 创建项目骨架、注册原始剧本、建立目录结构 | Coordinator |
| `material_sorting` | 前期素材归类 | 用户提供的参考素材（人物/场景/风格/道具）归类到 `前期采样/` | Coordinator |
| `supervisor_extraction` | 监制提取设定 | 从原始剧本提取角色/场景/道具设定，产出分集剧本 | Producer |
| `global_character_tasks` | 全局角色参考图任务生成 | 角色导演结合全局设定+角色设定+特征采样生成角色参考图任务表 | Character-director |
| `global_character_art` | 全局角色参考图绘制 | 美术指导根据任务表绘制所有角色的全局参考图 | Art-director |
| `global_prop_tasks` | 全局道具参考图任务生成 | 道具师结合全局设定+道具设定+特征采样生成道具参考图任务表 | Prop-maker |
| `global_prop_art` | 全局道具参考图绘制 | 美术指导根据任务表绘制所有道具的全局参考图 | Art-director |
| `global_scene_tasks` | 全局场景参考图任务生成 | 置景师结合全局设定+场景设定+特征采样生成场景参考图任务表 | Set-designer |
| `global_scene_art` | 全局场景参考图绘制 | 美术指导根据任务表绘制所有场景的全局参考图 | Art-director |
| `episode_storyboard` | 剧集分镜脚本与分镜图 | 分镜导演制作分镜脚本；**必选**调用 `expand_scenes_to_groups.py` 拆分为独立组文件，产出物包含 `{剧集号}/分镜/分组/组{N}.json`（供 video-director 使用，不再视为可选）；按 project_config.json 中 use_storyboard_images 决定是否生成分镜图任务表并由美术指导执行绘制 | Storyboard-director → [可选] Art-director |
| `episode_character_ref` | 剧集级角色妆造匹配清单 | 角色导演参考全局设定+角色设定+本集剧本，仅产出 `{剧集号}/角色参考图/妆造匹配清单.json`（不产出图片任务表，Art-director 本阶段不参与）；该清单由 coordinator 在 `asset_sync` 阶段消费 | Character-director |
| `episode_prop_ref` | 剧集级道具参考图生成 | 道具师参考全局设定+道具设定+本集分镜脚本中道具使用描述，生成剧集级道具参考图；美术指导执行绘制 | Prop-maker → Art-director |
| `episode_scene_ref` | 剧集级场景参考图生成 | 置景师参考全局设定+场景设定+本集分镜脚本中场景变化描述，生成剧集级场景参考图；美术指导执行绘制 | Set-designer → Art-director |
| `asset_sync` | 资产同步 | Coordinator 读取本集"妆造匹配清单.json"，将所需角色/场景/道具参考图从 `全局依赖/...` 复制到 `temp/分组素材/{剧集号}/角色参考|场景参考|道具参考/`，供 video-director 使用 | Coordinator |
| `video_generation` | 视频生成 | 前置依赖：分镜组 JSON 已就绪（`{剧集号}/分镜/分组/组{N}.json`）、资产同步已完成（`temp/分组素材/{剧集号}/` 下三类参考图齐全）。视频导演基于分镜组 JSON 生成视频；如有下集回到 `episode_storyboard`，否则进入交付 | Video-director |
| `delivery` | 交付归档 | 最终打包、阶段标记 complete | Coordinator |

## 操作规则

| 操作 | 前置条件 | 后置动作 |
|------|----------|----------|
| 推进到下一阶段 | 当前阶段 `status` 为 `completed` | 当前阶段锁定不可改，下一阶段设为 `in_progress` |
| 到达检查点 | — | 更新 `completed_at`，写入事件 |

## 推进流程

**禁止使用 `Read`/`Write` 文件工具。所有文件操作必须通过 `RunCommand` CLI 执行。**

1. **使用 CLI 读取 stages.json**，**先校验阶段完整性**：确认 `stages` 数组包含全部 16 阶段（顺序见上方"阶段定义"表），且每个阶段字段齐全（`name` / `label` / `status` / `artifacts` / `started_at` / `completed_at`）。若阶段缺失或字段不全，**立即报错并停止操作**。

   ```powershell
   # PowerShell (Windows)
   $json = Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/stages.json"
   $stages = $json | ConvertFrom-Json
   if ($stages.stages.Count -ne 16) { throw "stages.json 阶段数异常: $($stages.stages.Count)，应为 16" }
   ```
   ```bash
   # bash (Unix/macOS)：建议用 python3 解析 JSON
   python3 -c "
   import json
   with open('.meta/projects/{id}/stages.json', 'r', encoding='utf-8') as f:
     s = json.load(f)
   assert len(s['stages']) == 16, f'阶段数异常: {len(s[\"stages\"])}'
   for x in s['stages']:
     for k in ('name','label','status','artifacts','started_at','completed_at'):
       assert k in x, f'阶段 {x.get(\"name\")} 缺字段 {k}'
   "
   ```
2. 在 `stages` 数组中定位 `current` 阶段
3. 验证其 `status` 是否为 `completed`，若是则推进到下一阶段；若不是则拒绝操作
4. 将当前阶段的 `completed_at` 设为当前时间
5. 将下一阶段的 `status` 设为 `in_progress`，`started_at` 设为当前时间
6. 更新 `project.json` 中的 `current_stage`
7. **使用 CLI 追加 events.jsonl**：
   ```powershell
   # PowerShell (Windows)
   Add-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value '{"timestamp":"...","type":"stage.transition","actor":"project-coordinator","data":{...}}'
   ```
   ```bash
   # bash (Unix/macOS)
   python3 -c "
   import json
   event = {'timestamp':'...','type':'stage.transition','actor':'project-coordinator','data':{...}}
   with open('.meta/projects/{id}/events.jsonl', 'a', encoding='utf-8') as f:
     f.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
   "
   ```
8. **使用 CLI 写回 stages.json**：
   ```powershell
   # PowerShell (Windows)
   $stages | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/stages.json"
   ```
   ```bash
   # bash (Unix/macOS)
   python3 -c "
   import json
   with open('.meta/projects/{id}/stages.json', 'w', encoding='utf-8') as f:
     json.dump(stages, f, ensure_ascii=False, indent=2)
   "
   ```
9. **校验**：调用 `validate.py` 校验 `.meta/projects/{id}/stages.json`、`project.json`、`events.jsonl` 语法，通过后才算完成

> **`actor` 命名规范**：events.jsonl 中的 `actor` 字段必须是 opencode.json 中定义的 skill name（如 `producer`、`storyboard-generator`、`roles-ref-generator`、`scene-ref-generator`、`prop-ref-generator`、`art-director`、`video-director-libtv`、`project-coordinator`）。`coordinator` 角色发起的事件统一使用 `project-coordinator` 作为 actor。禁止使用 `script_writer`、`character-director` 这类未定义名（character-director 实际对应 skill 是 `roles-ref-generator`）。详见 `project_management.md` 的 events.jsonl 字段说明。

## 查询

遍历 `stages` 数组可获知：
- 已完成阶段的总数和列表
- 当前阶段及耗时
- 后续待开始的阶段
