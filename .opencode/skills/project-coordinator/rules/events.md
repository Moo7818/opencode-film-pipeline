# 事件审计

## append-only 语义

events 表只增不改：每个 meta_* 写操作与业务变更在**同一事务**内追加一条事件，失败即整体回滚。rowid 正序即项目完整时间线，可重建任意时刻的状态快照。不存在"修改/删除事件"的操作。

## actor 约束

- actor 由数据库 schema 强制：`CHECK (actor IN (...))`，枚举唯一来源为 templates.py 的 `ACTORS`（user / producer / storyboard-generator / roles-ref-generator / scene-ref-generator / prop-ref-generator / art-director / video-director-libtv / project-coordinator）
- meta-server 写入的全部事件 actor 固定为 `project-coordinator`（统筹是唯一写者）

## 事件类型清单（meta-server 实际写入）

| type | 触发工具 | data 要点 |
|------|----------|-----------|
| `project.created` | meta_init_project | name / type / directories / description |
| `stage.transition` | meta_advance_stage（正常推进） | from / to / reason |
| `stage.skip` | meta_advance_stage（skip=true） | from / to / reason / skip_reason |
| `artifact.created` | meta_register_artifact / meta_archive_artifact / meta_scan_and_register | artifact_id / type / path / name / hash / size / stage |
| `artifact.archived` | meta_archive_artifact | artifact_id / src / dst / moved_from / type / hash / size |
| `artifact.scan` | meta_scan_and_register（实跑） | registered / pending / missing 计数 |
| `project.archived` | meta_export_project | name / id / zip_path / files |
| `project.deleted` | meta_delete_project | name / id / removed_files / errors |

## 查询

`meta_query`（scope=events）：按 rowid 倒序（最新在前）；filters 支持 type / actor 等值过滤；limit 控制条数（上限 1000）。可选 project_id 限定单项目。

## 审计场景

- **时间线回放**：不设 limit 逐页拉取，重建项目完整变更历史
- **阶段耗时**：筛选 stage.transition / stage.skip 事件的 from/to 与时间戳
- **注销后追溯**：项目注销不删事件行，仍可按 project_id 查询
