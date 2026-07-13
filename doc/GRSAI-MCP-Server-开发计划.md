# GRSAI 统一 MCP Server 开发计划

> 版本：v2.0 | 日期：2026-06-16 | 范式：Spec Coding（子 agent 驱动开发）

---

## 〇、开发范式说明

本项目所有开发任务均通过 **子 agent spec coding** 完成。每个阶段产出一份 **spec 文件**（`.md`），由 `general` 或 `system-engineer` 类型的子 agent 读取 spec 后自主执行。主 agent（Orchestrator）负责：

1. 按顺序 spawn 子 agent，传入对应 spec 路径
2. 等待子 agent 完成，检查产出物
3. 执行 spec 中定义的验收检查（shell 命令）
4. 通过后进入下一阶段

**Spec 文件规范**：
- 每个 spec 是自包含的，子 agent 无需额外上下文即可执行
- Spec 中明确列出：输入文件路径、输出文件路径、代码模式参考、验收命令
- Spec 中的代码示例是**精确参考**，子 agent 应复用现有代码模式而非从零编写
- 验收命令必须可自动化执行（shell 命令），不依赖人工判断

---

## 一、背景与目标

### 1.1 现状

GRSAI API（`grsai.dakka.com.cn`）在管线中被两个 skill 各自独立集成：

| 集成点 | Skill | 核心脚本 | 代码行数 |
|--------|-------|---------|---------|
| 图像生成 | art-director | `api_client.py` + `cos_uploader.py` + `file_cache.py` + `batch_generator.py` | ~1100 |
| LLM 调用 | storyboard-generator | `call_llm.py` | 163 |
| 凭证加载 | 两者各自实现 | `config.py` / 内联 `_cfg()` | ~150 |

**问题**：同一 API 域两套认证、轮询、重试逻辑不一致、脚本不可复用、每次调用加载整套脚本路径 token 开销大。

### 1.2 目标

构建 GRSAI 统一 MCP Server，将 API 集成收拢为标准 MCP 服务单元。

### 1.3 目标目录结构

```
.opencode/
├── mcp-servers/
│   └── grsai-server/
│       ├── server.py              # MCP server 主入口
│       ├── grsai_client.py        # GRSAI API 客户端（图像 + LLM）
│       ├── cos_client.py          # 腾讯云 COS 上传
│       ├── config.py              # 凭证加载
│       ├── credentials.json       # 凭证（从 media_gen_config.json 迁移）
│       └── requirements.txt       # 依赖
├── scripts/
│   └── validators/
│       └── image_task_validator.py # 共享图像任务校验器（合并 3 个 ref-generator 的 validators）
└── skills/
    ├── art-director/
    │   └── SKILL.md               # 改造：MCP tool 调用模式
    └── storyboard-generator/
        └── SKILL.md               # 改造：MCP tool 调用模式
```

---

## 二、阶段规划与 Spec 清单

共 7 个阶段，每阶段对应一份 spec 文件。阶段顺序有依赖，不可跳过。

| 阶段 | Spec 文件 | 执行子 Agent | 依赖 | 预估工时 |
|------|----------|-------------|------|---------|
| 0 | `specs/phase-0-skeleton.md` | general | 无 | 0.5d |
| 1 | `specs/phase-1-credentials.md` | general | Phase 0 | 0.5d |
| 2 | `specs/phase-2-llm-tool.md` | general | Phase 1 | 1d |
| 3 | `specs/phase-3-image-tool.md` | general | Phase 1 | 1.5d |
| 4 | `specs/phase-4-validators.md` | general | Phase 3 | 0.5d |
| 5 | `specs/phase-5-skill改造.md` | system-engineer | Phase 2-4 | 1d |
| 6 | `specs/phase-6-cleanup.md` | general | Phase 5 | 0.5d |

**注意**：Phase 2（LLM）和 Phase 3（图像）可并行执行，它们都依赖 Phase 1 但彼此独立。

---

## 三、各阶段 Spec 定义

### Phase 0：MCP Server 骨架

**Spec 路径**：`doc/specs/phase-0-skeleton.md`

**目标**：创建 MCP server 骨架，确保 opencode 能发现并连接。

**输入上下文**：
- opencode.json 当前内容（读取后在 mcpServers 节追加配置）
- MCP Python SDK 用法（参考 mcp 文档）

