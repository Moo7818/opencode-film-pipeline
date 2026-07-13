# Phase 2 Spec：LLM API 工具化

> 目标：将 call_llm.py 的 LLM 调用能力封装为 MCP tool grsai_call_llm

## 输入上下文

读取以下文件：
- `.opencode/skills/storyboard-generator/scripts/call_llm.py`（163 行）—— 完整读取，这是 LLM 调用的核心实现
- `.opencode/mcp-servers/grsai-server/config.py`（Phase 1 产出）—— 凭证加载模块
- `.opencode/mcp-servers/grsai-server/server.py`（Phase 0 产出）—— MCP server 骨架

## 任务

### 1. 创建 grsai_client.py

创建 `.opencode/mcp-servers/grsai-server/grsai_client.py`，从 `call_llm.py` 提取核心 LLM 调用逻辑：

```python
#!/usr/bin/env python3
"""GRSAI API 客户端

封装 GRSAI 图像生成和 LLM 调用的统一客户端。
Phase 2：LLM 调用
Phase 3：图像生成（后续扩展）
"""

import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from config import _cfg, get_api_key, get_host

MAX_RETRIES = 3


def call_llm(messages, model=None, temperature=0.7, max_tokens=None, timeout=300):
    """调用 GRSAI LLM API，支持 3 次指数退避重试

    从 call_llm.py call() 函数提取，保持完全一致的行为。

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        model: 模型名，默认从配置读取，fallback "gemini-3.1-pro"
        temperature: 温度，默认 0.7
        max_tokens: 最大 token 数（可选）
        timeout: 请求超时秒数，默认 300

    Returns:
        {"content": str, "finish_reason": str, "usage": dict}

    Raises:
        RuntimeError: 认证失败、上下文超长、请求错误、网络错误
    """
    api_key = get_api_key()
    host = get_host()
    model = model or _cfg("GRSAI_LLM_MODEL") or "gemini-3.1-pro"

    body = {
        "model": model,
        "stream": False,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            return {
                "content": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"),
                "usage": data.get("usage", {}),
            }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise RuntimeError(f"认证失败 (HTTP {e.code}): {err_body[:300]}")
            if e.code == 400 and ("context_length" in err_body.lower() or "token" in err_body.lower()):
                raise RuntimeError(f"上下文超长 (HTTP 400): {err_body[:300]}")
            if e.code == 400:
                raise RuntimeError(f"请求参数错误 (HTTP 400): {err_body[:300]}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"API 失败 (HTTP {e.code}, 已重试{MAX_RETRIES}次): {err_body[:300]}")
        except urllib.error.URLError as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"网络错误 (已重试{MAX_RETRIES}次): {e.reason}")
        wait = min(2 ** attempt, 60) * (0.5 + random.random())
        print(f"  ⚠ 第{attempt}次失败，{wait:.1f}s 后重试...", file=sys.stderr)
        time.sleep(wait)

    raise RuntimeError("不可达状态")
```

### 2. 在 server.py 中注册 grsai_call_llm tool

修改 `.opencode/mcp-servers/grsai-server/server.py`：

1. 在 `list_tools()` 中添加 tool 定义：

```python
Tool(
    name="grsai_call_llm",
    description="调用 GRSAI LLM API，支持 3 次指数退避重试",
    inputSchema={
        "type": "object",
        "required": ["messages"],
        "properties": {
            "messages": {
                "type": "array",
                "description": "对话消息列表",
                "items": {
                    "type": "object",
                    "required": ["role", "content"],
                    "properties": {
                        "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                        "content": {"type": "string"},
                    },
                },
            },
            "model": {
                "type": "string",
                "description": "模型名，如 gemini-3.1-pro",
                "default": "gemini-3.1-pro",
            },
            "temperature": {
                "type": "number",
                "description": "温度",
                "default": 0.7,
            },
            "max_tokens": {
                "type": "integer",
                "description": "最大 token 数（可选）",
            },
            "timeout": {
                "type": "integer",
                "description": "请求超时秒数",
                "default": 300,
            },
        },
    },
),
```

2. 在 `call_tool()` 中添加处理：

```python
elif name == "grsai_call_llm":
    from grsai_client import call_llm
    try:
        result = call_llm(
            messages=arguments["messages"],
            model=arguments.get("model"),
            temperature=arguments.get("temperature", 0.7),
            max_tokens=arguments.get("max_tokens"),
            timeout=arguments.get("timeout", 300),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except RuntimeError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
```

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/mcp-servers/grsai-server/grsai_client.py` | 新建 |
| `.opencode/mcp-servers/grsai-server/server.py` | 修改（添加 tool 定义和处理） |

## 验收

```bash
# 1. grsai_client.py 语法正确
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/grsai_client.py').read()); print('grsai_client syntax OK')"

# 2. server.py 包含 grsai_call_llm
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
assert 'grsai_call_llm' in code, 'grsai_call_llm not found'
print('tool registered OK')
"

# 3. grsai_client 可导入
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from grsai_client import call_llm
assert callable(call_llm)
print('import OK')
"

# 4. 依赖链完整
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host
from grsai_client import call_llm
print('dependency chain OK')
"
```
