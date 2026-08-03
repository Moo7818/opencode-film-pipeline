# 事件审计

## 事件类型

| `type` | 触发时机 | `data` 示例 |
|--------|----------|-------------|
| `project.created` | 新项目创建后 | `{"name":"山与鱼"}` |
| `project.deleted` | 项目完全注销后 | `{"name":"山与鱼","id":"uuid","reason":"用户请求注销"}` |
| `project.archived` | 项目打包归档后 | `{"name":"山与鱼","id":"uuid","zip_path":"temp/山与鱼_uuid_20260516.zip"}` |
| `stage.transition` | 阶段推进后 | `{"from":"project_init","to":"material_sorting","reason":"项目初始化完成"}` |
| `artifact.created` | 新产物注册后 | `{"artifact_id":"art_001","type":"script","path":"..."}` |
| `artifact.updated` | 产物更新后 | `{"artifact_id":"art_001","old_status":"draft","new_status":"final"}` |
| `artifact.deprecated` | 产物废弃后 | `{"artifact_id":"art_001"}` |
| `artifact.archived` | 产物从临时路径归档到项目目录后 | `{"artifact_id":"art_002","src":"temp/batch_001/xxx.png","dst":"project/山与鱼/01/分镜/xxx.png","type":"storyboard"}` |
| `batch.submitted` | 批次任务提交时 | `{"batch_id":"batch_...","type":"storyboard","count":3}` |
| `batch.completed` | 批次任务完成时 | `{"batch_id":"batch_...","succeeded":2,"failed":1}` |
| `error` | 操作异常时 | `{"operation":"stage.transition","error":"当前阶段未完成"}` |

## 规范格式（所有事件必须遵循）

每行 JSON 的顶层字段必须按以下规范：

```json
{"timestamp":"...","type":"...","actor":"...","data":{...}}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `timestamp` | 是 | ISO 8601 格式，含时区，如 `2026-05-16T10:00:00+08:00` |
| `type` | 是 | 事件类型（见上表） |
| `actor` | 是 | 触发者：`user` / `project-coordinator` / `{skill_name}` |
| `data` | 是 | 事件详情，自由结构对象 |
| `project_id` | 否 | 关联的项目 UUID（与 `.meta/projects/{id}/` 一致） |
| `batch_id` | 否 | 关联的批次 ID（与 `.logs/_index.json` 一致），用于跨日志追踪 |

**格式约束：**
- 值中的中文使用实际 `ensure_ascii=False`（明文中文），禁止 Unicode 转义
- 必须紧凑序列化（`separators=(",", ":")`），不包含多余空白
- 每行独立有效，可使用逐行读取解析

## 写入规则

1. **每次操作必须记录**：所有对项目状态有变更的操作（创建、推进、注册、更新、废弃、归档）都必须包含对应事件
2. **追加写入（使用 CLI）**：仅追加到 `.meta/projects/{id}/events.jsonl` 末尾，不修改已有行
   ```bash
   python -c "
   import json
   event = {'timestamp':'...','type':'...','actor':'project-coordinator','data':{...}}
   with open('.meta/projects/{id}/events.jsonl', 'a', encoding='utf-8') as f:
     f.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
   "
   ```
3. **时间戳**：使用 ISO 8601 格式，含时区信息
4. **actor 标识**：`project-coordinator` 表示统筹 agent 发起的操作，`user` 表示用户发起的操作
5. **写后校验**：每次追加写入后，调用 `validate.py` 校验 `events.jsonl` 语法，确保追加行格式正确

## 文件格式

```
events.jsonl
├── 第 1 行: {"timestamp":"...","type":"project.created","actor":"user","data":{...}}
├── 第 2 行: {"timestamp":"...","type":"stage.transition","actor":"project-coordinator","data":{...}}
├── 第 3 行: {"timestamp":"...","type":"artifact.created","actor":"producer","data":{...}}
└── ...
```

## 查询场景

- 时间线回放：按时间排序可重建项目完整变更历史
- 阶段耗时：筛选 `stage.transition` 事件计算各阶段持续时间
- 错误追踪：筛选 `error` 事件定位操作失败的原因