**具体任务**：
1. 创建目录 `.opencode/mcp-servers/grsai-server/`
2. 安装依赖：在项目 venv 中 `uv add mcp`
3. 编写 `server.py`：
   - 使用 `mcp.server.Server` 创建 server 实例
   - 注册一个 `grsai_health_check` tool（返回 `{status: "ok"}`）
   - 实现 stdio transport
4. 编写 `requirements.txt`：`mcp`
5. 修改 `opencode.json`：在顶层添加 `mcpServers` 节

**代码参考**：
```python
# server.py 骨架模式
from mcp.server import Server
from mcp.server.stdio import stdio_server
import asyncio, json

server = Server("grsai")

@server.list_tools()
async def list_tools():
    return [...]  # tool 定义

@server.call_tool()
async def call_tool(name, arguments):
    if name == "grsai_health_check":
        return {"type": "text", "text": json.dumps({"status": "ok"})}

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

**opencode.json 配置追加**：
```json
{
  "mcpServers": {
    "grsai": {
      "command": "python",
      "args": [".opencode/mcp-servers/grsai-server/server.py"],
      "cwd": "{workspace}"
    }
  }
}
```

**验收命令**：
```bash
# 1. 进程存活
ps aux | grep "grsai-server/server.py" | grep -v grep

# 2. opencode.json 包含 mcpServers 节
python -c "import json; d=json.load(open('opencode.json')); assert 'mcpServers' in d and 'grsai' in d['mcpServers']"

# 3. server.py 语法检查
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/server.py').read()); print('syntax OK')"
```

---

### Phase 1：凭证统一

**Spec 路径**：`doc/specs/phase-1-credentials.md`

**目标**：将分散的凭证管理收拢到 MCP server 内部。

**输入上下文**：
- 现有凭证文件：`.opencode/credentials/media_gen_config.json`（包含 GRSAI_API_KEY、GRSAI_API_HOST、GRSAI_MODEL、GRSAI_OSS_ID、GRSAI_OSS_PATH、TENCENT_COS_*）
- 现有凭证加载代码参考：`.opencode/skills/art-director/script/config.py`（lines 33-61）

**具体任务**：
1. 创建 `.opencode/mcp-servers/grsai-server/config.py`：
   - 从 `config.py`（参考文件）提取 `load_skill_config()` 和 `_cfg()` 模式
   - 凭证来源简化为：环境变量 > 同目录 `credentials.json`（不再 fallback 到 `~/.trae-cn`）
   - 导出函数：`get_api_key()`, `get_host()`, `get_model()`, `load_cos_config()`
2. 创建 `.opencode/mcp-servers/grsai-server/credentials.json`：
   - 从 `.opencode/credentials/media_gen_config.json` 复制 GRSAI + COS 相关字段
   - 不包含 ARK 相关字段（未使用）
3. 在 `server.py` 中实现 `grsai_health_check` tool：
   - 检查 API key 是否存在且非空
   - 检查 host 是否可达（简单 HTTP HEAD）
   - 检查 COS 凭证是否完整
   - 返回 `{api_key_valid, host, cos_configured}`

**代码参考**：
```python
# config.py 核心模式（从 art-director/script/config.py 提取）
import json, os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "credentials.json"
_config_cache = None

def load_skill_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
        return _config_cache
    _config_cache = {}
    return _config_cache

def _cfg(key):
    val = os.environ.get(key, "")
    if val:
        return val
    return load_skill_config().get(key, "")
```

**验收命令**：
```bash
# 1. config.py 语法检查
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/config.py').read()); print('syntax OK')"

# 2. credentials.json 包含必要字段
python -c "
import json
c = json.load(open('.opencode/mcp-servers/grsai-server/credentials.json'))
for k in ['GRSAI_API_KEY', 'GRSAI_API_HOST', 'GRSAI_MODEL']:
    assert k in c and c[k], f'Missing or empty: {k}'
print('credentials OK')
"

