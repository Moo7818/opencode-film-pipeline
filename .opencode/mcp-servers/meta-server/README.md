# meta-server

动画短剧管线的项目元数据 MCP server。以 SQLite 为单一数据源，取代旧版每项目四个 JSON 文件（project.json / stages.json / manifest.json / events.jsonl）；coordinator 今后只调用本 server 的 MCP 工具，不再直接读写 `.meta/projects/{id}/` 下的 JSON。旧 JSON 数据经 `meta_import_legacy` 一次性迁移进新库后保持原样归档。

## 工具（9 个）

| 工具 | 作用 |
|------|------|
| `meta_init_project` | 创建项目：UUID + 目录骨架 + 17 阶段状态机 + 项目配置 + 首事件 |
| `meta_advance_stage` | 阶段推进一格；expected_types 前置校验；skip 需 skip_reason |
| `meta_register_artifact` | 注册产物（文件/目录），自动哈希与版本去重（旧 final 转 deprecated） |
| `meta_archive_artifact` | 从 temp/ 或 project/ 移动到规范目录并注册（归档 = 移动 + 注册） |
| `meta_scan_and_register` | 扫描项目目录批量注册；未知文件进 pending_reviews；报告 missing |
| `meta_query` | 只读查询：projects / stages / artifacts / events / pending |
| `meta_export_project` | 导出旧版四件套结构 + project_config.json 共 5 文件打包 ZIP |
| `meta_import_legacy` | 一次性迁移旧版 `.meta/projects/{id}/` 四件套 JSON 到新库（类型/阶段/actor/hash/path 归一化；产物指纹一律重算；重名返回 conflict 可用 name_override 规避）。支持 `scan_dir` 以 `project/{scan_dir}/` 真实产物为源（`_classify` 自动分类，未分类进 pending_reviews），`scan_exclude` 排除子目录 |
| `meta_delete_project` | 删除项目（confirm_name 防误删；DB 仅置 status='deleted'，保留审计） |

所有工具错误统一返回 `{"error": str, "code": str}`（code ∈ not_found / invalid / conflict / io），不抛异常。

## 安装

```bash
cd .opencode/mcp-servers/meta-server && uv sync
```

唯一第三方依赖为 `mcp`（Python >= 3.13，uv 自动管理）。

## 启动

```bash
uv run --no-sync --directory .opencode/mcp-servers/meta-server -m meta_server
```

opencode.json 中的 MCP 配置片段（如需启用）：

```json
"meta": {
  "type": "local",
  "command": ["uv", "run", "--no-sync", "--directory", ".opencode/mcp-servers/meta-server", "-m", "meta_server"],
  "enabled": true
}
```

## 测试

```bash
.opencode/mcp-servers/meta-server/.venv/bin/python temp/test_meta_server.py
```

测试沙箱位于 `temp/test_meta_run/`（META_PROJECT_ROOT 与 META_DB_PATH 均指向沙箱），脚本启动时只清理该子树，不触碰真实 `.meta/` 与其他 temp 文件；退出码非零表示有失败项。

## 环境变量

| 变量 | 说明 | 缺省 |
|------|------|------|
| `META_DB_PATH` | SQLite 数据库文件路径 | `{META_PROJECT_ROOT}/.meta/registry.db` |
| `META_PROJECT_ROOT` | 工作区根（项目目录、temp、导出的基准） | 按源码位置推导：`src/meta_server/db.py` 的 `parents[5]`，即工作区根 |

## 代码结构

- `templates.py`：阶段链/目录骨架/type 枚举与路径映射/actor 枚举/配置字段的单一来源（权威来源为 project-coordinator rules 与 schemas/project-config.json）
- `db.py`：连接工厂（WAL + foreign_keys）与建表 DDL（CHECK 约束强制枚举，artifacts 用部分唯一索引保证同项目同路径仅一条 final）
- `hashing.py`：sha256- / fast- / dir-fast- 三种指纹，只读二进制流与 stat，不解析内容
- `service.py`：全部业务逻辑，纯函数式，每个操作一个事务并写事件（actor 固定 project-coordinator）
- `server.py`：FastMCP 工具层，docstring 即接口文档
