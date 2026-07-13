# Phase 0 Spec：MCP Server 骨架

> 目标：创建 MCP server 骨架，确保 opencode 能发现并连接

## 输入上下文

读取以下文件了解当前状态：
- `opencode.json`（当前无 mcpServers 节）
- `.opencode/skills/art-director/SKILL.md`（了解 art-director 的脚本调用模式，供后续改造参考）

## 任务

### 1. 创建目录结构

```
.opencode/mcp-servers/grsai-server/
```

### 2. 安装依赖

在项目 venv 中安装 MCP Python SDK：

```bash
uv add mcp
```

### 3. 编写 server.py

创建 `.opencode/mcp-servers/grsai-server/server.py`，内容如下：

```python
#!/usr/bin/env python3
"""GRSAI 统一 MCP Server

提供以下工具：
- grsai_health_check: 检查 API 连通性和凭证有效性
- grsai_call_llm: 调用 GRSAI LLM API（Phase 2 实现）
- grsai_generate_image: 调用 GRSAI 图像生成 API（Phase 3 实现）
- grsai_batch_generate: 批量图像生成（Phase 3 实现）
- grsai_upload_cos: 腾讯云 COS 上传（Phase 3 实现）
"""

import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


server = Server("grsai")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="grsai_health_check",
            description="检查 GRSAI API 连通性和凭证有效性",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "grsai_health_check":
        result = {"status": "ok"}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

### 4. 编写 requirements.txt

创建 `.opencode/mcp-servers/grsai-server/requirements.txt`：

```
mcp
```

### 5. 修改 opencode.json

在 `opencode.json` 顶层添加 `mcpServers` 节。读取当前文件，在 JSON 顶层追加：

```json
{
  "mcpServers": {
    "grsai": {
      "command": "python",
      "args": [".opencode/mcp-servers/grsai-server/server.py"]
    }
  }
}
```

注意：不覆盖 opencode.json 的其他内容，只追加 mcpServers 节。

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/mcp-servers/grsai-server/server.py` | 新建 |
| `.opencode/mcp-servers/grsai-server/requirements.txt` | 新建 |
| `opencode.json` | 修改（追加 mcpServers 节） |

## 验收

```bash
# 1. server.py 语法正确
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/server.py').read()); print('syntax OK')"

# 2. opencode.json 包含 mcpServers
python -c "
import json
d = json.load(open('opencode.json'))
assert 'mcpServers' in d, 'mcpServers not found'
assert 'grsai' in d['mcpServers'], 'grsai not found in mcpServers'
print('config OK')
"

# 3. 依赖已安装
python -c "import mcp; print('mcp installed OK')"
```