# 3. health_check tool 可调用（在 server.py 中验证）
python -c "
import ast
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
assert 'grsai_health_check' in code, 'health_check tool not found'
print('tool registered OK')
"
```

---

### Phase 2：LLM API 工具化

**Spec 路径**：`doc/specs/phase-2-llm-tool.md`

**目标**：将 `call_llm.py` 的 LLM 调用能力封装为 MCP tool `grsai_call_llm`。

**输入上下文**：
- 现有实现：`.opencode/skills/storyboard-generator/scripts/call_llm.py`（163 行，完整读取）
- 凭证模块：Phase 1 产出的 `.opencode/mcp-servers/grsai-server/config.py`

**具体任务**：
1. 创建 `.opencode/mcp-servers/grsai-server/grsai_client.py`：
   - 从 `call_llm.py` 提取 `call()` 函数核心逻辑（lines 34-77）
   - 保留 3 次指数退避重试（`2^attempt * (0.5+random)` 秒）
   - 保留 401/403 直接报错、400 区分可重试/不可重试的逻辑
   - 使用 Phase 1 的 `config.py` 获取凭证（不再内联 `_cfg()`）
   - 导出：`call_llm(messages, model, temperature, max_tokens, timeout)` → `dict`
2. 在 `server.py` 中注册 `grsai_call_llm` tool：
   - 输入：messages (array), model (string, default "gemini-3.1-pro"), temperature (number, default 0.7), timeout (integer, default 300)
   - 输出：{content, finish_reason, usage}
3. 保留 `call_llm.py` 原文件不删除（Phase 6 清理）

**代码参考**：
```python
# grsai_client.py 中的 call_llm 函数（从 call_llm.py call() 提取）
import json, os, sys, time, random, urllib.error, urllib.request
from config import _cfg

MAX_RETRIES = 3

