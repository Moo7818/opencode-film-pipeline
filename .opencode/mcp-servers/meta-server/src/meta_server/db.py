"""SQLite 连接工厂与建表 DDL。"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .templates import ACTORS, ARTIFACT_STATUS, ARTIFACT_TYPES, PROJECT_STATUS, PROJECT_TYPES, STAGE_STATUS


def project_root() -> Path:
    env = os.environ.get("META_PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # src/meta_server/db.py -> meta-server -> mcp-servers -> .opencode -> 工作区根
    return Path(__file__).resolve().parents[5]


def default_db_path() -> Path:
    env = os.environ.get("META_DB_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return project_root() / ".meta" / "registry.db"


def _enum(values) -> str:
    return ",".join(f"'{v}'" for v in values)


DDL = (
    f"""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        type TEXT NOT NULL CHECK (type IN ({_enum(PROJECT_TYPES)})),
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ({_enum(PROJECT_STATUS)})),
        current_stage TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stages (
        project_id TEXT NOT NULL REFERENCES projects(id),
        idx INTEGER NOT NULL,
        name TEXT NOT NULL,
        label TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (%s)),
        started_at TEXT,
        completed_at TEXT,
        UNIQUE (project_id, name),
        UNIQUE (project_id, idx)
    )
    """ % _enum(STAGE_STATUS),
    f"""
    CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id),
        type TEXT NOT NULL CHECK (type IN ({_enum(ARTIFACT_TYPES)})),
        name TEXT NOT NULL,
        path TEXT NOT NULL,
        stage TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'final' CHECK (status IN ({_enum(ARTIFACT_STATUS)})),
        hash TEXT NOT NULL CHECK (hash LIKE 'sha256-%' OR hash LIKE 'fast-%' OR hash LIKE 'dir-fast-%'),
        size INTEGER NOT NULL,
        tags TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    # 部分索引：同一项目同一路径同时只允许一条 status='final'
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_final
    ON artifacts (project_id, path) WHERE status = 'final'
    """,
    f"""
    CREATE TABLE IF NOT EXISTS events (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        type TEXT NOT NULL,
        actor TEXT NOT NULL CHECK (actor IN ({_enum(ACTORS)})),
        project_id TEXT,
        data TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_configs (
        project_id TEXT PRIMARY KEY REFERENCES projects(id),
        config TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pending_reviews (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id),
        path TEXT NOT NULL,
        size INTEGER,
        mtime TEXT,
        created_at TEXT NOT NULL
    )
    """,
)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in DDL:
        conn.execute(stmt)
    conn.commit()


@contextmanager
def connect(db=None):
    path = Path(db).expanduser().resolve() if db else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()
