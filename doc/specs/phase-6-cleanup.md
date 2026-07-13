# Phase 6 Spec：废弃脚本清理

> 目标：标记废弃文件，确认无残留引用

## 输入上下文

读取以下文件确认当前状态：
- Phase 5 完成后的 art-director/SKILL.md（已改造）
- Phase 5 完成后的 storyboard-generator/SKILL.md（已改造）

## 任务

### 1. 标记废弃文件

在以下 5 个文件头部添加废弃标记（不删除文件，保留供参考）：

废弃标记格式：
```python
# DEPRECATED: 此文件已被 .opencode/mcp-servers/grsai-server/ 中的对应模块替代。
# 图像生成 API → grsai_client.py
# COS 上传 → cos_client.py
# 凭证管理 → config.py
# 批量生成 → grsai_batch_generate MCP tool
# 将在后续版本删除。
```

需要标记的文件：
1. `.opencode/skills/art-director/script/api_client.py`（218 行）
2. `.opencode/skills/art-director/script/cos_uploader.py`（110 行）
3. `.opencode/skills/art-director/script/file_cache.py`（155 行）
4. `.opencode/skills/art-director/script/config.py`（93 行）
5. `.opencode/skills/storyboard-generator/scripts/call_llm.py`（163 行）

### 2. 评估 batch_generator.py

`batch_generator.py`（632 行）是 art-director 的主 CLI 入口。由于 SKILL.md 已改造为 MCP tool 调用，此文件不再被 agent 使用。

**决策**：在文件头部添加废弃标记，不删除。

废弃标记格式：
```python
# DEPRECATED: 此文件已被 MCP tool grsai_batch_generate 替代。
# Agent 现在通过 MCP tool 调用图像生成，不再使用此 CLI。
# 保留供参考，将在后续版本删除。
```

### 3. 全局搜索确认无残留引用

搜索整个 `.opencode/skills/` 目录，确认废弃文件名不再出现在活跃代码中。

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/skills/art-director/script/api_client.py` | 添加废弃标记 |
| `.opencode/skills/art-director/script/cos_uploader.py` | 添加废弃标记 |
| `.opencode/skills/art-director/script/file_cache.py` | 添加废弃标记 |
| `.opencode/skills/art-director/script/config.py` | 添加废弃标记 |
| `.opencode/skills/art-director/script/batch_generator.py` | 添加废弃标记 |
| `.opencode/skills/storyboard-generator/scripts/call_llm.py` | 添加废弃标记 |

## 验收

```bash
# 1. 废弃文件头部有 DEPRECATED 标记
for f in \
  .opencode/skills/art-director/script/api_client.py \
  .opencode/skills/art-director/script/cos_uploader.py \
  .opencode/skills/art-director/script/file_cache.py \
  .opencode/skills/art-director/script/config.py \
  .opencode/skills/art-director/script/batch_generator.py \
  .opencode/skills/storyboard-generator/scripts/call_llm.py; do
  if head -5 "$f" | grep -q "DEPRECATED"; then
    echo "$f ✓"
  else
    echo "$f ✗ MISSING DEPRECATED"
  fi
done

# 2. 无活跃代码引用废弃文件（排除自身和废弃文件）
grep -r "api_client\|cos_uploader\|file_cache\|call_llm" \
  .opencode/skills/ --include="*.py" --include="*.md" \
  | grep -v "DEPRECATED" \
  | grep -v "script/" \
  | grep -v "scripts/" \
  | grep -v "grsai-server" \
  || echo "no active references"

# 3. MCP server 5 个 tool 均已注册
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
tools = ['grsai_health_check', 'grsai_call_llm', 'grsai_generate_image', 'grsai_batch_generate', 'grsai_upload_cos']
for t in tools:
    assert t in code, f'{t} missing'
print(f'all {len(tools)} tools registered OK')
"

# 4. 共享 validator 存在
test -f .opencode/scripts/validators/image_task_validator.py && echo "shared validator exists OK" || echo "MISSING"
```
