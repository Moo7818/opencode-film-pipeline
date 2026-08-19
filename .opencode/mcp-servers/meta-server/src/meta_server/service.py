"""业务逻辑层。纯函数式，显式传 db 路径；每个操作一个事务，结束时写事件。

硬约束：禁止读取任何产物文件的内容（只允许 stat/rename/move/copy 与本模块自身的 JSON 元数据写盘）；
SHA-256 只按二进制流计算，不做内容解析。
"""

import copy
import functools
import json
import os
import re
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import db, hashing, templates
from .templates import ARTIFACT_TYPES, CONFIG_FIELDS, CONFIG_WRITE_ACL, STAGES, TYPE_TO_DIR

ACTOR = "project-coordinator"

_EPISODE_RE = re.compile(r"^\d{1,3}$")

_QUERY_ALLOWED = {
    "projects": {"type", "status"},
    "stages": {"status"},
    "artifacts": {"type", "stage", "status", "name"},
    "events": {"type", "actor"},
    "pending": set(),
    "config": set(),
}

# 配置枚举字段的合法取值（标量字段，仅一层路径写入时校验）
_CONFIG_ENUMS = {
    "reference_image_mode": ("visual_anchor", "storyboard_images", "none"),
    "storyboard_mode": ("detailed", "simplified"),
    "video_prompt_mode": ("optimized", "raw"),
}

# 配置布尔字段（标量字段，仅一层路径写入时校验）
_CONFIG_BOOL_FIELDS = ("enable_sound", "suppress_run", "has_audio_reference")

_PROJECT_CONFIG_REJECT = (
    "project_config 类型禁止注册：运行时配置存于 project_configs 表，不再落盘该文件"
)


