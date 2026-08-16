# 项目统筹管理规范（registry.db）

项目统筹 agent（project-coordinator）的操作手册。定义 SQLite 元数据库的表结构、状态语义与工作流。所有操作通过 meta_* MCP 工具完成。

---

## 1. 体系结构

- **唯一元数据源**：`.meta/registry.db`（SQLite，WAL 模式 + foreign_keys）。连接工厂与建表 DDL 的权威源是 `.opencode/mcp-servers/meta-server/src/meta_server/db.py`
- **唯一写者**：coordinator（经 meta-server 写入）。禁止任何 agent 直接打开或修改该数据库
- **旧版 JSON 已废弃**：每项目四件套（project.json / stages.json / manifest.json / events.jsonl）不再是运行时数据源，仅作为 `meta_export_project` 的导出格式保留。旧 JSON 数据保持原样，不做迁移
- **产物目录**：`project/{项目名}/` 为实际产物区，骨架由 `meta_init_project` 自动创建

## 2. 表结构

| 表 | 作用 | 关键列 |
|----|------|--------|
| `projects` | 项目主表 | id（UUID 主键）、name（唯一，含已删除项目）、type、status、current_stage、created_at、updated_at、description |
| `stages` | 17 阶段状态机 | project_id、idx（顺序，唯一约束）、name、label、status、started_at、completed_at；UNIQUE(project_id, name) 与 UNIQUE(project_id, idx) |
| `artifacts` | 产物清单 | id（UUID）、project_id、type（枚举 CHECK）、name、path、stage、status、hash（前缀 CHECK）、size、tags（JSON 文本）、created_at、updated_at |
| `events` | 事件溯源 | rowid 自增主键、timestamp、type、actor（ACTORS 枚举 CHECK）、project_id、data（紧凑 JSON 文本） |
| `project_configs` | 项目运行时配置 | project_id（主键）、config（JSON 文本，字段与默认值权威源为 `.opencode/schemas/project-config.json` 与 templates.py 的 CONFIG_FIELDS） |
| `pending_reviews` | 待人工归类文件 | id、project_id、path、size、mtime、created_at |

**部分唯一索引** `idx_artifacts_final ON artifacts (project_id, path) WHERE status = 'final'`：同项目同路径同时只允许一条 final 记录，DB 层强制版本唯一。

## 3. 状态语义

| 状态域 | 取值 | 语义 |
|--------|------|------|
| projects.status | `active` / `deleted` | 注销是软删除：目录递归删除，DB 行保留审计，name 永久占用（重名返回 conflict） |
| stages.status | `pending` / `in_progress` / `completed` | 单向流转，completed 不可逆；current_stage 与 stages 表同步 |
| artifacts.status | `pending_review` / `final` / `deprecated` | 生命周期见 [manifest.md](manifest.md) |

**事务语义**：每个 meta_* 写操作是一个事务，业务变更与对应事件同事务写入；校验失败时不修改任何状态。

## 4. 项目目录结构（人读说明）

骨架目录与占位文件的权威源是 templates.py 的 `PROJECT_DIRS` 与 `PROJECT_PLACEHOLDER_FILES`，由 `meta_init_project` 一次性创建：

```
project/{项目名}/
├── 原始剧本.md                  # raw_script
├── 前期采样/人物|场景|风格|道具/   # reference
├── 全局依赖/
│   ├── 全局设定.md               # setting（producer 在 supervisor_extraction 阶段填充）
│   ├── 角色设定/具体设定|角色参考图/
│   ├── 场景设定/具体设定|场景参考图/
│   ├── 道具设定/具体设定|道具参考图/
│   └── 音色参考/
└── {剧集号}/剧本.md|分镜|海报设计|视频/
```

temp/ 存放导出 ZIP（`temp/导出/`）与各 agent 的临时产物，**只增不删**。

## 5. 工作流概览

| 环节 | 工具 |
|------|------|
| 创建项目（骨架 + 状态机 + 配置 + 首事件） | meta_init_project |
| 阶段推进（expected_types 校验 / skip） | meta_advance_stage |
| 产物注册（不移动文件） | meta_register_artifact |
| 产物归档（移动 + 注册） | meta_archive_artifact |
| 素材归类扫描（批量注册 + pending + missing） | meta_scan_and_register |
| 查询（projects/stages/artifacts/events/pending） | meta_query |
| 打包导出（旧版四件套 ZIP） | meta_export_project |
| 注销（软删 + 审计保留） | meta_delete_project |

具体调用时机、前置条件与异常处置见 [SKILL.md](../SKILL.md)。
