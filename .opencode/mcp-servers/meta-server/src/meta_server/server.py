"""Meta MCP Server — 项目元数据管理（FastMCP 标准范式）。

提供 8 个工具：meta_init_project / meta_advance_stage / meta_register_artifact /
meta_archive_artifact / meta_scan_and_register / meta_query / meta_export_project /
meta_delete_project。所有工具错误统一返回 {"error": str, "code": str}，不抛异常。
"""

import functools
import sys

from mcp.server.fastmcp import FastMCP

from . import service

mcp = FastMCP("meta")


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "code": "io"}
    return wrapper


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_init_project(
    name: str,
    type: str = "animation_series",
    config: dict | None = None,
    model: str | None = None,
    description: str = "",
    raw_script_path: str | None = None,
) -> dict:
    """创建新项目：生成 UUID、建目录骨架、初始化 17 阶段状态机与项目配置。

    参数：
    - name：项目名，同时是 project/{name}/ 目录名；不得与现存或已删除（deleted）项目重名
    - type：项目类型，animation_series | film | episode | other；阶段链固定为 17 阶段
    - config：项目配置字典，覆盖默认字段（aspect_ratio/resolution/reference_image_mode/mode/enable_sound/storyboard_mode/has_audio_reference/suppress_run/episodes/workspace_id 等）
    - model：视频生成模型名，等价于 config.model，优先级高于 config 内同名键
    - description：项目描述，可为空
    - raw_script_path：可选原始剧本路径；提供且为文件时复制为 project/{name}/原始剧本.md 并注册为 raw_script 产物

    行为：创建 PROJECT_DIRS 全部骨架目录与占位说明文件（全局设定.md 等）；projects 行 current_stage=project_init，stages 表 idx=0 为 in_progress，其余 pending；project_configs 行按 CONFIG_FIELDS 默认值补全；写入首条 project.created 事件。

    返回 {project_id, current_stage, directories_created, config[, raw_script]}；失败返回 {error, code}，code ∈ not_found/invalid/conflict/io。
    """
    return service.init_project(
        name=name, type=type, config=config, model=model,
        description=description, raw_script_path=raw_script_path,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_advance_stage(
    project_id: str,
    reason: str = "",
    skip: bool = False,
    skip_reason: str | None = None,
) -> dict:
    """将当前阶段推进一格：完成当前阶段并开启下一阶段。只允许逐阶段前进，禁止回退或越级。

    参数：
    - project_id：项目 UUID
    - reason：推进原因，写入事件 data.reason
    - skip：True 时跳过产物前置校验，事件类型改写为 stage.skip
    - skip_reason：skip=True 时必填，说明跳过原因

    前置校验：当前阶段 expected_types 中每个 type 在 artifacts 表必须至少存在一条 status='final' 记录；不满足时返回 {error, missing: [缺失type列表], code: 'invalid'}，且不修改任何状态。skip=True 跳过该校验。

    完成：当前阶段置 completed 并写 completed_at；下一阶段置 in_progress 并写 started_at；projects.current_stage/updated_at 同步更新；写 stage.transition（或 stage.skip）事件。

    最后一个阶段（delivery）推进完成后无下一阶段：projects.current_stage 保持 delivery，返回 finished=True；此后再次调用返回错误（code='invalid'）。
    """
    return service.advance_stage(
        project_id=project_id, reason=reason, skip=skip, skip_reason=skip_reason,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_register_artifact(
    project_id: str,
    type: str,
    path: str,
    stage: str | None = None,
    name: str | None = None,
    tags: list | None = None,
) -> dict:
    """注册产物（文件或目录）到 manifest，不移动文件。

    参数：
    - project_id：项目 UUID
    - type：产物类型，必须为合法枚举：raw_script/project_config/script/character_design/character_ref/scene_design/scene_ref/prop_design/prop_ref/storyboard/poster/setting/reference/audio_reference/video/video_manifest/other
    - path：产物路径，必须已存在（文件或目录）；相对路径按工作区根（META_PROJECT_ROOT）解析
    - stage：产物所属阶段，缺省取项目 current_stage；必须为该项目 17 阶段之一
    - name：展示名，缺省取路径最后一段
    - tags：标签列表，缺省为空列表

    哈希规则：目录 → dir-fast-{文件数}-{总字节}-{最大mtime_ns}；图片文件（png/jpg/jpeg/gif/webp/bmp/tiff/tif）→ fast-{mtime_ns}-{size}；其余文件 → sha256-{hex}。

    版本语义：同项目同路径已有 status='final' 记录时，旧行自动置 deprecated（刷新 updated_at），随后插入新 final 行；写 artifact.created 事件（data 含 hash/size/type/stage）。
    """
    return service.register_artifact(
        project_id=project_id, type=type, path=path, stage=stage, name=name, tags=tags,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_archive_artifact(
    project_id: str,
    src: str,
    type: str,
    stage: str | None = None,
    name: str | None = None,
    tags: list | None = None,
) -> dict:
    """归档产物：将临时文件移动到该 type 的规范目录并注册（归档 = 移动 + 注册，一个事务）。

    参数：
    - src：源路径，必须存在且位于工作区 temp/ 或 project/ 下（resolve 后不得逃出 META_PROJECT_ROOT）
    - type：产物类型（枚举同 meta_register_artifact）；目标目录由 TYPE_TO_DIR 模板推导，目录不存在则自动创建
    - stage/name/tags：语义同 meta_register_artifact

    目标文件名推导：{filename} 取源文件名；{episode} 从源路径中的纯数字目录推断（无则 00）；{character}/{scene}/{prop} 取源文件名去扩展名；{subtype} 取源父目录名；模板文件名含除 {filename} 外的其他占位符（如 prop_ref）时直接保留源文件名。目标已存在时拒绝覆盖（code='conflict'）。

    事件 artifact.archived，data 含 moved_from/src/dst/hash/size。
    """
    return service.archive_artifact(
        project_id=project_id, src=src, type=type, stage=stage, name=name, tags=tags,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_scan_and_register(
    project_id: str,
    dry_run: bool = False,
) -> dict:
    """扫描项目目录 project/{name}/ 并批量注册产物。

    分类规则：按 TYPE_TO_DIR 逆向映射（目录前缀 → type）分类——前期采样/** → reference；全局依赖/角色设定|场景设定|道具设定/{具体设定|参考图} → 对应 design/ref 类型；全局依赖/音色参考 → audio_reference；全局设定.md → setting；原始剧本.md → raw_script；{剧集号}/剧本.md → script；{剧集号}/分镜|海报设计|视频 → storyboard/poster/video(_manifest)。跳过隐藏文件与占位入口文档（角色设定.md 等三个清单占位）。

    无法归类的文件记入 pending_reviews 表（每次全量扫描会先清空该项目旧 pending 再重建）；已注册（status='final' 且路径一致）的文件跳过；数据库中 final 但磁盘文件已缺失的产物列入 missing（只报告，不改状态）。

    dry_run=True 时只报告不落库、不写事件。返回 {registered, pending, missing, dry_run}；dry_run 的 registered 为 {path, type} 简报，实跑为完整产物记录。
    """
    return service.scan_and_register(project_id=project_id, dry_run=dry_run)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_query(
    scope: str,
    project_id: str | None = None,
    filters: dict | None = None,
    limit: int = 50,
) -> dict:
    """只读查询，不产生任何写入。

    scope 取值：
    - projects：全部活跃项目（status != 'deleted'）及其当前阶段，按创建时间排序
    - stages：需 project_id；返回该项目 17 阶段（含 idx/status/started_at/completed_at），按 idx 排序
    - artifacts：可选 project_id；按 created_at 倒序；filters 支持 type/stage/status/name 等值过滤
    - events：可选 project_id；按 rowid 倒序（最新在前）；filters 支持 type/actor 等值过滤
    - pending：可选 project_id；待人工归类的文件清单

    filters 为列名到值的等值字典，传入 scope 不支持的键会返回 code='invalid'。limit 默认 50（上限 1000）。

    返回 {scope, count, items}。
    """
    return service.query(scope=scope, project_id=project_id, filters=filters, limit=limit)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_export_project(
    project_id: str,
    dest: str | None = None,
) -> dict:
    """从 SQLite 生成旧版四件套结构并打包 ZIP（只读数据库内容 + 写出 ZIP，不修改项目状态）。

    ZIP 内根目录为 {项目名}/，固定包含 5 个文件：project.json、stages.json、manifest.json、events.jsonl、project_config.json。
    其中 manifest.json 的 path 转为相对工作区根的路径；stages.json 每阶段 artifacts 填该阶段 final 产物的 name 列表；events.jsonl 按时间正序、紧凑序列化、中文明文。

    参数：
    - dest：ZIP 输出路径，缺省 {META_PROJECT_ROOT}/temp/导出/{项目名}_{YYYYMMDD_HHMMSS}.zip；相对路径按工作区根解析

    完成后追加 project.archived 事件。返回 {zip_path, files, artifacts, events}。
    """
    return service.export_project(project_id=project_id, dest=dest)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
@_safe
def meta_import_legacy(
    legacy_dir: str,
    name_override: str | None = None,
    keep_id: bool = True,
    scan_dir: str | None = None,
    scan_exclude: list[str] | None = None,
) -> dict:
    """将旧版 .meta/projects/{id}/ 四件套 JSON 元数据迁移为新库记录（一次性迁移工具）。

    参数：
    - legacy_dir：旧项目元数据目录（含 project.json/stages.json/manifest.json/events.jsonl/project_config.json）
    - name_override：新项目名；缺省取旧 project.json 的 name；与现存项目重名时返回 code='conflict'
    - keep_id：True 时保留旧 UUID 作为项目 id（若与现存冲突则自动生成新 UUID）
    - scan_dir：真实产物目录（相对 project/ 的路径，如 '星光耀' 或 '吉泰安防/系列二_侥幸的代价'）。
      提供时以 project/{scan_dir}/ 下真实文件为产物来源（_classify 自动分类，无法分类的
      进 pending_reviews），忽略 manifest 产物清单；缺省 None 时按 manifest 导入。
    - scan_exclude：scan_dir 下需跳过的顶层子目录名列表（如吉泰安防下的系列子项目目录）。

    迁移语义：
    - 项目：id/name/type/description/created_at/updated_at 尽量保留；type 非法值映射为 other；status 一律 active
    - 阶段：新库固定 17 阶段链；旧阶段按映射表归一到 idx，completed/skipped → completed，in_progress → 当前阶段，其余 pending
    - 产物：scan_dir 模式扫描真实目录分类注册；manifest 模式按映射表归一（旧版 50+ 种 → 新库 17 种），
      path 规范化，状态 active/created → final，hash 一律重算，path 无法归入 project/ 或 temp/、
      文件缺失、重复的产物跳过并列入 skipped
    - 事件：逐条导入，actor 映射到新库枚举，type/data/timestamp 原样保留
    - 配置：合并默认字段 + 旧 config，reference_image_mode 由 use_storyboard_images 推断

    返回 {project_id, name, type, current_stage, stages, artifacts, events, artifacts_source, skipped, warnings}；
    失败返回 {error, code}，code ∈ not_found/invalid/conflict/io。
    """
    return service.import_legacy(
        legacy_dir=legacy_dir, name_override=name_override, keep_id=keep_id,
        scan_dir=scan_dir, scan_exclude=scan_exclude,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    }
)
@_safe
def meta_delete_project(
    project_id: str,
    confirm_name: str,
) -> dict:
    """删除项目（不可逆，防误删）。

    confirm_name 必须与项目名完全一致，否则拒绝（code='invalid'）。

    行为：递归删除 project/{name}/ 实际目录——不使用 ignore_errors，逐文件/目录收集失败清单；数据库不删任何行，仅将 projects.status 置 'deleted'（stages/artifacts/events 全部保留供审计）；写 project.deleted 事件。

    返回 {removed_files, errors[, error, code]}。
    """
    return service.delete_project(project_id=project_id, confirm_name=confirm_name)


def main():
    """MCP server 启动入口，支持 `python -m meta_server` 和 entry_point `meta-server`。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    mcp.run()


if __name__ == "__main__":
    main()