class _Fail(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def _fail(message, code):
    raise _Fail(message, code)


def _public(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _Fail as e:
            return {"error": e.message, "code": e.code}
        except sqlite3.IntegrityError as e:
            return {"error": f"数据库约束失败: {e}", "code": "conflict"}
        except OSError as e:
            return {"error": f"文件系统错误: {e}", "code": "io"}
    return wrapper


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(conn, project_id, type_, data):
    conn.execute(
        "INSERT INTO events (timestamp, type, actor, project_id, data) VALUES (?,?,?,?,?)",
        (_now(), type_, ACTOR, project_id, json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
    )


def _root() -> Path:
    return db.project_root()


def _project_dir(name) -> Path:
    return _root() / "project" / name


def _resolve(path) -> Path:
    p = Path(path).expanduser()
    return p.resolve() if p.is_absolute() else (_root() / p).resolve()


def _get_project(conn, project_id, active_only=True):
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        _fail(f"项目不存在: {project_id}", "not_found")
    if active_only and row["status"] != "active":
        _fail(f"项目已删除: {row['name']}", "conflict")
    return row


def _fingerprint(path: Path):
    if path.is_dir():
        stats = hashing.dir_stats(path)
        return hashing.dir_fingerprint(path, stats), stats[1]
    st = path.stat()
    return hashing.fast_fingerprint(path), st.st_size


def _register_artifact(conn, project, type_, path: Path, stage=None, name=None, tags=None):
    pid = project["id"]
    if type_ not in ARTIFACT_TYPES:
        _fail(f"非法产物类型: {type_}，允许值 {list(ARTIFACT_TYPES)}", "invalid")
    if stage is None:
        stage = project["current_stage"]
    hit = conn.execute("SELECT 1 FROM stages WHERE project_id = ? AND name = ?", (pid, stage)).fetchone()
    if hit is None:
        _fail(f"非法阶段: {stage}", "invalid")
    if not path.exists():
        _fail(f"路径不存在: {path}", "not_found")
    if name is None:
        name = path.name
    digest, size = _fingerprint(path)
    now = _now()
    aid = str(uuid.uuid4())
    conn.execute(
        "UPDATE artifacts SET status = 'deprecated', updated_at = ? WHERE project_id = ? AND path = ? AND status = 'final'",
        (now, pid, str(path)),
    )
    conn.execute(
        "INSERT INTO artifacts (id, project_id, type, name, path, stage, status, hash, size, tags, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, pid, type_, name, str(path), stage, "final", digest, size, json.dumps(tags or [], ensure_ascii=False), now, now),
    )
    _emit(conn, pid, "artifact.created", {
        "artifact_id": aid,
        "type": type_,
        "path": str(path),
        "name": name,
        "hash": digest,
        "size": size,
        "stage": stage,
    })
    return {
        "id": aid,
        "project_id": pid,
        "type": type_,
        "name": name,
        "path": str(path),
        "stage": stage,
        "status": "final",
        "hash": digest,
        "size": size,
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
    }


def _fill_tokens(text, values) -> str:
    return re.sub(r"\{([^{}]+)\}", lambda m: str(values.get(m.group(1), m.group(0))), text)


def _episode_hint(p: Path, root: Path) -> str:
    try:
        parts = p.relative_to(root).parts
    except ValueError:
        parts = p.parts
    for part in parts:
        if _EPISODE_RE.match(part):
            return part
    return "00"


def _canonical_dest(project, type_: str, src: Path) -> Path:
    if type_ == "project_config":
        return _root() / ".meta" / "projects" / project["id"] / "project_config.json"
    tmpl = TYPE_TO_DIR[type_]
    stem = src.stem
    values = {
        "filename": src.name,
        "character": stem,
        "scene": stem,
        "prop": stem,
        "subtype": src.parent.name,
        "episode": _episode_hint(src, _root()),
        "path": src.name,
        "uuid": project["id"],
        "name": project["name"],
    }
    parts = tmpl.split("/")
    base = parts[-1]
    if "{filename}" not in base and "{" in base:
        base = src.name
    else:
        base = _fill_tokens(base, values)
    dir_parts = [_fill_tokens(p, values) for p in parts[:-1]]
    return _project_dir(project["name"]).joinpath(*dir_parts, base)


_GLOBAL_SUBTYPE_MAP = {
    ("角色设定", "具体设定"): "character_design",
    ("角色设定", "角色参考图"): "character_ref",
    ("场景设定", "具体设定"): "scene_design",
    ("场景设定", "场景参考图"): "scene_ref",
    ("道具设定", "具体设定"): "prop_design",
    ("道具设定", "道具参考图"): "prop_ref",
}


def _classify(parts) -> str | None:
    if parts == ("原始剧本.md",):
        return "raw_script"
    if parts == ("全局依赖", "全局设定.md"):
        return "setting"
    if len(parts) >= 2 and parts[0] == "前期采样":
        return "reference"
    if parts[0] == "产品采样" or parts[0] == "采样":
        return "reference"
    if parts[0] == "全局依赖":
        if len(parts) == 3 and parts[1] == "音色参考":
            return "audio_reference"
        if len(parts) >= 4 and (parts[1], parts[2]) in _GLOBAL_SUBTYPE_MAP:
            return _GLOBAL_SUBTYPE_MAP[(parts[1], parts[2])]
        if len(parts) >= 3 and (parts[1],) in ((("角色设定",) if parts[2] == "角色参考图" else ()),):
            return "character_ref"
        # 兼容 全局依赖/角色参考图/xxx.png（无 设定 二层目录）的布局
        if len(parts) >= 3 and parts[1] in ("角色参考图", "角色设定"):
            return "character_ref" if parts[1] == "角色参考图" else "character_design"
        if len(parts) >= 3 and parts[1] in ("场景参考图", "场景设定"):
            return "scene_ref" if parts[1] == "场景参考图" else "scene_design"
        if len(parts) >= 3 and parts[1] in ("道具参考图", "道具设定"):
            return "prop_ref" if parts[1] == "道具参考图" else "prop_design"
        return None
    # 剧集目录：纯数字（01）或 EP 前缀（EP01 / EP01_标题）
    if len(parts) >= 2 and (_EPISODE_RE.match(parts[0]) or re.match(r"^EP\d{1,3}(?:_|$)", parts[0])):
        if parts[1] in ("分镜", "分镜图") or (parts[1] == "分镜" and len(parts) >= 3):
            return "storyboard"
        if len(parts) >= 2 and parts[1] == "剧本.md":
            return "script"
        if parts[1] == "海报设计" or parts[1] == "海报":
            return "poster"
        if parts[1] == "视频":
            return "video_manifest" if parts[-1] == "_manifest.json" else "video"
        if parts[1] == "角色参考图":
            return "character_ref"
        if parts[1] == "场景参考图":
            return "scene_ref"
        if parts[1] == "道具参考图":
            return "prop_ref"
        if parts[1] == "角色设定":
            return "character_design"
        if parts[1] == "场景设定":
            return "scene_design"
        if parts[1] == "道具设定":
            return "prop_design"
        if parts[1] == "音色参考":
            return "audio_reference"
    # 无剧集前缀但目录直接是类型目录（如 EP03 内容平铺：分镜/、角色参考图/）
    if len(parts) >= 2:
        first = parts[0]
        if first == "分镜":
            return "storyboard"
        if first == "角色参考图":
            return "character_ref"
        if first == "场景参考图":
            return "scene_ref"
        if first == "道具参考图":
            return "prop_ref"
        if first == "角色设定":
            return "character_design"
        if first == "场景设定":
            return "scene_design"
        if first == "道具设定":
            return "prop_design"
        if first == "海报" or first == "海报设计":
            return "poster"
        if first == "视频":
            return "video_manifest" if parts[-1] == "_manifest.json" else "video"
        if first == "音色参考":
            return "audio_reference"
    # 顶层文件启发式
    fn = parts[-1].lower()
    if fn.endswith("_manifest.json") and "视频" in "/".join(parts[:-1]):
        return "video_manifest"
    if fn == "mv分镜脚本.json" or (len(parts) == 1 and ("分镜" in parts[0] or "分镜脚本" in parts[0])):
        return "storyboard"
    if len(parts) == 1 and ("设定" in parts[0] or "设定_" in parts[0]):
        return "setting"
    if len(parts) == 1 and "剧本" in parts[0]:
        return "script"
    return None


def _rmtree_collect(path: Path):
    removed = 0
    errors = []
    if not path.exists():
        return removed, errors
    entries = []
    for dirpath, dirnames, filenames in os.walk(path):
        for fn in filenames:
            entries.append(Path(dirpath) / fn)
        for dn in dirnames:
            entries.append(Path(dirpath) / dn)
    entries.append(path)
    entries.sort(key=lambda p: len(p.parts), reverse=True)
    for entry in entries:
        try:
            if entry.is_dir() and not entry.is_symlink():
                entry.rmdir()
            else:
                entry.unlink()
            removed += 1
        except OSError as exc:
            errors.append({"path": str(entry), "error": str(exc)})
    return removed, errors


@_public
def init_project(name, type="animation_series", config=None, model=None, description="", raw_script_path=None, dbp=None):
    name = (name or "").strip()
    if not name:
        _fail("项目名不能为空", "invalid")
    if type not in templates.PROJECT_TYPES:
        _fail(f"非法项目类型: {type}，允许值 {list(templates.PROJECT_TYPES)}", "invalid")
    pdir = _project_dir(name)
    if pdir.exists():
        _fail(f"项目目录已存在: {pdir}", "conflict")
    src_script = None
    if raw_script_path:
        src_script = _resolve(raw_script_path)
        if not src_script.is_file():
            _fail(f"raw_script_path 不是文件: {src_script}", "not_found")
    created_dirs = list(templates.PROJECT_DIRS)
    for rel in templates.PROJECT_DIRS:
        (pdir / rel).mkdir(parents=True, exist_ok=True)
    for rel, content in templates.PROJECT_PLACEHOLDER_FILES:
        target = pdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    pid = str(uuid.uuid4())
    now = _now()
    merged = dict(CONFIG_FIELDS)
    if isinstance(config, dict):
        merged.update(config)
    if model:
        merged["model"] = model
    with db.connect(dbp) as conn:
        dup = conn.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        if dup is not None:
            _fail(f"项目名已存在（含已删除项目）: {name}", "conflict")
        with conn:
            conn.execute(
                "INSERT INTO projects (id, name, type, status, current_stage, created_at, updated_at, description)"
                " VALUES (?,?,?,'active',?,?,?,?)",
                (pid, name, type, STAGES[0]["name"], now, now, description or ""),
            )
            for i, st in enumerate(STAGES):
                if i == 0:
                    conn.execute(
                        "INSERT INTO stages (project_id, idx, name, label, status, started_at, completed_at)"
                        " VALUES (?,?,?,?, 'in_progress', ?, NULL)",
                        (pid, i, st["name"], st["label"], now),
                    )
                else:
                    conn.execute(
                        "INSERT INTO stages (project_id, idx, name, label, status, started_at, completed_at)"
                        " VALUES (?,?,?,?, 'pending', NULL, NULL)",
                        (pid, i, st["name"], st["label"]),
                    )
            conn.execute(
                "INSERT INTO project_configs (project_id, config) VALUES (?,?)",
                (pid, json.dumps(merged, ensure_ascii=False)),
            )
            _emit(conn, pid, "project.created", {
                "name": name,
                "type": type,
                "directories": created_dirs,
                "description": description or "",
            })
    result = {
        "project_id": pid,
        "current_stage": STAGES[0]["name"],
        "directories_created": created_dirs,
        "config": merged,
    }
    if src_script is not None:
        dest = pdir / "原始剧本.md"
        shutil.copy2(src_script, dest)
        with db.connect(dbp) as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
            with conn:
                art = _register_artifact(conn, row, "raw_script", dest, stage=STAGES[0]["name"], name="原始剧本.md")
        result["raw_script"] = {k: art[k] for k in ("id", "type", "path", "hash", "size", "stage")}
    return result


@_public
def advance_stage(project_id, reason="", skip=False, skip_reason=None, dbp=None):
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id)
        with conn:
            cur = conn.execute(
                "SELECT * FROM stages WHERE project_id = ? AND name = ?",
                (project_id, project["current_stage"]),
            ).fetchone()
            if cur is None:
                _fail("阶段状态异常：current_stage 无对应行", "invalid")
            if cur["status"] == "completed":
                _fail(f"阶段 {cur['name']} 已完成，不可重复推进或回退", "invalid")
            if skip:
                if not skip_reason:
                    _fail("skip=True 必须提供 skip_reason", "invalid")
            else:
                expected = templates.STAGE_EXPECTED[cur["name"]]
                missing = [
                    t for t in expected
                    if conn.execute(
                        "SELECT 1 FROM artifacts WHERE project_id = ? AND type = ? AND status = 'final'",
                        (project_id, t),
                    ).fetchone() is None
                ]
                if missing:
                    return {
                        "error": f"阶段 {cur['name']} 缺少 final 产物: {missing}",
                        "code": "invalid",
                        "missing": missing,
                        "current_stage": cur["name"],
                    }
            now = _now()
            conn.execute(
                "UPDATE stages SET status = 'completed', completed_at = ? WHERE project_id = ? AND name = ?",
                (now, project_id, cur["name"]),
            )
            nxt = conn.execute(
                "SELECT * FROM stages WHERE project_id = ? AND idx = ?",
                (project_id, cur["idx"] + 1),
            ).fetchone()
            if nxt is not None:
                conn.execute(
                    "UPDATE stages SET status = 'in_progress', started_at = ? WHERE project_id = ? AND name = ?",
                    (now, project_id, nxt["name"]),
                )
                conn.execute(
                    "UPDATE projects SET current_stage = ?, updated_at = ? WHERE id = ?",
                    (nxt["name"], now, project_id),
                )
            else:
                conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
            event_type = "stage.skip" if skip else "stage.transition"
            data = {"from": cur["name"], "to": nxt["name"] if nxt is not None else None, "reason": reason}
            if skip:
                data["skip_reason"] = skip_reason
            _emit(conn, project_id, event_type, data)
            return {
                "project_id": project_id,
                "from": cur["name"],
                "to": nxt["name"] if nxt is not None else None,
                "current_stage": nxt["name"] if nxt is not None else cur["name"],
                "finished": nxt is None,
            }


@_public
def register_artifact(project_id, type, path, stage=None, name=None, tags=None, dbp=None):
    if type == "project_config":
        _fail(_PROJECT_CONFIG_REJECT, "invalid")
    p = _resolve(path)
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id)
        with conn:
            return _register_artifact(conn, project, type, p, stage, name, tags)


@_public
def archive_artifact(project_id, src, type, stage=None, name=None, tags=None, dbp=None):
    if type == "project_config":
        _fail(_PROJECT_CONFIG_REJECT, "invalid")
    if type not in ARTIFACT_TYPES:
        _fail(f"非法产物类型: {type}，允许值 {list(ARTIFACT_TYPES)}", "invalid")
    s = _resolve(src)
    if not s.exists():
        _fail(f"src 不存在: {s}", "not_found")
    root = _root()
    try:
        rel = s.relative_to(root)
    except ValueError:
        _fail(f"src 必须位于工作区根内: {s}", "invalid")
    if not rel.parts or rel.parts[0] not in ("temp", "project"):
        _fail("src 必须位于 temp/ 或 project/ 下", "invalid")
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id)
        with conn:
            dest = _canonical_dest(project, type, s)
            if dest.exists():
                _fail(f"目标已存在，禁止覆盖: {dest}", "conflict")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(dest))
            art = _register_artifact(conn, project, type, dest, stage, name, tags)
            _emit(conn, project_id, "artifact.archived", {
                "artifact_id": art["id"],
                "src": str(s),
                "dst": str(dest),
                "moved_from": str(s),
                "type": type,
                "hash": art["hash"],
                "size": art["size"],
            })
            out = dict(art)
            out["moved_from"] = str(s)
            return out


