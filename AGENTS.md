# 全局行为规则

所有 agent 使用精简的中文与用户交互。严禁使用任何emoji！！

## Python 环境
- 根项目虚拟环境：`.venv/`（项目根目录）
- GRSAI MCP 独立环境：`.opencode/mcp-servers/grsai-server/.venv/`（与根隔离）
- Python 版本：3.13.x（uv 管理，自动下载，不依赖系统全局包）
- 依赖声明：根 `pyproject.toml`；MCP 见 `.opencode/mcp-servers/grsai-server/pyproject.toml`
- 依赖管理：`uv sync`；新机器推荐一键脚本 `.opencode/scripts/bootstrap_mcp.sh`（Unix）或 `bootstrap_mcp.ps1`（Windows）

### 部署流程（新机器）
见 [.opencode/rules/deployment.md](.opencode/rules/deployment.md)。

### MCP 服务器配置
opencode.json 使用 `uv run` 跨平台启动 grsai-server（无需 sh/bat 包装）：
```json
"command": ["uv", "run", "--no-sync", "--directory", ".opencode/mcp-servers/grsai-server", "-m", "grsai_server"]
```

> 须先 bootstrap / `uv sync` 生成子项目 `.venv`。`--no-sync` 避免 MCP 冷启动联网。详见 deployment.md 与 grsai-server/README.md。

## 文件操作规则
- 项目业务文件存放在 `project/` 目录下
- `temp/` 路径下的任何文件**禁止删除**（临时文件存放在 `temp/` 中）

## 配置与技能修改规则
- `.opencode/` 下的所有 skill/agent/config 文件必须通过 `system-engineer` 子 agent（调试 skill 时自动加载 `skill-creator` 技能，调试 MCP Server 时自动加载 `mcp-builder` 技能）修改，除system-engineer之外的任何 agent 不得直接操作。

## SubAgent 职责边界
- 每个subagent **只完成自己职责相关的事**，严禁越权。
- coordinator 只做元数据管理（创建项目、修改 stages/manifest/events、打包归档），**不参与任何内容制作**
- 内容制作（角色/场景/道具参考图任务表、分镜脚本、生图、视频生成等）必须由对应的 subagent 完成

## Git/GitHub 网络代理

GitHub 网络配置方法见 [.opencode/rules/git-network-proxy.md](.opencode/rules/git-network-proxy.md)。

## 凭证管理

凭证的完整流程见 [.opencode/rules/credential-management.md](.opencode/rules/credential-management.md)。