def call_llm(messages, model=None, temperature=0.7, max_tokens=None, timeout=300):
    api_key = _cfg("GRSAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GRSAI_API_KEY")
    host = _cfg("GRSAI_API_HOST") or "https://grsai.dakka.com.cn"
    model = model or _cfg("GRSAI_LLM_MODEL") or "gemini-3.1-pro"

    body = {"model": model, "stream": False, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens

    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
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
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise RuntimeError(f"认证失败 (HTTP {e.code}): {body[:300]}")
            if e.code == 400 and ("context_length" in body.lower() or "token" in body.lower()):
                raise RuntimeError(f"上下文超长 (HTTP 400): {body[:300]}")
            if e.code == 400:
                raise RuntimeError(f"请求参数错误 (HTTP 400): {body[:300]}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"API 失败 (HTTP {e.code}, 已重试{MAX_RETRIES}次): {body[:300]}")
        except urllib.error.URLError as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"网络错误 (已重试{MAX_RETRIES}次): {e.reason}")
        wait = min(2 ** attempt, 60) * (0.5 + random.random())
        print(f"  ⚠ 第{attempt}次失败，{wait:.1f}s 后重试...", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError("不可达状态")
```

**验收命令**：
```bash
# 1. grsai_client.py 语法检查
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/grsai_client.py').read()); print('syntax OK')"

# 2. server.py 包含 grsai_call_llm tool 注册
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
assert 'grsai_call_llm' in code, 'grsai_call_llm tool not found'
print('tool registered OK')
"

# 3. call_llm 函数可导入（不执行网络调用）
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from grsai_client import call_llm
assert callable(call_llm)
print('import OK')
"
```

---

### Phase 3：图像生成 API 工具化

**Spec 路径**：`doc/specs/phase-3-image-tool.md`

**目标**：将图像生成 API 的提交+轮询+COS 上传封装为 MCP tool。

**输入上下文**：
- 现有实现（完整读取）：
  - `.opencode/skills/art-director/script/api_client.py`（218 行）
  - `.opencode/skills/art-director/script/cos_uploader.py`（110 行）
  - `.opencode/skills/art-director/script/file_cache.py`（155 行）
  - `.opencode/skills/art-director/script/batch_generator.py`（632 行）
- 凭证模块：Phase 1 产出的 `.opencode/mcp-servers/grsai-server/config.py`

**具体任务**：
1. 创建 `.opencode/mcp-servers/grsai-server/cos_client.py`：
   - 从 `cos_uploader.py` 提取 `upload_to_cos()` 函数（lines 76-110）
   - 保留 HMAC-SHA256 签名逻辑（lines 15-73）
   - 导出：`upload_to_cos(local_path, secret_id, secret_key, bucket, region, timestamp)` → `str` (URL)
2. 扩展 `grsai_client.py`：
   - 从 `api_client.py` 提取：`draw_gpt_image()`（lines 125-168）、`draw_result()`（lines 171-189）、`resolve_aspect_ratio()`（lines 59-77）、`_is_nano_banana_model()`（lines 80-81）
   - 从 `file_cache.py` 提取：`process_urls()`（lines 97-155）、`compute_file_hash()`（lines 47-54）
   - 使用 Phase 1 的 `config.py` 获取 COS 凭证
   - 导出：`generate_image(prompt, model, aspect_ratio, images, ...)` → `dict`
3. 在 `server.py` 中注册 3 个 tool：
   - `grsai_generate_image`：单张生成，内部处理提交+sleep+轮询，阻塞返回结果
   - `grsai_batch_generate`：批量并发提交+轮询+下载
   - `grsai_upload_cos`：COS 上传

**代码参考**：
```python
# grsai_client.py 中的 generate_image 核心流程
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def generate_image(prompt, model, aspect_ratio=None, image_size=None,
                   reference_images=None, oss_id=None, oss_path=None,
                   poll_delay=14, poll_interval=5, max_poll_rounds=60):
    """单张图像生成，阻塞直到完成"""
    # 1. 处理参考图（本地文件 → COS URL）
    processed_urls = process_urls(reference_images, ...)

    # 2. 构建请求体
    body = {"model": model, "prompt": prompt, "replyType": "async"}
    if _is_nano_banana_model(model):
        body["aspectRatio"] = aspect_ratio or "1:1"
        if image_size:
            body["imageSize"] = image_size.upper()
    else:
        body["aspectRatio"] = resolve_aspect_ratio(aspect_ratio, image_size)
    if processed_urls:
        body["images"] = processed_urls if isinstance(processed_urls, list) else [processed_urls]

    # 3. 提交
    resp = _api_request(f"{host}/v1/api/generate", headers, body)
    result = _parse_response(resp)
    task_id = result.get("id")

    # 4. 如果已有结果（同步返回），直接返回
    image_url = _extract_image_url(result)
    if image_url:
        return {"status": "completed", "image_url": image_url, "task_id": task_id}

    # 5. 轮询
    time.sleep(poll_delay)
    for _ in range(max_poll_rounds):
        time.sleep(poll_interval)
        result = _poll_result(task_id)
        status = result.get("status")
        if status == "failed":
            return {"status": "failed", "error": _extract_failure_reason(result), "task_id": task_id}
        if status == "succeeded":
            image_url = _extract_image_url(result)
            if image_url:
                return {"status": "completed", "image_url": image_url, "task_id": task_id,
                        "oss_url": _extract_oss_url(result)}
    return {"status": "timeout", "error": f"轮询超时 {max_poll_rounds * poll_interval}s", "task_id": task_id}
```

**验收命令**：
```bash
# 1. 所有新文件语法检查
for f in .opencode/mcp-servers/grsai-server/{cos_client,grsai_client,server}.py; do
  python -c "import ast; ast.parse(open('$f').read()); print(f'$f OK')"
done

# 2. server.py 包含所有 image tool
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
for tool in ['grsai_generate_image', 'grsai_batch_generate', 'grsai_upload_cos']:
    assert tool in code, f'{tool} not found'
print('all image tools registered OK')
"

# 3. cos_client 可导入
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from cos_client import upload_to_cos
assert callable(upload_to_cos)
print('cos_client import OK')
"

# 4. grsai_client 可导入
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from grsai_client import generate_image, call_llm
assert callable(generate_image) and callable(call_llm)
print('grsai_client import OK')
"
```

---

### Phase 4：Validators 整合

**Spec 路径**：`doc/specs/phase-4-validators.md`

**目标**：合并三个 ref-generator 的重复 validators 为共享模块。

**输入上下文**：
- `.opencode/skills/roles-ref-generator/scripts/validators.py`（96 行）
- `.opencode/skills/prop-ref-generator/scripts/validators.py`（87 行）
- `.opencode/skills/scene-ref-generator/scripts/validators.py`（84 行）
- 三个文件差异：仅 `FIXED_ASPECT_RATIO` 常量和函数签名不同

**具体任务**：
1. 创建 `.opencode/scripts/validators/image_task_validator.py`：
   - 提取公共校验逻辑
   - 参数化：`validate_tasks(tasks, aspect_ratio="16:9", image_size="1K", model="gpt-image-2")`
   - 导出：`validate_tasks()` 和 `format_report()`
2. 将三个 ref-generator 的 `validators.py` 改为调用共享模块：
   ```python
   # roles-ref-generator/scripts/validators.py
   import sys, os
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'validators'))
   from image_task_validator import validate_tasks, format_report
   FIXED_ASPECT_RATIO = "16:9"
   FIXED_IMAGE_SIZE = "1K"
   FIXED_MODEL = "gpt-image-2"
   def validate_tasks_wrapper(tasks):
       return validate_tasks(tasks, aspect_ratio=FIXED_ASPECT_RATIO, image_size=FIXED_IMAGE_SIZE, model=FIXED_MODEL)
   ```
3. MCP server 的 `grsai_batch_generate` 入口增加轻量防御（prompt 非空、model 非空）

**验收命令**：
```bash
# 1. 共享 validator 语法检查
python -c "import ast; ast.parse(open('.opencode/scripts/validators/image_task_validator.py').read()); print('syntax OK')"

