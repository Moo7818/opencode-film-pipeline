"""单一来源常量：阶段链、目录骨架、产物类型与路径映射、actor 枚举、配置字段。

权威来源（不得在本文件之外另行硬编码）：
- 阶段链与 label：.opencode/skills/project-coordinator/rules/stages.md
- type 枚举与目录映射：.opencode/skills/project-coordinator/rules/project_management.md 第 3 节
- actor 枚举与事件类型：.opencode/skills/project-coordinator/rules/events.md
- 配置字段与默认值：.opencode/schemas/project-config.json
"""

PROJECT_TYPES = ("animation_series", "film", "episode", "other")

PROJECT_STATUS = ("active", "deleted")

STAGE_STATUS = ("pending", "in_progress", "completed")

ARTIFACT_STATUS = ("pending_review", "final", "deprecated")

STAGES = (
    {"name": "project_init", "label": "项目初始化", "expected_types": ("raw_script",)},
    {"name": "material_sorting", "label": "前期素材归类", "expected_types": ()},
    {"name": "supervisor_extraction", "label": "监制提取设定", "expected_types": ("setting", "character_design", "scene_design", "prop_design", "script")},
    {"name": "global_character_tasks", "label": "全局角色参考图任务生成", "expected_types": ()},
    {"name": "global_character_art", "label": "全局角色参考图绘制", "expected_types": ("character_ref",)},
    {"name": "global_prop_tasks", "label": "全局道具参考图任务生成", "expected_types": ()},
    {"name": "global_prop_art", "label": "全局道具参考图绘制", "expected_types": ("prop_ref",)},
    {"name": "global_scene_tasks", "label": "全局场景参考图任务生成", "expected_types": ()},
    {"name": "global_scene_art", "label": "全局场景参考图绘制", "expected_types": ("scene_ref",)},
    {"name": "episode_storyboard_script", "label": "剧集分镜脚本", "expected_types": ("storyboard",)},
    {"name": "episode_character_ref", "label": "剧集级角色妆造匹配清单", "expected_types": ()},
    {"name": "episode_prop_ref", "label": "剧集级道具参考图生成", "expected_types": ("prop_ref",)},
    {"name": "episode_scene_ref", "label": "剧集级场景参考图生成", "expected_types": ("scene_ref",)},
    {"name": "episode_storyboard_images", "label": "剧集参考图生成", "expected_types": ()},
    {"name": "asset_sync", "label": "资产同步", "expected_types": ()},
    {"name": "video_generation", "label": "视频生成", "expected_types": ("video", "video_manifest")},
    {"name": "delivery", "label": "交付归档", "expected_types": ()},
)

STAGE_NAMES = tuple(s["name"] for s in STAGES)

STAGE_EXPECTED = {s["name"]: s["expected_types"] for s in STAGES}

PROJECT_DIRS = (
    "前期采样/人物",
    "前期采样/场景",
    "前期采样/风格",
    "前期采样/道具",
    "全局依赖/角色设定/具体设定",
    "全局依赖/角色设定/角色参考图",
    "全局依赖/场景设定/具体设定",
    "全局依赖/场景设定/场景参考图",
    "全局依赖/道具设定/具体设定",
    "全局依赖/道具设定/道具参考图",
    "全局依赖/音色参考",
)

PROJECT_PLACEHOLDER_FILES = (
    ("全局依赖/全局设定.md", ""),
    ("全局依赖/角色设定/角色设定.md", "# 角色设定\n\n角色清单及路径索引占位，由 producer 在 supervisor_extraction 阶段维护。\n"),
    ("全局依赖/场景设定/场景设定.md", "# 场景设定\n\n场景清单及路径索引占位，由 producer 在 supervisor_extraction 阶段维护。\n"),
    ("全局依赖/道具设定/道具设定.md", "# 道具设定\n\n道具清单及路径索引占位，由 producer 在 supervisor_extraction 阶段维护。\n"),
)

ARTIFACT_TYPES = (
    "raw_script",
    "project_config",
    "script",
    "character_design",
    "character_ref",
    "scene_design",
    "scene_ref",
    "prop_design",
    "prop_ref",
    "storyboard",
    "poster",
    "setting",
    "reference",
    "audio_reference",
    "video",
    "video_manifest",
    "other",
)

TYPE_TO_DIR = {
    "raw_script": "原始剧本.md",
    # 仅 export/import 用途（导出 ZIP 内保留该文件），运行时配置存于 project_configs 表，不落盘
    "project_config": ".meta/projects/{uuid}/project_config.json",
    "script": "{episode}/剧本.md",
    "character_design": "全局依赖/角色设定/具体设定/{character}.md",
    "character_ref": "全局依赖/角色设定/角色参考图/{character}.png",
    "scene_design": "全局依赖/场景设定/具体设定/{scene}.md",
    "scene_ref": "全局依赖/场景设定/场景参考图/{scene}.png",
    "prop_design": "全局依赖/道具设定/具体设定/{prop}.md",
    "prop_ref": "全局依赖/道具设定/道具参考图/{prop}_{出现场合}_基准.png",
    "storyboard": "{episode}/分镜/{filename}",
    "poster": "{episode}/海报设计/{filename}",
    "setting": "全局依赖/全局设定.md",
    "reference": "前期采样/{subtype}/{filename}",
    "audio_reference": "全局依赖/音色参考/{filename}",
    "video": "{episode}/视频/{filename}",
    "video_manifest": "{episode}/视频/_manifest.json",
    "other": "{path}",
}

TYPE_TO_DIR_PLACEHOLDERS = {
    "{name}": "项目名（project/{name}/ 目录）",
    "{uuid}": "项目 UUID",
    "{episode}": "剧集号，如 01、02",
    "{character}": "角色名",
    "{scene}": "场景名",
    "{prop}": "道具名",
    "{出现场合}": "道具出现场合",
    "{subtype}": "参考素材子类型：人物/场景/风格/道具",
    "{filename}": "原始文件名",
    "{path}": "相对项目目录的自定义路径",
}

SCAN_SKIP = (
    ("全局依赖", "角色设定", "角色设定.md"),
    ("全局依赖", "场景设定", "场景设定.md"),
    ("全局依赖", "道具设定", "道具设定.md"),
)

ACTORS = (
    "user",
    "producer",
    "storyboard-generator",
    "roles-ref-generator",
    "scene-ref-generator",
    "prop-ref-generator",
    "art-director",
    "video-director-libtv",
    "project-coordinator",
)

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif")

CONFIG_FIELDS = {
    "workspace_id": None,
    "episodes": {},
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "model": "",
    "use_storyboard_images": None,
    "reference_image_mode": "visual_anchor",
    "mode": "mixed2video",
    "enable_sound": True,
    "storyboard_mode": "detailed",
    "has_audio_reference": False,
    "suppress_run": False,
    "video_prompt_mode": "optimized",
}

# 配置字段写权限白名单（ACL），权威源：doc/配置链路DB化_长期改造方案.md §2.3。
# 未在此列出的 CONFIG_FIELDS 字段默认仅 ("project-coordinator",) 可写。
CONFIG_WRITE_ACL = {
    "workspace_id": ("video-director-libtv", "project-coordinator"),
    "episodes": ("video-director-libtv", "project-coordinator"),
    "suppress_run": ("project-coordinator",),
}
