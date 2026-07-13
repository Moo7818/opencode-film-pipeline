# Phase 1 Spec：凭证统一

> 目标：将分散的凭证管理收拢到 MCP server 内部

## 输入上下文

读取以下文件：
- `.opencode/skills/art-director/script/config.py`（93 行）—— 现有凭证加载逻辑的参考实现
- `.opencode/credentials/media_gen_config.json`（15 行）—— 当前凭证文件，包含 GRSAI + COS + ARK 三套 key
- `.opencode/mcp-servers/grsai-server/server.py`（Phase 0 产出）—— MCP server 骨架

## 任务

### 1. 创建 config.py

创建 `.opencode/mcp-servers/grsai-server/config.py`，从 `art-director/script/config.py` 提取凭证加载逻辑，简化 fallback 链：

```python
#!/usr/bin/env python3
"""凭证加载模块

加载优先级：环境变量 > 同目录 credentials.json
"""

import json
import os
import sys
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "credentials.json"

# 环境变量 key 名
CFG_API_KEY = "GRSAI_API_KEY"
CFG_HOST = "GRSAI_API_HOST"
CFG_MODEL = "GRSAI_MODEL"
CFG_OSS_ID = "GRSAI_OSS_ID"
CFG_OSS_PATH = "GRSAI_OSS_PATH"
CFG_COS_ID = "TENCENT_COS_SECRET_ID"
CFG_COS_KEY = "TENCENT_COS_SECRET_KEY"
CFG_COS_BUCKET = "TENCENT_COS_BUCKET"
CFG_COS_REGION = "TENCENT_COS_REGION"

DEFAULT_HOST = "https://grsai.dakka.com.cn"
DEFAULT_MODEL = "gpt-image-2"

_config_cache = None


def load_skill_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
            return _config_cache
        except Exception:
            pass
    _config_cache = {}
    return _config_cache


def _cfg(key):
    val = os.environ.get(key, "")
    if val:
        return val
    return load_skill_config().get(key, "")


def get_api_key():
    key = _cfg(CFG_API_KEY)
    if not key:
        print(f"缺少 {CFG_API_KEY}，请在 {CONFIG_FILE} 或环境变量中配置", file=sys.stderr)
        sys.exit(1)
    return key


def get_host():
    return _cfg(CFG_HOST) or DEFAULT_HOST


def get_model():
    return _cfg(CFG_MODEL) or DEFAULT_MODEL


def load_cos_config():
    sid = _cfg(CFG_COS_ID)
    skey = _cfg(CFG_COS_KEY)
    bucket = _cfg(CFG_COS_BUCKET)
    region = _cfg(CFG_COS_REGION)
    if sid and skey and bucket and region:
        return {
            "secret_id": sid,
            "secret_key": skey,
            "bucket": bucket,
            "region": region,
        }
    return None
```

### 2. 创建 credentials.json

复制 `.opencode/credentials/media_gen_config.json` 的内容到 `.opencode/mcp-servers/grsai-server/credentials.json`，保留以下字段，移除 ARK 相关字段：

保留：
- `GRSAI_API_KEY`
- `GRSAI_API_HOST`
- `GRSAI_MODEL`
- `GRSAI_OSS_ID`
- `GRSAI_OSS_PATH`
- `TENCENT_COS_SECRET_ID`
- `TENCENT_COS_SECRET_KEY`
- `TENCENT_COS_BUCKET`
- `TENCENT_COS_REGION`

移除：
- `ARK_API_KEY`（未使用）
- `ARK_BASE_URL`（未使用）
- `TENCENT_COS_SIGNED_URL`（未使用）
- `TENCENT_COS_EXPIRE_SECONDS`（未使用）

### 3. 实现 grsai_health_check tool

修改 `.opencode/mcp-servers/grsai-server/server.py`，在 `call_tool` 中实现 health_check：

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "grsai_health_check":
        from config import _cfg, CFG_API_KEY, CFG_HOST, CFG_COS_ID, CFG_COS_KEY, CFG_COS_BUCKET, CFG_COS_REGION, DEFAULT_HOST

        api_key = _cfg(CFG_API_KEY)
        host = _cfg(CFG_HOST) or DEFAULT_HOST
        cos_configured = all([
            _cfg(CFG_COS_ID),
            _cfg(CFG_COS_KEY),
            _cfg(CFG_COS_BUCKET),
            _cfg(CFG_COS_REGION),
        ])

        result = {
            "api_key_valid": bool(api_key),
            "host": host,
            "cos_configured": cos_configured,
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
```

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/mcp-servers/grsai-server/config.py` | 新建 |
| `.opencode/mcp-servers/grsai-server/credentials.json` | 新建（从 media_gen_config.json 迁移） |
| `.opencode/mcp-servers/grsai-server/server.py` | 修改（添加 health_check 逻辑） |

## 验收

```bash
# 1. config.py 语法正确
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/config.py').read()); print('config syntax OK')"

# 2. credentials.json 包含必要字段
python -c "
import json
c = json.load(open('.opencode/mcp-servers/grsai-server/credentials.json'))
for k in ['GRSAI_API_KEY', 'GRSAI_API_HOST', 'GRSAI_MODEL']:
    assert k in c and c[k], f'Missing or empty: {k}'
print('credentials OK')
"

# 3. server.py 包含 health_check
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
assert 'grsai_health_check' in code, 'health_check not found'
print('tool registered OK')
"

# 4. config 模块可导入
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host, load_cos_config
print('config import OK')
"
```