@_public
def scan_and_register(project_id, dry_run=False, dbp=None):
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id)
        pdir = _project_dir(project["name"])
        if not pdir.is_dir():
            _fail(f"项目目录不存在: {pdir}", "not_found")
        registered_final = {
            r["path"] for r in conn.execute(
                "SELECT path FROM artifacts WHERE project_id = ? AND status = 'final'", (project_id,)
            )
        }
        to_register = []
        pending = []
        for dirpath, dirnames, filenames in os.walk(pdir):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if fn.startswith("."):
                    continue
                fpath = Path(dirpath) / fn
                rel = fpath.relative_to(pdir)
                if rel.parts in templates.SCAN_SKIP:
                    continue
                if str(fpath) in registered_final:
                    continue
                type_ = _classify(rel.parts)
                if type_ is None:
                    st = fpath.stat()
                    pending.append({
                        "id": str(uuid.uuid4()),
                        "path": str(fpath),
                        "size": st.st_size,
                        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    })
                else:
                    to_register.append((fpath, type_))
        missing = []
        for r in conn.execute(
            "SELECT id, path, type FROM artifacts WHERE project_id = ? AND status = 'final'", (project_id,)
        ):
            if not Path(r["path"]).exists():
                missing.append({"id": r["id"], "path": r["path"], "type": r["type"]})
        registered = []
        if not dry_run:
            with conn:
                for fpath, type_ in to_register:
                    registered.append(_register_artifact(conn, project, type_, fpath))
                conn.execute("DELETE FROM pending_reviews WHERE project_id = ?", (project_id,))
                now = _now()
                for item in pending:
                    conn.execute(
                        "INSERT INTO pending_reviews (id, project_id, path, size, mtime, created_at) VALUES (?,?,?,?,?,?)",
                        (item["id"], project_id, item["path"], item["size"], item["mtime"], now),
                    )
                _emit(conn, project_id, "artifact.scan", {
                    "registered": len(registered),
                    "pending": len(pending),
                    "missing": len(missing),
                    "dry_run": False,
                })
        else:
            registered = [{"path": str(f), "type": t} for f, t in to_register]
        return {
            "project_id": project_id,
            "registered": registered,
            "pending": pending,
            "missing": missing,
            "dry_run": dry_run,
        }