# 2. 各 ref-generator validators 可导入
for skill in roles-ref-generator prop-ref-generator scene-ref-generator; do
  python -c "
import sys; sys.path.insert(0, '.opencode/skills/$skill/scripts')
from validators import validate_tasks
print('$skill validators import OK')
"
done

# 3. 共享 validator 对示例数据校验通过
python -c "
import sys; sys.path.insert(0, '.opencode/scripts/validators')
from image_task_validator import validate_tasks
tasks = [{'prompt': 'test', 'imageSize': '1K', 'aspectRatio': '16:9', 'filename': 'test.png', 'images': []}]
errors = validate_tasks(tasks, aspect_ratio='16:9')
assert errors == [], f'Unexpected errors: {errors}'
print('validation OK')
"
```

---

### Phase 5：SKILL.md 全面改造

**Spec 路径**：`doc/specs/phase-5-skill改造.md`

**目标**：将 art-director 和 storyboard-generator 的 SKILL.md 从 CLI 调用切换为 MCP tool 调用。

**执行子 Agent**：`system-engineer`（调试 skill 时加载 `skill-creator` 技能，调试 MCP Server 时加载 `mcp-builder` 技能）

**输入上下文**：
- `.opencode/skills/art-director/SKILL.md`（完整读取）
- `.opencode/skills/storyboard-generator/SKILL.md`（完整读取）
- Phase 0-4 产出的 MCP server 文件（了解 tool 名称和参数）

**具体任务**：

**5a. art-director/SKILL.md**：
- 移除所有 `batch_generator.py` 路径引用
- 移除脚本参数说明（`--tasks`, `--model`, `--concurrency` 等）
- 替换为 MCP tool 调用示例：
  ```
  ## 图像生成

  通过 MCP tool `grsai_batch_generate` 执行批量生图。

  输入格式不变（仍按 .opencode/schemas/image-generation.json 生成 tasks.json），
  但调用方式从 CLI 改为 MCP tool：

  示例（Agent 调用 MCP tool）：
    tool: grsai_batch_generate
    input:
      tasks: [{prompt: "...", model: "gpt-image-2", ...}]
      output_dir: "./generated/角色参考图"
      concurrency: 10

  返回：
    {batch_id, total, succeeded, failed, results: [...]}
  ```
- 保留：提示词构建规则、参考图约定、模型差异说明
- 移除：凭证配置说明、脚本路径、CLI 参数

**5b. storyboard-generator/SKILL.md**：
- 移除 `call_llm.py` CLI 调用模式
- 替换为 MCP tool 调用示例：
  ```
  ## LLM 调用

  通过 MCP tool `grsai_call_llm` 执行 LLM 调用。

  单次调用示例：
    tool: grsai_call_llm
    input:
      messages: [{role: "system", content: "..."}, {role: "user", content: "..."}]
      model: "gemini-3.1-pro"
      temperature: 0.7

  长剧本分片模式：
    1. shard_manager.py 分片（保留，仍为 CLI 调用）
    2. 每个分片调用 grsai_call_llm tool
    3. shard_manager.py 合并结果（保留，仍为 CLI 调用）
  ```
- 保留：shard_manager.py 调用说明、validators.py 调用说明、分镜结构规范
- 移除：call_llm.py 路径、凭证说明

**验收命令**：
```bash
# 1. art-director SKILL.md 无废弃引用
grep -c "batch_generator.py" .opencode/skills/art-director/SKILL.md
# 预期：0

# 2. storyboard-generator SKILL.md 无废弃引用
grep -c "call_llm.py" .opencode/skills/storyboard-generator/SKILL.md
# 预期：0

