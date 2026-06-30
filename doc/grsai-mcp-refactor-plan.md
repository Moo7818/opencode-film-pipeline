# GRSAI MCP Server 通用化重构计划

> 版本：v1.0 | 日期：2026-06-30 | 状态：计划中

---

## 一、重构目标

将 GRSAI MCP Server 从「本地 stdio 嵌入式」形态重构为「通用型 MCP Server」，支持：

1. **双传输模式** — stdio（向后兼容）+ Streamable HTTP（独立部署）
2. **符合 MCP 最佳实践** — Tool Annotations、外部化配置、结构化错误处理
3. **异步化** — `urllib` → `httpx.AsyncClient`，避免阻塞
4. **可观测性** — 增强健康检查、结构化日志
5. **可部署性** — CLI 参数化、Docker 就绪

---

## 二、阶段计划

```
Phase 1 ── Tool Annotations + CLI 参数化
    │          测试：语法检查 + 可导入性
    ▼
Phase 2 ── 配置外部化 + 配置验证
    │          测试：配置加载 + 缺失报错
    ▼
Phase 3 ── 核心调用异步化 (httpx)
    │          测试：单元测试 + 异步导入
    ▼
Phase 4 ── 增强健康检查 + 错误处理
    │          测试：健康检查 + 错误场景
    ▼
Phase 5 ── 端到端集成测试
```

**铁律**：每个 Phase 的测试必须全部通过，才能进入下一 Phase。

---

## 三、详细 Phase 设计

### Phase 1：Tool Annotations + CLI 参数化

**影响文件**：`server.py`

**改动内容**：

1. 为 5 个工具添加 MCP Tool Annotations：
   - `grsai_health_check`：readOnlyHint=true, idempotentHint=true
   - `grsai_submit_image`：readOnlyHint=false, openWorldHint=true
   - `grsai_poll_result`：readOnlyHint=true, idempotentHint=true
   - `grsai_batch_generate`：readOnlyHint=false, openWorldHint=true
   - `grsai_upload_cos`：readOnlyHint=false, destructiveHint=false, openWorldHint=true

2. 添加 CLI 参数支持：
   - `--transport`：`stdio`（默认）| `streamable_http`
   - `--port`：int，默认 8000
   - `--host`：str，默认 `127.0.0.1`
   - 保留 stdio 为默认值，确保向后兼容

3. 更新 `__main__` 块使用 argparse

**验收测试**：
```bash
# 语法检查
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/server.py').read()); print('syntax ok')"

# 导入检查
python -c "import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server'); from server import mcp; print(f'ok: {len(mcp._tools)} tools')"

# CLI 参数检查
python .opencode/mcp-servers/grsai-server/server.py --help 2>&1 | grep -q 'transport' && echo 'cli ok'
```

---

### Phase 2：配置外部化

**影响文件**：`config.py`

**改动内容**：

1. `CONFIG_FILE` 路径改为可通过环境变量 `GRSAI_CONFIG_PATH` 覆盖
2. 启动时验证所有必要配置存在
3. 增加 `validate_config()` 函数，返回缺失字段列表
4. 支持 `--config` CLI 参数（通过 `GRSAI_CONFIG_PATH` 透传）

**验收测试**：
```bash
# 配置加载测试
python -c "import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server'); from config import validate_config; result = validate_config(); print(f'config valid: {result}')"

# 环境变量覆盖测试
GRSAI_API_HOST=https://test.example.com python -c "import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server'); from config import get_host; print(get_host())"

# 缺失配置报错
GRSAI_API_KEY='' python -c "import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server'); from config import get_api_key; print('should have raised')" 2>&1 | grep -q '缺少' && echo 'error ok'
```

---

### Phase 3：核心调用异步化

**影响文件**：`grsai_client.py`、`cos_client.py`、`server.py`

**改动内容**：

1. `grsai_client.py`：
   - `_api_request` → 使用 `httpx.AsyncClient` 替代 `urllib`
   - `submit_image` → 异步版本 `async_submit_image`
   - `poll_image` → 异步版本 `async_poll_image`（`time.sleep` → `asyncio.sleep`）
   - 保留同步版本（向后兼容 `batch_generate`）
   - `generate_image` → 异步版本 `async_generate_image`

