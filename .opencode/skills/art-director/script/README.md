# script/ 模块说明

## 模块结构

```
script/
├── batch_generator.py   # 主入口：CLI 解析、任务调度、下载管理
├── config.py            # 配置加载：环境变量 > 配置文件
├── cos_uploader.py      # 腾讯云 COS 上传（HMAC-SHA256 签名）
├── file_cache.py        # 文件映射缓存（SHA256 去重）
├── log_manager.py       # 日志索引与全量文档管理
├── api_client.py        # GRSAI API 调用封装
└── README.md            # 本文件
```

## 依赖关系

```
config.py  (配置加载，无依赖)
    ↑
cos_uploader.py  (COS 上传，无依赖)
    ↑
file_cache.py  (文件缓存，依赖 cos_uploader)
    ↑
log_manager.py  (日志管理，无依赖)
    ↑
api_client.py  (API 调用，依赖 config + file_cache + log_manager)
    ↑
batch_generator.py  (主入口，依赖以上所有模块)
```

## 运行方式

从技能根目录运行（`{baseDir}` 指技能目录的绝对路径）：

```bash
python {baseDir}/script/batch_generator.py --tasks ./tasks.json -o ./output
```

或直接进入 `script/` 目录运行：

```bash
cd {baseDir}/script
python batch_generator.py --tasks ./tasks.json -o ./output
```

## 各模块职责

### config.py
- 管理所有配置常量（API 密钥、主机地址、模型名称等）
- 凭证加载优先级：环境变量 > `~/.trae-cn/media_gen_config.json`
- 导出函数：`get_api_key()`, `get_host()`, `get_model()`, `load_cos_config()`, `_cfg()`

### cos_uploader.py
- 腾讯云 COS 对象存储上传
- 使用 TC3-HMAC-SHA256 签名认证
- 自动 URL 编码中文文件名
- 导出函数：`upload_to_cos()`

### file_cache.py
- 本地文件与 COS URL 的映射缓存
- SHA256 哈希去重，相同文件只上传一次
- 自动检测文件移动并重新上传
- 导出函数：`process_urls()`, `load_file_map()`, `query_file_map()`, `update_file_map()`

### log_manager.py
- 双层日志结构：索引表（`_index.json`）+ 全量文档（`batch_*.json`）
- 支持自动更新和手动重建索引
- 导出函数：`update_index()`, `rebuild_index()`, `resolve_logs_dir()`

### api_client.py
- 封装 GRSAI API 调用（生成 + 结果查询）
- 自动根据模型前缀选择参数格式（gpt-image vs nano-banana）
- aspectRatio 像素映射表
- 导出函数：`draw_gpt_image()`, `draw_result()`, 以及 `extract_*()` 系列

### batch_generator.py
- CLI 参数解析（argparse）
- 任务提交、轮询、下载的完整调度
- 日志写入和索引更新
- 导出函数：`main()`, `run_batch_generation()`, `load_tasks_from_json()`

## 新增模块注意事项

1. **导入方式**：所有模块使用绝对导入（`from config import ...`），因为脚本从 `script/` 目录直接运行
2. **循环依赖**：当前无循环依赖。新增模块时注意依赖方向保持单向
3. **配置常量**：新增配置项时在 `config.py` 中定义常量名，统一管理
4. **API 接口**：新增 API 接口时在 `api_client.py` 中添加，保持与现有风格一致