@_public
def query(scope, project_id=None, project_name=None, filters=None, limit=50, dbp=None):
    if scope not in _QUERY_ALLOWED:
        _fail(f"非法 scope: {scope}，允许值 {sorted(_QUERY_ALLOWED)}", "invalid")
    filters = dict(filters or {})
    unknown = set(filters) - _QUERY_ALLOWED[scope]
    if unknown:
        _fail(f"scope={scope} 不支持的过滤键: {sorted(unknown)}，允许值 {sorted(_QUERY_ALLOWED[scope])}", "invalid")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    if limit <= 0 or limit > 1000:
        limit = 50
    with db.connect(dbp) as conn:
        if scope == "config":
            if not project_id and not project_name:
                _fail("需要 project_id 或 project_name", "invalid")
            # project_id 与 project_name 皆提供时以 project_id 为准
            if project_id:
                row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM projects WHERE name = ?", (project_name,)).fetchone()
            if row is None:
                _fail(f"项目不存在: {project_id or project_name}", "not_found")
            cfg_row = conn.execute(
                "SELECT config FROM project_configs WHERE project_id = ?", (row["id"],)
            ).fetchone()
            merged = dict(CONFIG_FIELDS)
            if cfg_row is not None:
                try:
                    stored = json.loads(cfg_row["config"] or "{}")
                except (TypeError, ValueError):
                    stored = {}
                if isinstance(stored, dict):
                    merged.update(stored)
            return {
                "scope": "config",
                "count": 1,
                "project_id": row["id"],
                "name": row["name"],
                "updated_at": row["updated_at"],
                "config": merged,
            }
        if scope == "projects":
            sql = "SELECT id, name, type, status, current_stage, created_at, updated_at, description FROM projects WHERE status != 'deleted'"
            params = []
            for key in ("type", "status"):
                if key in filters:
                    sql += f" AND {key} = ?"
                    params.append(filters[key])
            sql += " ORDER BY created_at"
            items = [dict(r) for r in conn.execute(sql, params)]
        elif scope == "stages":
            if not project_id:
                _fail("scope=stages 需要 project_id", "invalid")
            _get_project(conn, project_id, active_only=False)
            sql = "SELECT idx, name, label, status, started_at, completed_at FROM stages WHERE project_id = ?"
            params = [project_id]
            if "status" in filters:
                sql += " AND status = ?"
                params.append(filters["status"])
            sql += " ORDER BY idx"
            items = [dict(r) for r in conn.execute(sql, params)]
        elif scope == "artifacts":
            sql = "SELECT * FROM artifacts WHERE 1=1"
            params = []
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            for key in ("type", "stage", "status", "name"):
                if key in filters:
                    sql += f" AND {key} = ?"
                    params.append(filters[key])
            sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
            params.append(limit)
            items = []
            for r in conn.execute(sql, params):
                d = dict(r)
                try:
                    d["tags"] = json.loads(d.get("tags") or "[]")
                except (TypeError, ValueError):
                    d["tags"] = []
                items.append(d)
        elif scope == "events":
            sql = "SELECT rowid AS id, timestamp, type, actor, project_id, data FROM events WHERE 1=1"
            params = []
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            for key in ("type", "actor"):
                if key in filters:
                    sql += f" AND {key} = ?"
                    params.append(filters[key])
            sql += " ORDER BY rowid DESC LIMIT ?"
            params.append(limit)
            items = []
            for r in conn.execute(sql, params):
                d = dict(r)
                try:
                    d["data"] = json.loads(d.get("data") or "{}")
                except (TypeError, ValueError):
                    d["data"] = {}
                items.append(d)
        else:
            sql = "SELECT id, project_id, path, size, mtime, created_at FROM pending_reviews WHERE 1=1"
            params = []
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            sql += " ORDER BY created_at, path"
            items = [dict(r) for r in conn.execute(sql, params)]
        return {"scope": scope, "count": len(items), "items": items}


@_public
def update_config(project_id, updates, actor, dbp=None):
    """更新项目配置：点路径局部更新 + 字段级写权限白名单（ACL）+ 单事务 read-merge-write。

    规格来源：doc/配置链路DB化_长期改造方案.md §3.2。校验失败不改任何状态。
    """
    if actor not in templates.ACTORS:
        _fail(f"非法 actor: {actor}，允许值 {list(templates.ACTORS)}", "invalid")
    if not isinstance(updates, dict) or not updates:
        _fail("updates 必须为非空 dict（键为点路径，如 episodes.EP01.canvas_uuid）", "invalid")
    paths = []
    for key in updates:
        parts = str(key).split(".")
        # 两层指：根键 + 最多两段子键路径（如 episodes.EP01.canvas_uuid），段数 4 及以上 invalid
        if len(parts) > 3:
            _fail(f"点路径最多两层（如 episodes.EP01.canvas_uuid），收到: {key}", "invalid")
        root = parts[0]
        if root not in CONFIG_FIELDS:
            _fail(f"未知配置字段: {root}，允许值 {sorted(CONFIG_FIELDS)}", "invalid")
        allowed = CONFIG_WRITE_ACL.get(root, ("project-coordinator",))
        if actor not in allowed:
            _fail(f"ACL 拒绝: actor={actor} 无权写配置字段 {root}，允许的 actor: {list(allowed)}", "invalid")
        if len(parts) == 1:
            if root in _CONFIG_ENUMS and updates[key] not in _CONFIG_ENUMS[root]:
                _fail(f"非法枚举值: {root}={updates[key]!r}，允许值 {list(_CONFIG_ENUMS[root])}", "invalid")
            if root in _CONFIG_BOOL_FIELDS and not isinstance(updates[key], bool):
                _fail(f"配置字段 {root} 必须为 bool，得到 {type(updates[key]).__name__}", "invalid")
        paths.append((parts, key))
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id)
        with conn:
            row = conn.execute(
                "SELECT config FROM project_configs WHERE project_id = ?", (project_id,)
            ).fetchone()
            merged = dict(CONFIG_FIELDS)
            if row is not None:
                try:
                    stored = json.loads(row["config"] or "{}")
                except (TypeError, ValueError):
                    stored = {}
                if isinstance(stored, dict):
                    merged.update(stored)
            for parts, key in paths:
                if len(parts) == 1:
                    merged[parts[0]] = updates[key]
                    continue
                head = parts[0]
                if not isinstance(merged.get(head), dict):
                    _fail(f"两层路径 {key} 要求配置字段 {head} 为 dict", "invalid")
                # 深拷贝子树，避免原地修改 CONFIG_FIELDS 共享的默认容器
                subtree = copy.deepcopy(merged[head])
                node = subtree
                for sub in parts[1:-1]:
                    cur = node.get(sub)
                    if cur is not None and not isinstance(cur, dict):
                        _fail(f"两层路径 {key} 要求 {head}.{sub} 为 dict", "invalid")
                    if cur is None:
                        cur = {}
                        node[sub] = cur
                    node = cur
                node[parts[-1]] = updates[key]
                merged[head] = subtree
            if row is not None:
                conn.execute(
                    "UPDATE project_configs SET config = ? WHERE project_id = ?",
                    (json.dumps(merged, ensure_ascii=False), project_id),
                )
            else:
                conn.execute(
                    "INSERT INTO project_configs (project_id, config) VALUES (?,?)",
                    (project_id, json.dumps(merged, ensure_ascii=False)),
                )
            now = _now()
            conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
            _emit(conn, project_id, "config.updated", {
                "actor": actor,
                "changed_keys": sorted(updates),
                "updates": updates,
            })
            return {"config": merged, "changed_keys": sorted(updates)}