# 3. 两个 SKILL.md 包含 MCP tool 名称
grep -c "grsai_" .opencode/skills/art-director/SKILL.md
grep -c "grsai_" .opencode/skills/storyboard-generator/SKILL.md
# 预期：各 >= 1

# 4. 其他 skill 的 SKILL.md 未受影响
grep -rl "grsai_" .opencode/skills/ | grep -v "art-director\|storyboard-generator\|grsai-server"
# 预期：无输出
```

---

### Phase 6：废弃脚本清理

**Spec 路径**：`doc/specs/phase-6-cleanup.md`

**目标**：标记废弃文件，确认无残留引用。

**输入上下文**：
- Phase 5 完成后的 SKILL.md（已改造）
- 废弃文件清单

**具体任务**：
1. 在以下文件头部添加废弃标记（`# DEPRECATED: 此文件已被 .opencode/mcp-servers/grsai-server/ 替代，将在后续版本删除`）：
   - `.opencode/skills/art-director/script/api_client.py`
   - `.opencode/skills/art-director/script/cos_uploader.py`
   - `.opencode/skills/art-director/script/file_cache.py`
   - `.opencode/skills/art-director/script/config.py`
   - `.opencode/skills/storyboard-generator/scripts/call_llm.py`
2. `batch_generator.py`：保留为薄 wrapper 或添加废弃标记（视 Phase 5 改造结果决定）
3. 全局搜索确认无活跃代码引用废弃文件
4. 保留 `validators.py`（storyboard-generator 的，业务逻辑独立）

**验收命令**：
```bash
# 1. 废弃文件头部有 DEPRECATED 标记
for f in \
  .opencode/skills/art-director/script/api_client.py \
  .opencode/skills/art-director/script/cos_uploader.py \
  .opencode/skills/art-director/script/file_cache.py \
  .opencode/skills/art-director/script/config.py \
  .opencode/skills/storyboard-generator/scripts/call_llm.py; do
  head -3 "$f" | grep -q "DEPRECATED" && echo "$f OK" || echo "$f MISSING DEPRECATED"
done

# 2. 无活跃代码引用废弃文件
grep -r "api_client\|cos_uploader\|file_cache" .opencode/skills/ --include="*.py" --include="*.md" | grep -v "DEPRECATED\|phase-" | grep -v "grsai-server"
# 预期：无输出或仅有注释引用

# 3. MCP server 功能完整（5 个 tool 均已注册）
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
tools = ['grsai_health_check', 'grsai_call_llm', 'grsai_generate_image', 'grsai_batch_generate', 'grsai_upload_cos']
for t in tools:
    assert t in code, f'{t} missing'
print(f'all {len(tools)} tools registered OK')
"
```

---

## 四、端到端测试 Spec

**Spec 路径**：`doc/specs/e2e-test.md`

**目标**：验证 MCP server 在完整管线中的表现。

**前置条件**：Phase 0-6 全部完成。

**测试用例**：

### E2E-01：LLM 调用链路

**操作**：
1. 启动 MCP server（opencode 自动管理）
2. Agent 调用 `grsai_call_llm` tool，传入测试 messages
3. 验证返回 content 非空、usage 包含 token 计数

**验收命令**：
```bash
# 通过 opencode 的 MCP 客户端调用（实际测试时由 agent 执行）
# 此处为离线验证 server 可启动
timeout 5 python .opencode/mcp-servers/grsai-server/server.py 2>&1 || true
# 预期：进程启动不报 ImportError
```

### E2E-02：图像生成链路

**操作**：
1. 准备 2 个测试任务的 tasks.json
2. Agent 调用 `grsai_batch_generate` tool
3. 验证返回结果中 succeeded >= 1
4. 验证 output_dir 中有下载的图片文件

**验收命令**：
```bash
# 离线验证：import 链完整
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host, load_cos_config
from grsai_client import generate_image, call_llm, _resolve_aspect_ratio
from cos_client import upload_to_cos
print('all imports OK')
"
```

### E2E-03：异常恢复

**操作**：
1. 调用 `grsai_call_llm` 传入空 messages → 预期返回错误
2. 调用 `grsai_generate_image` 传入空 prompt → 预期返回错误
3. 验证错误信息明确

### E2E-04：validators 端到端

