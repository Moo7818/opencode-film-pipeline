# 日志管理规范

## 目录结构

```
项目根目录/
├── .logs/                         # 项目级日志目录
│   ├── _index.json                # 轻量索引表
│   ├── batch_20260504_142045.json # 全量文档
│   ├── batch_20260504_143530.json # 全量文档
│   └── failed_batch_*.json        # 失败任务详情
├── 中间产物/
│   ├── 角色参考图/                # 产物输出目录
│   └── 分镜图/
```

## 索引表（_index.json）

轻量级索引，只存储关键元数据，支持快速查询批次概览：

```json
{
  "version": "1.0",
  "updated_at": "2026-05-04T14:20:45",
  "total_batches": 2,
  "batches": [
    {
      "batch_id": "batch_20260504_142045",
      "type": "character_reference",
      "output_dir": "中间产物/角色参考图",
      "submitted_at": "2026-05-04T14:20:45",
      "completed_at": "2026-05-04T14:25:30",
      "total": 10,
      "succeeded": 8,
      "failed": 2,
      "model": "gpt-image-2-vip",
      "log_file": "batch_20260504_142045.json"
    }
  ]
}
```

### 索引表字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `batch_id` | 是 | 批次唯一标识 |
| `type` | 否 | 批次类型：`character_reference` / `storyboard` / `other` |
| `output_dir` | 是 | 产物输出目录 |
| `submitted_at` | 是 | 提交时间 |
| `completed_at` | 是 | 完成时间 |
| `total` | 是 | 总任务数 |
| `succeeded` | 是 | 成功数 |
| `failed` | 是 | 失败数 |
| `model` | 是 | 使用的模型 |
| `log_file` | 是 | 对应的全量文档文件名 |
| `project_id` | 否 | 关联的项目 UUID（与 `.meta/projects/{id}/` 一致），用于跨日志追溯 |

### 全量文档字段补充

全量文档（`batch_*.json`）在原有字段基础上，增加 `project_id` 字段用于跨系统关联：

```json
{
  "batch_id": "batch_20260504_142045",
  "project_id": "a1b2c3d4-...",
  ...
}
```

### 索引表特点

- **轻量级**：只存储关键元数据，不包含详细的 results
- **快速查询**：可以快速获取批次列表、成功率统计
- **Token 开销低**：LLM 可以快速读取
- **支持过滤**：可以按状态、时间等过滤

## 全量文档（batch_*.json）

每个批次一个独立的 JSON 文件，包含完整的数据：

```json
{
  "batch_id": "batch_20260504_142045",
  "submitted_at": "2026-05-04T14:20:45",
  "completed_at": "2026-05-04T14:25:30",
  "total": 10,
  "succeeded": 8,
  "failed": 2,
  "output_dir": "./generated",
  "model": "gpt-image-2-vip",
  "results": [...],
  "failed_tasks": [...]
}
```

## 查询场景

| 场景 | 方法 |
|------|------|
| 查询项目所有批次 | 读取项目级 `_index.json` |
| 查询特定类型批次 | 索引过滤 `type` 字段 |
| 查询特定批次 | 读取对应的 `batch_*.json` |
| 查询失败任务 | 索引表过滤 + 全量文档详情 |

## 索引维护

**自动更新：** 每次运行批量生成时，自动更新索引表

**自动检测：** 未传 `--project-dir` 时，脚本自动扫描 CWD 下的 `project/` 目录。若其中只有一个非隐藏子目录，自动将其作为项目根目录，`.logs` 正确落在项目目录内。

**手动重建：** 如果索引表损坏，可从全量文档重建：
```bash
python {baseDir}/script/batch_generator.py --rebuild-index -p ./project_root
```

**索引表损坏不影响全量文档，可随时重建。**