@_public
def export_project(project_id, dest=None, dbp=None):
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id, active_only=False)
        name = project["name"]
        root = _root()

        def rel(p) -> str:
            try:
                return Path(p).relative_to(root).as_posix()
            except ValueError:
                return str(p)

        cfg_row = conn.execute("SELECT config FROM project_configs WHERE project_id = ?", (project_id,)).fetchone()
        config = json.loads(cfg_row["config"]) if cfg_row is not None else {}
        stages = [dict(r) for r in conn.execute(
            "SELECT * FROM stages WHERE project_id = ? ORDER BY idx", (project_id,)
        )]
        arts = [dict(r) for r in conn.execute(
            "SELECT * FROM artifacts WHERE project_id = ? ORDER BY created_at, rowid", (project_id,)
        )]
        evs = list(conn.execute(
            "SELECT timestamp, type, actor, project_id, data FROM events WHERE project_id = ? ORDER BY rowid",
            (project_id,),
        ))
        project_json = {
            "_version": 1,
            "id": project["id"],
            "name": name,
            "type": project["type"],
            "status": project["status"],
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
            "description": project["description"],
            "current_stage": project["current_stage"],
        }
        stages_json = {
            "_version": 1,
            "current": project["current_stage"],
            "stages": [
                {
                    "name": s["name"],
                    "label": s["label"],
                    "status": s["status"],
                    "started_at": s["started_at"],
                    "completed_at": s["completed_at"],
                    "artifacts": [a["name"] for a in arts if a["stage"] == s["name"] and a["status"] == "final"],
                }
                for s in stages
            ],
        }
        manifest_json = {
            "_version": 1,
            "artifacts": [
                {
                    "id": a["id"],
                    "type": a["type"],
                    "name": a["name"],
                    "path": rel(a["path"]),
                    "stage": a["stage"],
                    "status": a["status"],
                    "created_at": a["created_at"],
                    "updated_at": a["updated_at"],
                    "hash": a["hash"],
                    "size": a["size"],
                    "tags": json.loads(a.get("tags") or "[]"),
                }
                for a in arts
            ],
        }
        events_lines = [
            json.dumps(
                {"timestamp": e["timestamp"], "type": e["type"], "actor": e["actor"], "project_id": e["project_id"], "data": json.loads(e["data"])},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for e in evs
        ]
        if dest is None:
            dest = root / "temp" / "导出" / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        dest_path = Path(dest).expanduser()
        if not dest_path.is_absolute():
            dest_path = root / dest_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        files = {
            "project.json": json.dumps(project_json, ensure_ascii=False, indent=2),
            "stages.json": json.dumps(stages_json, ensure_ascii=False, indent=2),
            "manifest.json": json.dumps(manifest_json, ensure_ascii=False, indent=2),
            "events.jsonl": ("\n".join(events_lines) + "\n") if events_lines else "",
            "project_config.json": json.dumps(config, ensure_ascii=False, indent=2),
        }
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn, content in files.items():
                zf.writestr(f"{name}/{fn}", content)
        with conn:
            _emit(conn, project_id, "project.archived", {
                "name": name,
                "id": project_id,
                "zip_path": str(dest_path),
                "files": list(files),
            })
        return {
            "project_id": project_id,
            "name": name,
            "zip_path": str(dest_path),
            "files": [f"{name}/{fn}" for fn in files],
            "artifacts": len(arts),
            "events": len(events_lines),
        }


# ---------------------------------------------------------------------------
# 旧版 JSON 元数据迁移（import_legacy）
# ---------------------------------------------------------------------------

# 旧版产物 type -> 新库枚举
_LEGACY_TYPE_MAP = {
    "raw_script": "raw_script",
    "project_config": "project_config",
    "script": "script",
    "character_design": "character_design",
    "character_ref": "character_ref",
    "scene_design": "scene_design",
    "scene_ref": "scene_ref",
    "prop_design": "prop_design",
    "prop_ref": "prop_ref",
    "storyboard": "storyboard",
    "storyboard_ref": "storyboard",
    "storyboard_image": "storyboard",
    "storyboard_group": "storyboard",
    "storyboard_script": "storyboard",
    "storyboard_direction": "storyboard",
    "storyboard_image_tasks": "other",
    "poster": "poster",
    "setting": "setting",
    "reference": "reference",
    "reference_image": "reference",
    "product_sample": "reference",
    "audio_reference": "audio_reference",
    "video": "video",
    "video_segment": "video",
    "video_group": "video",
    "video_node": "video",
    "video_manifest": "video_manifest",
    "episode_script": "script",
    "group_script": "storyboard",
    "asset_sync": "other",
    "task_table": "other",
    "task_manifest": "other",
    "task_json": "other",
    "project_rule": "other",
    "character_wardrobe": "character_design",
    "character_ref_tasks": "other",
    "character_ref_task": "other",
    "character_design_index": "other",
    "scene_ref_tasks": "other",
    "scene_ref_task": "other",
    "scene_design_index": "other",
    "prop_ref_tasks": "other",
    "prop_ref_task": "other",
    "prop_design_index": "other",
    "subproject_reference": "other",
    "canvas": "other",
}

# 旧版事件 actor -> 新库 actor 枚举
_LEGACY_ACTOR_MAP = {
    "coordinator": "project-coordinator",
    "project-coordinator": "project-coordinator",
    "producer": "producer",
    "user": "user",
    "art-director": "art-director",
    "character-director": "roles-ref-generator",
    "video-director": "video-director-libtv",
    "orchestrator": "project-coordinator",
    "storyboard-generator": "storyboard-generator",
    "scene-ref-generator": "scene-ref-generator",
    "prop-ref-generator": "prop-ref-generator",
    "roles-ref-generator": "roles-ref-generator",
}

# 旧版阶段名 -> 新 17 阶段 idx（尽力映射；未覆盖名称不参与状态重建）
_LEGACY_STAGE_IDX = {
    "project_init": 0, "material_sorting": 1, "supervisor_extraction": 2,
    "global_character_tasks": 3, "global_character_art": 4,
    "global_prop_tasks": 5, "global_prop_art": 6,
    "global_scene_tasks": 7, "global_scene_art": 8,
    "episode_storyboard_script": 9, "episode_storyboard": 9,
    "episode_character_ref": 10,
    "episode_prop_ref": 11, "episode_scene_ref": 12,
    "episode_storyboard_images": 13,
    "asset_sync": 14, "video_generation": 15, "delivery": 16,
    "planning": 0, "pre_production": 2, "preproduction": 2,
    "production": 15, "post_production": 15, "postproduction": 15,
    "review": 16, "completed": 16, "init": 0,
    "1_项目初始化": 0, "项目初始化": 0, "stage1_project_init": 0,
    "2_监制提取设定": 2, "监制提取设定": 2, "监制提取设定（全局）": 2,
    "supervisor_extract": 2,
    "setting_extraction": 2, "前期设定": 2, "剧本创作": 2,
    "角色场景道具设计": 2, "EP06~EP10 监制提取设定": 2,
    "3_全局视觉资产生成": 3, "全局视觉资产生成": 3, "global_visual_asset": 3,
    "global_assets": 4, "角色设定与资产制作": 4,
    "3_角色参考图生成": 4, "角色参考图生成": 4, "角色参考图": 4, "角色设定": 4,
    "5_道具参考图生成": 6, "道具参考图生成": 6, "道具参考图": 6, "道具设定": 6,
    "4_场景参考图生成": 8, "场景参考图生成": 8, "场景参考图": 8, "场景设定": 8,
    "4_拆解分镜（EP01）": 9, "拆解分镜": 9, "分镜剧": 9, "storyboard": 9,
    "EP01~EP05 拆解分镜": 9, "EP06~EP10 拆解分镜": 9,
    "stage3_episode_script": 9, "stage4_storyboard": 9,
    "episode_assets": 11,
    "5_剧集级参考图（EP01）": 12, "剧集级参考图": 12,
    "stage5_episode_ref": 12, "ep08_15_storyboard_ref": 12,
    "6_分镜制作": 13, "分镜制作": 13, "EP01分镜制作": 13,
    "EP01~EP05 分镜制作": 13, "EP02-EP05分镜制作": 13, "EP06-EP20分镜制作": 13,
    "storyboard_remake": 13, "ep08_15_storyboard": 13,
    "EP01~EP05 画布节点": 14, "EP06~EP10 画布节点": 14, "画布节点": 14,
    "6_视频生成（EP01）": 15, "7_视频生成": 15, "视频生成": 15,
    "视频生成（EP01）": 15, "video_production": 15, "episode_video": 15,
    "episode_video_remake": 15, "ep08_15_video": 15, "stage6_video": 15,
    "后期合成": 15, "按集执行(EP01)": 15, "按集执行(EP02)": 15,
    "按集执行(EP03)": 15, "按集执行(EP04)": 15,
    "8_输出交付": 16, "输出交付": 16, "交付归档": 16,
}


def _legacy_stage_idx(name, project_stages=None) -> int | None:
    """旧阶段名 -> 新 17 阶段 idx。

    project_stages：旧 stages.json 的有序阶段列表（含 name/status），用于解析
    数字或 stageN 形式的产物 stage 字段（1-based 索引查旧阶段名后递归映射）。
    """
    if name is None:
        return None
    if isinstance(name, int):
        name = str(name)
    name = str(name).strip()
    if name in _LEGACY_STAGE_IDX:
        return _LEGACY_STAGE_IDX[name]
    if project_stages:
        # 数字/stageN = 旧阶段数组 1-based 索引
        n = None
        if re.fullmatch(r"\d{1,3}", name):
            n = int(name)
        elif re.fullmatch(r"stage\d{1,3}", name, re.IGNORECASE):
            n = int(name[5:])
        if n is not None and 1 <= n <= len(project_stages):
            real = project_stages[n - 1].get("name")
            if real and real != name:
                return _legacy_stage_idx(real)
    if re.match(r"ep_execution\(EP\d+\)", name) or re.match(r"^EP\d{1,2}$", name):
        return 15
    if "分镜" in name and "制作" in name:
        return 13
    if "分镜" in name:
        return 9
    if "视频" in name or "合成" in name:
        return 15
    if "参考图" in name or "设定" in name:
        return 4
    return None


def _legacy_normalize_path(p, name: str) -> str | None:
    """规范化旧 manifest 路径：绝对/反斜杠/相对 → 工作区相对 posix 路径。
    返回 None 表示该路径不可迁移（非 project/ 或 temp/ 下）。

    注意：Windows 绝对路径中项目根可能含 'project' 子串（如
    'D:\\Opencode project\\New\\project\\...'），因此不能简单地
    find('project/')，必须锚定工作区根或路径分隔符。
    """
    if not p:
        return None
    p = str(p).replace("\\", "/").strip()
    if p.startswith("D:") or p.startswith("C:") or p.startswith("/") or re.match(r"^[A-Za-z]:", p):
        # 尝试锚定工作区根
        root = str(_root()).replace("\\", "/")
        idx = p.find(root)
        if idx >= 0:
            p = p[idx + len(root):].lstrip("/")
        else:
            # 未含工作区根：找第一个 'project/' 或 'temp/'（须位于段首，避免命中 'Opencode project/'）
            best = None
            for m in re.finditer(r"(?:^|/)(project|temp)/", p):
                seg = m.group(1)
                if seg == "project" or seg == "temp":
                    best = m.start() + 1  # +1 跳过前导 '/'
                    break
            if best is None:
                return None
            p = p[best:]
    if p.startswith(".meta/") or p.startswith("canvas:"):
        return None
    if p.startswith("project/") or p.startswith("temp/"):
        return p
    return None


@_public
def import_legacy(legacy_dir, name_override=None, keep_id=True, scan_dir=None, scan_exclude=None, dbp=None):
    """将旧版 .meta/projects/{id}/ 下的四件套 JSON 元数据迁移为新库记录。

    参数：
    - legacy_dir：旧项目元数据目录（含 project.json/stages.json/manifest.json/events.jsonl/project_config.json）
    - name_override：新项目名；缺省取旧 project.json 的 name
    - keep_id：True 时保留旧 UUID 作为项目 id（唯一约束检查，冲突则自动生成新 UUID）
    - scan_dir：真实产物目录（相对 project/ 的路径，如 '星光耀' 或 '吉泰安防/系列二_侥幸的代价'）。
      提供时以 project/{scan_dir}/ 下真实文件为产物来源（_classify 自动分类，
      无法分类的进 pending_reviews），忽略 manifest 产物清单；缺省 None 时按 manifest 导入。
    - scan_exclude：scan_dir 下需跳过的顶层子目录名元组（如吉泰安防下的系列子项目目录）。

    迁移语义：
    - projects：id/name/type/description/created_at/updated_at 尽量保留；type 非法值映射为 other；status 一律 active
    - stages：新库固定 17 阶段链。将旧阶段按 _LEGACY_STAGE_IDX 映射到 idx，已映射且状态为
      completed/skipped 的阶段置 completed；in_progress 阶段记录为当前阶段；其余 pending。
      当前阶段取旧 current_stage 映射 idx，缺省为第一个未 completed 的 idx
    - artifacts：scan_dir 提供时扫描真实目录分类注册（未分类进 pending_reviews）；否则按 manifest
      导入（type 经映射表归一、path 规范化、状态归一、hash/size 一律重算、缺失/非法路径跳过）
    - events：逐条导入，actor 映射到新枚举，type/data/timestamp 原样保留
    - project_configs：合并 CONFIG_FIELDS 默认值 + 旧 config；reference_image_mode 由
      use_storyboard_images 推断

    返回 {project_id, name, stages, artifacts, events, skipped, warnings}。
    """
    ldir = Path(legacy_dir)
    if not ldir.is_dir():
        _fail(f"旧元数据目录不存在: {ldir}", "not_found")

    def _read(name):
        fp = ldir / name
        if not fp.is_file():
            return None
        try:
            return json.loads(fp.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None

    pj = _read("project.json") or {}
    st_json = _read("stages.json") or {}
    mf = _read("manifest.json") or {}
    cfg = _read("project_config.json") or {}
    events = []
    evp = ldir / "events.jsonl"
    if evp.is_file():
        for line in evp.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue

    name = (name_override or pj.get("name") or "").strip()
    if not name:
        _fail(f"无法确定项目名（缺 project.json 且未传 name_override）: {ldir}", "invalid")
    ptype = pj.get("type") or "other"
    if ptype not in templates.PROJECT_TYPES:
        ptype = "other"
    desc = (pj.get("description") or "")[:500]
    created_at = pj.get("created_at") or _now()
    updated_at = pj.get("updated_at") or created_at

    # 阶段状态重建
    old_stages = st_json.get("stages", [])
    new_current_idx = None
    completed_idx = set()
    for s in old_stages:
        nm = s.get("name")
        idx = _legacy_stage_idx(nm, old_stages)
        if idx is None:
            continue
        status = s.get("status")
        if status in ("completed", "skipped"):
            completed_idx.add(idx)
        elif status == "in_progress":
            new_current_idx = idx
    old_current = pj.get("current_stage") or st_json.get("current") or st_json.get("current_stage")
    if old_current:
        ci = _legacy_stage_idx(str(old_current), old_stages)
        if ci is not None:
            new_current_idx = ci
    # 若 new_current_idx 对应的旧阶段本身已完成（全完成项目 cur=delivery/completed），
    # 推进到其后第一个未完成阶段；全部完成则停留在 delivery（保持 completed）
    if new_current_idx is not None and new_current_idx in completed_idx:
        nxt = next((i for i in range(new_current_idx + 1, len(templates.STAGES)) if i not in completed_idx), None)
        new_current_idx = nxt
    if new_current_idx is None:
        for i in range(len(templates.STAGES)):
            if i not in completed_idx:
                new_current_idx = i
                break
        else:
            new_current_idx = len(templates.STAGES) - 1
    # 当前阶段之前的必须 completed
    for i in range(new_current_idx):
        completed_idx.add(i)
    all_done = all(i in completed_idx for i in range(len(templates.STAGES)))

    with db.connect(dbp) as conn:
        dup = conn.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        if dup is not None:
            _fail(f"项目名已存在（含已删除项目）: {name}", "conflict")
        if keep_id and (pj.get("id") or pj.get("uuid")):
            pid = str(pj.get("id") or pj.get("uuid"))
            has = conn.execute("SELECT 1 FROM projects WHERE id = ?", (pid,)).fetchone()
            if has:
                pid = str(uuid.uuid4())
        elif keep_id and st_json.get("project_id"):
            pid = str(st_json["project_id"])
            has = conn.execute("SELECT 1 FROM projects WHERE id = ?", (pid,)).fetchone()
            if has:
                pid = str(uuid.uuid4())
        else:
            pid = str(uuid.uuid4())

        with conn:
            conn.execute(
                "INSERT INTO projects (id, name, type, status, current_stage, created_at, updated_at, description)"
                " VALUES (?,?,?, 'active', ?,?,?,?)",
                (pid, name, ptype, templates.STAGES[new_current_idx]["name"], created_at, updated_at, desc),
            )
            for i, st in enumerate(templates.STAGES):
                status = "pending"
                started_at, completed_at = None, None
                if i == new_current_idx and not all_done:
                    status = "in_progress"
                    started_at = updated_at
                elif i in completed_idx:
                    status = "completed"
                    completed_at = updated_at
                conn.execute(
                    "INSERT INTO stages (project_id, idx, name, label, status, started_at, completed_at)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (pid, i, st["name"], st["label"], status, started_at, completed_at),
                )
            merged = dict(CONFIG_FIELDS)
            if isinstance(cfg, dict):
                merged.update(cfg)
            if "use_storyboard_images" in merged and merged["use_storyboard_images"] is not None:
                merged["reference_image_mode"] = "storyboard_images" if merged["use_storyboard_images"] else "visual_anchor"
            conn.execute(
                "INSERT INTO project_configs (project_id, config) VALUES (?,?)",
                (pid, json.dumps(merged, ensure_ascii=False)),
            )

            # artifacts
            art_count = 0
            skipped_arts = []
            seen_final_paths = set()
            if scan_dir:
                scan_root = _root() / "project" / scan_dir
                if not scan_root.is_dir():
                    _fail(f"真实产物目录不存在: {scan_root}", "not_found")
                exclude = set(scan_exclude or ())
                # 类型 → 阶段映射（真实产物按类型归属阶段）
                TYPE_TO_STAGE = {
                    "raw_script": 0,
                    "setting": 2, "character_design": 2, "scene_design": 2, "prop_design": 2,
                    "script": 9, "storyboard": 9, "poster": 13,
                    "character_ref": 4, "scene_ref": 8, "prop_ref": 6,
                    "reference": 1, "audio_reference": 2,
                    "video": 15, "video_manifest": 15,
                }
                internal_dirs = (".pipeline", ".libtv", "temp", "node_modules")
                pending_now = _now()
                for dirpath, dirnames, filenames in os.walk(scan_root):
                    dirnames[:] = [
                        d for d in dirnames
                        if not d.startswith(".") and d not in internal_dirs and d not in exclude
                    ]
                    for fn in filenames:
                        if fn.startswith("."):
                            continue
                        fpath = Path(dirpath) / fn
                        rel = fpath.relative_to(scan_root)
                        if rel.parts in templates.SCAN_SKIP:
                            continue
                        ntype = _classify(rel.parts)
                        if ntype is None:
                            # 未分类进 pending_reviews（保留真实文件待审查）
                            skipped_arts.append({"name": fn, "type": None, "reason": "unclassified"})
                            try:
                                st = fpath.stat()
                                conn.execute(
                                    "INSERT INTO pending_reviews (id, project_id, path, size, mtime, created_at) VALUES (?,?,?,?,?,?)",
                                    (str(uuid.uuid4()), pid, str(fpath), st.st_size,
                                     datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(), pending_now),
                                )
                            except sqlite3.IntegrityError:
                                pass
                            continue
                        key = (pid, str(fpath))
                        if key in seen_final_paths:
                            continue
                        seen_final_paths.add(key)
                        s_idx = TYPE_TO_STAGE.get(ntype, new_current_idx)
                        a_stage = templates.STAGES[s_idx]["name"]
                        h_recalc = hashing.dir_fingerprint(fpath, hashing.dir_stats(fpath)) if fpath.is_dir() else hashing.fast_fingerprint(fpath)
                        size_recalc = fpath.stat().st_size if fpath.is_file() else sum(f.stat().st_size for f in fpath.rglob("*") if f.is_file())
                        aid = str(uuid.uuid4())
                        try:
                            conn.execute(
                                "INSERT INTO artifacts (id, project_id, type, name, path, stage, status, hash, size, tags, created_at, updated_at)"
                                " VALUES (?,?,?,?,?,?, 'final',?,?,?,?,?)",
                                (aid, pid, ntype, fpath.name, str(fpath), a_stage, h_recalc, size_recalc,
                                 "[]", _now(), _now()),
                            )
                            art_count += 1
                        except sqlite3.IntegrityError:
                            skipped_arts.append({"name": fn, "type": ntype, "reason": "dup"})
            else:
                for a in mf.get("artifacts", []):
                    atype = a.get("type")
                    ntype = _LEGACY_TYPE_MAP.get(atype)
                    if ntype is None:
                        ntype = "other"
                    if ntype not in ARTIFACT_TYPES:
                        ntype = "other"
                    norm = _legacy_normalize_path(a.get("path"), name)
                    if norm is None:
                        skipped_arts.append({"name": a.get("name"), "type": atype, "reason": "path"})
                        continue
                    fp = _root() / norm
                    if not fp.exists():
                        skipped_arts.append({"name": a.get("name"), "type": atype, "reason": "missing"})
                        continue
                    if ntype == "project_config":
                        continue
                    key = (pid, str(fp))
                    if key in seen_final_paths:
                        continue
                    seen_final_paths.add(key)
                    status = "final" if a.get("status") in ("final", "active", "created", None) else "deprecated"
                    # 产物自身的旧 stage 映射到新阶段名；失败则归入当前阶段
                    a_idx = _legacy_stage_idx(a.get("stage"), old_stages)
                    a_stage = templates.STAGES[a_idx]["name"] if a_idx is not None else templates.STAGES[new_current_idx]["name"]
                    # 指纹/大小一律重算，不信任旧 manifest 值
                    h_recalc = hashing.dir_fingerprint(fp, hashing.dir_stats(fp)) if fp.is_dir() else hashing.fast_fingerprint(fp)
                    size_recalc = (
                        sum(f.stat().st_size for f in fp.rglob("*") if f.is_file())
                        if fp.is_dir()
                        else fp.stat().st_size
                    )
                    aid = a.get("id") or str(uuid.uuid4())
                    if not isinstance(aid, str) or not aid.strip():
                        aid = str(uuid.uuid4())
                    # 旧产物 id 可能跨项目重复（如 art_001），或与现存冲突；冲突时生成新 UUID 重试
                    inserted = False
                    for _attempt in range(3):
                        try:
                            conn.execute(
                                "INSERT INTO artifacts (id, project_id, type, name, path, stage, status, hash, size, tags, created_at, updated_at)"
                                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                (aid, pid, ntype, a.get("name") or fp.name, str(fp),
                                 a_stage, status, h_recalc, size_recalc,
                                 json.dumps(a.get("tags") or [], ensure_ascii=False),
                                 a.get("created_at") or _now(), a.get("updated_at") or _now()),
                            )
                            inserted = True
                            break
                        except sqlite3.IntegrityError:
                            aid = str(uuid.uuid4())
                    if inserted:
                        art_count += 1
                    else:
                        skipped_arts.append({"name": a.get("name"), "type": atype, "reason": "dup"})

            # events（actor 映射，type/data/timestamp 保留）
            ev_count = 0
            for e in events:
                actor = _LEGACY_ACTOR_MAP.get(e.get("actor"), "project-coordinator")
                conn.execute(
                    "INSERT INTO events (timestamp, type, actor, project_id, data) VALUES (?,?,?,?,?)",
                    (e.get("timestamp") or _now(), e.get("type") or "legacy.import", actor, pid,
                     json.dumps(e.get("data") or {}, ensure_ascii=False, separators=(",", ":"))),
                )
                ev_count += 1

            _emit(conn, pid, "legacy.import", {
                "from_dir": str(ldir),
                "name": name,
                "artifacts": art_count,
                "events": ev_count,
                "skipped": len(skipped_arts),
                "artifacts_source": scan_dir or "manifest",
            })

        return {
            "project_id": pid,
            "name": name,
            "type": ptype,
            "current_stage": templates.STAGES[new_current_idx]["name"],
            "stages": len(templates.STAGES),
            "artifacts": art_count,
            "events": ev_count,
            "artifacts_source": scan_dir or "manifest",
            "skipped": skipped_arts,
            "warnings": [],
        }


@_public
def delete_project(project_id, confirm_name, dbp=None):
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id, active_only=False)
        if project["status"] == "deleted":
            _fail(f"项目已处于 deleted 状态: {project['name']}", "conflict")
        if confirm_name != project["name"]:
            _fail("confirm_name 与项目名不一致，拒绝删除", "invalid")
        pdir = _project_dir(project["name"])
        removed, errors = _rmtree_collect(pdir)
        with conn:
            conn.execute(
                "UPDATE projects SET status = 'deleted', updated_at = ? WHERE id = ?",
                (_now(), project_id),
            )
            _emit(conn, project_id, "project.deleted", {
                "name": project["name"],
                "id": project_id,
                "removed_files": removed,
                "errors": errors,
            })
        return {
            "project_id": project_id,
            "name": project["name"],
            "status": "deleted",
            "removed_files": removed,
            "errors": errors,
        }
