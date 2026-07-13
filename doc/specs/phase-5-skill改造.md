# Phase 5 Spec：SKILL.md 全面改造

> 目标：将 art-director 和 storyboard-generator 的 SKILL.md 从 CLI 调用切换为 MCP tool 调用

## 输入上下文

读取以下文件：
- `.opencode/skills/art-director/SKILL.md`（完整读取）
- `.opencode/skills/storyboard-generator/SKILL.md`（完整读取）
- `.opencode/mcp-servers/grsai-server/server.py`（了解已注册的 tool 名称和参数）
- `.opencode/mcp-servers/grsai-server/grsai_client.py`（了解函数签名）

## 任务

### 1. 改造 art-director/SKILL.md

**移除**以下内容：
- 所有 `batch_generator.py` 路径引用（如 `{baseDir}/script/batch_generator.py`）
- CLI 参数说明（`--tasks`, `--model`, `--concurrency`, `--poll-delay` 等）
- 凭证配置说明（如 `media_gen_config.json` 路径、环境变量配置）
- `api_client.py`、`cos_uploader.py`、`file_cache.py`、`config.py` 的模块结构说明

**保留**以下内容：
- 提示词构建规则（风格关键词、四视图布局、参考图注入模式等）
- 模型差异说明（gpt-image-* vs nano-banana-* 的参数格式差异）
- 参考图命名约定（角色参考_01、场景参考_02 等）
- `.opencode/schemas/image-generation.json` 的引用

**新增** MCP tool 调用说明，在 SKILL.md 中合适位置添加：

```markdown
## 图像生成执行

通过 MCP tool `grsai_batch_generate` 执行批量生图。

### 输入格式

任务 JSON 格式不变（仍按 `.opencode/schemas/image-generation.json` 生成），
字段映射：
- `prompt` → MCP tool `prompt`
- `model` → MCP tool `model`
- `aspectRatio` → MCP tool `aspect_ratio`
- `imageSize` → MCP tool `image_size`
- `images` → MCP tool `reference_images`
- `filename` → MCP tool `filename`

### 调用示例

```
tool: grsai_batch_generate
input:
  tasks:
    - prompt: "生成全局角色参考图，..."
      model: "gpt-image-2"
      aspect_ratio: "2048x1152"
      image_size: "4K"
      filename: "character_01.png"
  output_dir: "./generated/角色参考图"
  concurrency: 10
```

### 返回格式

```json
{
  "batch_id": "batch_20260616_120000",
  "total": 5,
  "succeeded": 5,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "status": "completed",
      "image_url": "https://...",
      "local_path": "./generated/角色参考图/character_01.png"
    }
  ]
}
```

### 单张生成

如需生成单张图片（而非批量），使用 `grsai_generate_image`：
```
tool: grsai_generate_image
input:
  prompt: "..."
  model: "gpt-image-2"
  aspect_ratio: "16:9"
  image_size: "4K"
```
```

### 2. 改造 storyboard-generator/SKILL.md

**移除**以下内容：
- `call_llm.py` CLI 调用模式（如 `python call_llm.py --build-request`）
- `call_llm.py` 路径引用
- `call_llm.py` 的 `--input`、`--output`、`--batch-dir`、`--pipeline-dir` 参数说明
- 凭证配置说明

**保留**以下内容：
- 分片策略说明（shard_manager.py 的使用方式）
- validators.py 调用说明
- 分镜 JSON 结构规范（场→组→镜三级）
- System Prompt 构建规则

**新增** MCP tool 调用说明：

```markdown
## LLM 调用

通过 MCP tool `grsai_call_llm` 执行 LLM 调用。

### 单次调用

```
tool: grsai_call_llm
input:
  messages:
    - role: "system"
      content: "你是一个专业的分镜脚本..."
    - role: "user"
      content: "请将以下剧本拆解为分镜..."
  model: "gemini-3.1-pro"
  temperature: 0.7
```

### 返回格式

```json
{
  "content": "LLM 输出的 JSON 文本...",
  "finish_reason": "stop",
  "usage": {"prompt_tokens": 1200, "completion_tokens": 3000, "total_tokens": 4200}
}
```

### 长剧本分片模式

当剧本超过 2000 字时，使用分片策略：
1. 调用 `shard_manager.py` 分片（CLI，保留不变）
2. 每个分片调用 `grsai_call_llm` tool（可并发）
3. 调用 `shard_manager.py --merge` 合并（CLI，保留不变）

分片模式下，agent 并发调用多个 `grsai_call_llm` tool，每个分片独立。
```

### 3. 验证其他 skill 不受影响

确认以下 SKILL.md 未被修改：
- `.opencode/skills/roles-ref-generator/SKILL.md`
- `.opencode/skills/prop-ref-generator/SKILL.md`
- `.opencode/skills/scene-ref-generator/SKILL.md`
- `.opencode/skills/video-director-libtv/SKILL.md`
- `.opencode/skills/producer/SKILL.md`

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/skills/art-director/SKILL.md` | 修改（移除 CLI 引用，添加 MCP tool 说明） |
| `.opencode/skills/storyboard-generator/SKILL.md` | 修改（移除 CLI 引用，添加 MCP tool 说明） |

## 验收

```bash
# 1. art-director SKILL.md 无废弃引用
count=$(grep -c "batch_generator.py" .opencode/skills/art-director/SKILL.md 2>/dev/null || echo "0")
echo "art-director batch_generator references: $count"
test "$count" -eq "0" && echo "PASS" || echo "FAIL"

# 2. storyboard-generator SKILL.md 无废弃引用
count=$(grep -c "call_llm.py" .opencode/skills/storyboard-generator/SKILL.md 2>/dev/null || echo "0")
echo "storyboard-generator call_llm references: $count"
test "$count" -eq "0" && echo "PASS" || echo "FAIL"

# 3. 两个 SKILL.md 包含 MCP tool 名称
grep -c "grsai_" .opencode/skills/art-director/SKILL.md
grep -c "grsai_" .opencode/skills/storyboard-generator/SKILL.md

# 4. 其他 skill 未受影响
grep -rl "grsai_" .opencode/skills/ | grep -v "art-director\|storyboard-generator\|grsai-server" || echo "no contamination"
```
