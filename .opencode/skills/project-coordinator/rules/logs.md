# 日志聚合

## 日志来源

各技能在运行任务时，会将批次日志写入 `project/{项目名}/.logs/` 目录。统筹 agent 不直接产生日志，但需要监控和聚合这些日志。

## 监控方式

1. **被动引用**：当用户询问任务状态时，读取 `_index.json` 获取批次概览
2. **主动巡检**：在阶段推进前，检查当前阶段的所有批次是否已完成
3. **失败告警**：检查 `failed_batch_*.json` 是否存在失败任务

## 关联方式

`manifest.json` 中的产物与 `.logs/` 中的批次通过以下方式关联：

- `manifest.artifacts[].path` 对应批次日志中 `results[].output_path`
- `events.jsonl` 中的 `batch.submitted` / `batch.completed` 事件记录了 `batch_id`
- 可通过 `batch_id` 在 `_index.json` 中定位全量日志
- `_index.json` 中的 `project_id` 字段关联到 `.meta/projects/{id}/`，实现日志 ↔ 元数据双向追溯
- 批次日志（`batch_*.json`）的 `project_id` 字段与 `events.jsonl` 的 `project_id` 字段一致，支持跨系统 JOIN 查询

## 查询模式

| 用户问题 | 操作 |
|----------|------|
| "生成任务完成了吗？" | 读取 `_index.json`，检查最后一批次的状态 |
| "有多少失败的？" | 遍历 `_index.json` 累加 `failed` 字段，或检查 `failed_batch_*.json` |
| "某张图是什么时候生成的？" | 在 `_index.json` 中按类型筛选，读取对应批次日志的 `timestamp` |
| "我要重试失败的任务" | 读取 `failed_batch_*.json` 获取失败的 `task_index` 和 `prompt` |
