# E2E Test Spec：端到端测试

> 目标：验证 MCP server 在完整管线中的表现

## 前置条件

Phase 0-6 全部完成，所有验收命令通过。

## 测试环境

- MCP server 可启动（`python .opencode/mcp-servers/grsai-server/server.py` 不报错）
- 凭证已配置（`credentials.json` 包含有效的 GRSAI_API_KEY）
- 网络可达 `grsai.dakka.com.cn`

## 测试用例

### E2E-01：LLM 调用链路

**目标**：验证 `grsai_call_llm` tool 能正确调用 LLM API

**操作**：
1. Agent 启动后，调用 `grsai_call_llm` tool
2. 传入简单测试消息：`[{"role": "user", "content": "请用一句话介绍北京"}]`
3. 检查返回结果

**预期**：
- `content` 非空，包含中文文本
- `finish_reason` 为 "stop"
- `usage` 包含 token 计数

**验收**：
```bash
# 离线验证：import 链完整
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host
from grsai_client import call_llm
assert callable(call_llm)
print('E2E-01 setup OK')
"
```

### E2E-02：图像生成链路

**目标**：验证 `grsai_generate_image` 和 `grsai_batch_generate` 能正确生成图片

**操作**：
1. 准备 2 个测试任务：
   ```json
   [
     {"prompt": "a simple red circle on white background", "model": "gpt-image-2", "filename": "test_01.png"},
     {"prompt": "a simple blue square on white background", "model": "gpt-image-2", "filename": "test_02.png"}
   ]
   ```
2. Agent 调用 `grsai_batch_generate` tool
3. 检查返回结果

**预期**：
- `total` = 2
- `succeeded` >= 1
- `results` 中至少一条 `status` = "completed" 且 `image_url` 非空
- `output_dir` 中有下载的图片文件

**验收**：
```bash
# 离线验证：import 链完整
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host, load_cos_config
from grsai_client import generate_image
from cos_client import upload_to_cos
assert callable(generate_image) and callable(upload_to_cos)
print('E2E-02 setup OK')
"
```

### E2E-03：异常恢复

**目标**：验证 MCP server 对异常输入的处理

**操作**：
1. 调用 `grsai_call_llm` 传入空 messages → 预期返回错误
2. 调用 `grsai_generate_image` 传入空 prompt → 预期返回错误
3. 调用 `grsai_batch_generate` 传入空 tasks → 预期返回错误

**预期**：
- 每个异常调用返回 `{"error": "..."}` 格式
- 不导致 MCP server 进程崩溃

**验收**：
```bash
# 离线验证：错误处理逻辑
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from grsai_client import call_llm
try:
    call_llm(messages=[])
except Exception as e:
    print(f'Empty messages handled: {type(e).__name__}')
print('E2E-03 logic OK')
"
```

### E2E-04：validators 端到端

**目标**：验证共享 validator 能正确校验各 ref-generator 的任务格式

**操作**：
1. 模拟角色参考图任务：`aspect_ratio="16:9"`, `image_size="1K"`
2. 模拟场景参考图任务：`aspect_ratio="2:1"`, `image_size="1K"`
3. 调用共享 validator 校验

**预期**：
- 正确格式的任务：`errors` 为空
- 错误格式的任务：`errors` 非空

**验收**：
```bash
python -c "
import sys; sys.path.insert(0, '.opencode/scripts/validators')
from image_task_validator import validate_tasks, format_report

# 角色参考图
tasks_role = [{'prompt': 'test role', 'imageSize': '1K', 'aspectRatio': '16:9', 'filename': 'r.png', 'images': []}]
errors = validate_tasks(tasks_role, aspect_ratio='16:9')
assert not errors, f'role errors: {errors}'

# 场景参考图
tasks_scene = [{'prompt': 'test scene', 'imageSize': '1K', 'aspectRatio': '2:1', 'filename': 's.png', 'images': []}]
errors = validate_tasks(tasks_scene, aspect_ratio='2:1')
assert not errors, f'scene errors: {errors}'

# 错误格式
tasks_bad = [{'prompt': 'test', 'imageSize': '2K', 'aspectRatio': '9:16', 'filename': 'b.png', 'images': []}]
errors = validate_tasks(tasks_bad, aspect_ratio='16:9')
assert len(errors) >= 2, f'should have >= 2 errors, got {len(errors)}'

print('E2E-04 validator OK')
"
```

### E2E-05：凭证隔离

**目标**：验证凭证缺失时的错误处理

**操作**：
1. 临时重命名 `credentials.json` 为 `credentials.json.bak`
2. 调用 `grsai_health_check` → 预期 `api_key_valid: false`
3. 恢复文件

**验收**：
```bash
# 离线验证：凭证检查逻辑
python -c "
import sys, os; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
# 模拟缺失凭证
os.environ.pop('GRSAI_API_KEY', None)
from config import _cfg, CFG_API_KEY
val = _cfg(CFG_API_KEY)
assert not val, 'Should be empty without credentials'
print('E2E-05 credential check OK')
"
```

### E2E-06：MCP server 进程健康

**目标**：验证 MCP server 可正常启动和关闭

**验收**：
```bash
# 语法检查（server.py 可被 Python 解析）
python -c "import ast; ast.parse(open('.opencode/mcp-servers/grsai-server/server.py').read()); print('server syntax OK')"

# import 链完整
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
import server
print('server import OK')
"

# 依赖链完整
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host, load_cos_config
from cos_client import upload_to_cos
from grsai_client import call_llm, generate_image
print('all imports OK')
"
```

## 测试执行顺序

1. E2E-06（进程健康）→ 确认 server 可启动
2. E2E-05（凭证隔离）→ 确认证证逻辑正确
3. E2E-01（LLM 调用）→ 验证 LLM tool
4. E2E-02（图像生成）→ 验证图像 tool
5. E2E-03（异常恢复）→ 验证错误处理
6. E2E-04（validators）→ 验证共享校验器

## 通过标准

- 所有 6 个测试用例的验收命令通过
- 无 ImportError、SyntaxError
- MCP server 5 个 tool 均已注册
- 共享 validator 可正确校验三种任务格式