2. `cos_client.py`：
   - `upload_to_cos` → 异步版本 `async_upload_to_cos`
   - 保留同步版本

3. `server.py`：
   - 同步工具调用异步函数通过 `asyncio.run()` 包装
   - `grsai_batch_generate` 内部使用 `asyncio` 替代 `ThreadPoolExecutor`

4. `requirements.txt` 添加 `httpx`

**验收测试**：
```bash
# httpx 可导入
python -c "import httpx; print('httpx ok')"

# 异步函数语法检查
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/grsai_client.py').read()); print('grsai_client syntax ok')"

# 基本异步调用测试
python -c "
import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server')
import asyncio
from grsai_client import async_poll_image
async def test(): 
    result = await async_poll_image('test_id', poll_delay=0, poll_interval=1, max_poll_rounds=1)
    print(f'async poll works: {result[\"status\"]}')
asyncio.run(test())
"

# 同步接口仍然可用
python -c "import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server'); from grsai_client import submit_image, poll_image; print('sync api ok')"
```

---

### Phase 4：增强健康检查 + 错误处理

**影响文件**：`server.py`、`config.py`

**改动内容**：

1. `grsai_health_check` 增强分层检查：
   - Level 1: 配置完整性
   - Level 2: GRSAI API 连通性（实际 ping）
   - Level 3: COS 配置检查
   - Level 4: 已注册工具数量

2. 统一错误响应格式：`{"error": "...", "code": "...", "details": {...}}`

3. 每个工具返回结构化错误信息，便于 LLM 理解和修复

**验收测试**：
```bash
# 健康检查增强
python -c "
import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server')
from server import grsai_health_check
result = grsai_health_check()
assert 'api_key_valid' in result
assert 'host' in result
assert 'cos_configured' in result
assert 'api_reachable' in result or 'warnings' in result
print('health check enhanced ok')
"

# 错误格式统一
python -c "
import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server')
result = grsai_upload_cos('/nonexistent')
assert 'error' in result
print('error format ok')
"
```

---

### Phase 5：端到端集成测试

**测试范围**：
1. 服务启动测试（stdio 模式）
2. 5 个工具全部注册
3. 健康检查返回预期字段
4. 配置缺失时优雅报错
5. CLI 参数可正确切换 transport

**验收测试**：
```bash
# 1. 服务启动 + 工具注册
python -c "
import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server')
from server import mcp
tool_names = sorted(tool.name for tool in mcp._tools)
expected = ['grsai_batch_generate','grsai_health_check','grsai_poll_result','grsai_submit_image','grsai_upload_cos']
assert tool_names == expected, f'Expected {expected}, got {tool_names}'
print(f'5 tools registered ok: {tool_names}')
"

# 2. CLI 参数切换
python .opencode/mcp-servers/grsai-server/server.py --transport streamable_http --port 9999 &
PID=$!
sleep 2
curl -s http://127.0.0.1:9999/healthz 2>/dev/null && echo 'http mode ok' || echo 'http healthz not found (expected if not implemented)'
kill $PID 2>/dev/null

# 3. stdio 模式向后兼容（通过 opencode config）
python -c "
import sys; sys.path.insert(0,'.opencode/mcp-servers/grsai-server')
from server import mcp
print('stdio mode server ready')
"
```

---

## 四、文件清单

| 文件 | Phase | 改动类型 |
|------|-------|----------|
| `.opencode/mcp-servers/grsai-server/server.py` | 1, 3, 4 | 修改 |
| `.opencode/mcp-servers/grsai-server/config.py` | 2, 4 | 修改 |
| `.opencode/mcp-servers/grsai-server/grsai_client.py` | 3 | 修改 |
| `.opencode/mcp-servers/grsai-server/cos_client.py` | 3 | 修改 |
| `.opencode/mcp-servers/grsai-server/requirements.txt` | 3 | 修改 |
| `opencode.json` | 1 | 不变（向后兼容） |

---

## 五、回滚策略

每个 Phase 提交后，如果后续 Phase 出现问题：
- `git log --oneline -10` 查看最近提交
- `git revert <commit>` 单个 Phase 回滚
- 不影响其他 Phase 的改动