**操作**：
1. 各 ref-generator 生成 tasks.json
2. 调用共享 validator 校验
3. 验证校验通过

**验收命令**：
```bash
# 共享 validator 端到端
python -c "
import sys, json
sys.path.insert(0, '.opencode/scripts/validators')
from image_task_validator import validate_tasks, format_report

# 角色参考图格式
tasks_role = [{'prompt': 'test', 'imageSize': '1K', 'aspectRatio': '16:9', 'filename': 'r.png', 'images': []}]
errors = validate_tasks(tasks_role, aspect_ratio='16:9')
assert not errors, f'role errors: {errors}'

# 场景参考图格式
tasks_scene = [{'prompt': 'test', 'imageSize': '1K', 'aspectRatio': '2:1', 'filename': 's.png', 'images': []}]
errors = validate_tasks(tasks_scene, aspect_ratio='2:1')
assert not errors, f'scene errors: {errors}'

print('e2e validator OK')
"
```

---

## 五、执行流程

```
Orchestrator 读取本计划
    │
    ├─ Phase 0 ──spawn general agent──→ 读 spec/phase-0-skeleton.md → 执行 → 验收
    │       ↓ 通过
    ├─ Phase 1 ──spawn general agent──→ 读 spec/phase-1-credentials.md → 执行 → 验收
    │       ↓ 通过
    │       ├─ Phase 2 ──spawn general agent──→ 读 spec/phase-2-llm-tool.md → 执行 → 验收
    │       │       ↓ 通过
    │       └─ Phase 3 ──spawn general agent──→ 读 spec/phase-3-image-tool.md → 执行 → 验收
    │               ↓ 通过（Phase 2、3 可并行）
    ├─ Phase 4 ──spawn general agent──→ 读 spec/phase-4-validators.md → 执行 → 验收
    │       ↓ 通过
    ├─ Phase 5 ──spawn system-engineer agent──→ 读 spec/phase-5-skill改造.md → 执行 → 验收
    │       ↓ 通过
    ├─ Phase 6 ──spawn general agent──→ 读 spec/phase-6-cleanup.md → 执行 → 验收
    │       ↓ 通过
    └─ E2E ───spawn general agent──→ 读 spec/e2e-test.md → 执行 → 验收
            ↓ 全部通过
        项目完成
```

---

## 六、风险与缓解

| 风险 | 缓解 |
|------|------|
| 子 agent 执行 spec 时遗漏步骤 | 每个 spec 的验收命令是自动化的，主 agent 执行验收即可发现遗漏 |
| MCP SDK 版本不兼容 | requirements.txt 锁定版本；Phase 0 验收检查 import |
| 废弃脚本被遗漏引用 | Phase 6 全局 grep 搜索确认 |
| 并行 Phase 2/3 写入同一文件 | 两个 phase 写入不同文件（grsai_client.py vs cos_client.py），无冲突 |
| 子 agent 产出不符合 spec | spec 中包含精确代码参考，子 agent 应复用而非从零编写 |

---

## 七、工作量汇总

| 阶段 | 内容 | 预估工时 |
|------|------|---------|
| Phase 0 | MCP server 骨架 | 0.5d |
| Phase 1 | 凭证统一 | 0.5d |
| Phase 2 | LLM API 工具化 | 1d |
| Phase 3 | 图像生成 API 工具化 | 1.5d |
| Phase 4 | Validators 整合 | 0.5d |
| Phase 5 | SKILL.md 改造 | 1d |
| Phase 6 | 废弃清理 | 0.5d |
| E2E | 端到端测试 | 0.5d |
| **合计** | | **6d** |

---

## 八、Spec 文件清单

| Spec 文件 | 路径 | 状态 |
|-----------|------|------|
| Phase 0 | `doc/specs/phase-0-skeleton.md` | 待创建 |
| Phase 1 | `doc/specs/phase-1-credentials.md` | 待创建 |
| Phase 2 | `doc/specs/phase-2-llm-tool.md` | 待创建 |
| Phase 3 | `doc/specs/phase-3-image-tool.md` | 待创建 |
| Phase 4 | `doc/specs/phase-4-validators.md` | 待创建 |
| Phase 5 | `doc/specs/phase-5-skill改造.md` | 待创建 |
| Phase 6 | `doc/specs/phase-6-cleanup.md` | 待创建 |
| E2E | `doc/specs/e2e-test.md` | 待创建 |
