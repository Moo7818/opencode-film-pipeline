# 产物追踪

## 产物生命周期

```
pending_review ──→ final ──→ deprecated
（扫描到的未知文件）  （注册成功）  （同路径出现新 final 时旧行自动降级）
```

- `pending_review`：`meta_scan_and_register` 扫描到但无法归类的文件，记录在 `pending_reviews` 表，等待人工用 `meta_archive_artifact` 归类后重扫
- `final`：当前有效版本。DB 部分唯一索引保证**同项目同路径同时只有一条 final**
- `deprecated`：历史版本，保留可追溯，不删除

## 哈希（三种前缀）

| 前缀 | 适用 | 生成规则 |
|------|------|----------|
| `sha256-{hex}` | 普通文件 | 全量 SHA-256 |
| `fast-{mtime_ns}-{size}` | 图片文件（png/jpg/jpeg/gif/webp/bmp/tiff/tif，枚举见 templates.py IMAGE_EXTS） | 修改时间 + 大小快速指纹 |
| `dir-fast-{文件数}-{总字节}-{最大mtime_ns}` | 目录 | 目录统计指纹 |

哈希由工具自动计算，只读二进制流与 stat，**不解析内容**；哈希仅用于文件指纹识别与变更检测，不作为内容分析输入。

## 注册与归档

- **注册**（meta_register_artifact）：只登记，不移动文件。产物已在目标位置时使用
- **归档**（meta_archive_artifact）：移动 + 注册，一个事务完成。src 必须位于工作区 `temp/` 或 `project/` 下；目标路径按 type 模板自动推导；目标已存在时拒绝覆盖（conflict）；目标目录不存在自动创建
- **批量扫描**（meta_scan_and_register）：全量扫描 `project/{name}/`，按目录前缀逆向映射分类注册；每次扫描先清空并重建该项目的 pending_reviews；数据库中 final 但磁盘缺失的产物列入 missing（只报告，不改状态）；dry_run=true 时只报告不落库

## 类型与目录映射（人读说明）

> 权威源：templates.py 的 `TYPE_TO_DIR`。占位符由工具按源路径自动推导（{character}/{scene}/{prop} 取源文件名去扩展名，{episode} 取路径中的纯数字目录，{subtype} 取源父目录名）。

| type | 目标路径模板（相对 `project/{name}/`） |
|------|----------------------------------------|
| `raw_script` | `原始剧本.md` |
| `project_config` | 仅存在于导出 ZIP 内（导出格式）；register / archive 对该 type 一律返回 invalid，运行时不落盘 |
| `script` | `{episode}/剧本.md` |
| `character_design` | `全局依赖/角色设定/具体设定/{character}.md` |
| `character_ref` | `全局依赖/角色设定/角色参考图/{character}.png` |
| `scene_design` | `全局依赖/场景设定/具体设定/{scene}.md` |
| `scene_ref` | `全局依赖/场景设定/场景参考图/{scene}.png` |
| `prop_design` | `全局依赖/道具设定/具体设定/{prop}.md` |
| `prop_ref` | `全局依赖/道具设定/道具参考图/{prop}_{出现场合}_基准.png` |
| `storyboard` | `{episode}/分镜/{filename}` |
| `poster` | `{episode}/海报设计/{filename}` |
| `setting` | `全局依赖/全局设定.md` |
| `reference` | `前期采样/{subtype}/{filename}` |
| `audio_reference` | `全局依赖/音色参考/{filename}` |
| `video` | `{episode}/视频/{filename}` |
| `video_manifest` | `{episode}/视频/_manifest.json` |
| `other` | `{path}` |

## 查询

- `meta_query`（scope=artifacts）：按 created_at 倒序；filters 支持 type / stage / status / name 等值过滤
- `meta_query`（scope=pending）：待人工归类文件清单
