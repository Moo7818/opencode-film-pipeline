"""业务逻辑层。纯函数式，显式传 db 路径；每个操作一个事务，结束时写事件。

硬约束：禁止读取任何产物文件的内容（只允许 stat/rename/move/copy 与本模块自身的 JSON 元数据写盘）；
SHA-256 只按二进制流计算，不做内容解析。
"""

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
from .templates import ARTIFACT_TYPES, CONFIG_FIELDS, STAGES, TYPE_TO_DIR

ACTOR = "project-coordinator"

_EPISODE_RE = re.compile(r"^\d{1,3}$")

_QUERY_ALLOWED = {
    "projects": {"type", "status"},
    "stages": {"status"},
    "artifacts": {"type", "stage", "status", "name"},
    "events": {"type", "actor"},
    "pending": set(),
}


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
    if parts[0] == "全局依赖":
        if len(parts) == 3 and parts[1] == "音色参考":
            return "audio_reference"
        if len(parts) >= 4 and (parts[1], parts[2]) in _GLOBAL_SUBTYPE_MAP:
            return _GLOBAL_SUBTYPE_MAP[(parts[1], parts[2])]
        return None
    if len(parts) >= 2 and _EPISODE_RE.match(parts[0]):
        if len(parts) == 2 and parts[1] == "剧本.md":
            return "script"
        if parts[1] == "分镜":
            return "storyboard"
        if parts[1] == "海报设计":
            return "poster"
        if parts[1] == "视频":
            return "video_manifest" if parts[-1] == "_manifest.json" else "video"
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
    p = _resolve(path)
    with db.connect(dbp) as conn:
        project = _get_project(conn, project_id)
        with conn:
            return _register_artifact(conn, project, type, p, stage, name, tags)


@_public
def archive_artifact(project_id, src, type, stage=None, name=None, tags=None, dbp=None):
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
def query(scope, project_id=None, filters=None, limit=50, dbp=None):
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
