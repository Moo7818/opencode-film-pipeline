# 导出与审计

## 导出（meta_export_project）

- **产物**：从 SQLite 生成旧版四件套结构 + project_config.json 共 5 个文件（project.json / stages.json / manifest.json / events.jsonl / project_config.json），打包为一个 ZIP。project_config.json 仅作为导出格式存在于 ZIP 内，运行时配置存于 project_configs 表，磁盘不落盘
- **输出路径**：缺省 `{工作区根}/temp/导出/{项目名}_{YYYYMMDD_HHMMSS}.zip`；可通过 dest 指定（相对路径按工作区根解析）
- **性质**：只读数据库 + 写出 ZIP，不修改项目状态；完成后自动追加一条 `project.archived` 事件
- **用途**：交付归档、备份、传输，以及注销项目前的最后存档。导出件是快照，仅作离线查阅，**不作为元数据源回读**（唯一元数据源仍是 registry.db）

## 审计

| 场景 | 操作 |
|------|------|
| 时间线回放 | meta_query（scope=events），按时间正序重建变更历史 |
| 阶段耗时与跳过原因 | 筛选 stage.transition / stage.skip 事件 |
| 产物盘点 | meta_query（scope=artifacts），按 type / stage / status 过滤 |
| 产物缺失检测 | meta_scan_and_register（dry_run=true）的 missing 报告 |
| 待归类文件跟踪 | meta_query（scope=pending） |
| 注销后追溯 | 项目行仅置 deleted，stages / artifacts / events 均保留，仍可按 project_id 查询 |
