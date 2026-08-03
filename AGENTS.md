# 全局行为规则

所有 agent 使用精简的中文与用户交互。严禁使用任何emoji！！

## Python 环境
- 必须使用此虚拟环境，路径：`.venv/`（项目根目录）
- Python 版本：3.13.x（uv 管理）
- 依赖声明：`pyproject.toml`（项目根目录）
- 依赖管理：`uv sync` 安装/同步，`uv add <包>` 新增

### 部署流程（新机器）
见 [.opencode/rules/deployment.md](.opencode/rules/deployment.md)。

### MCP 服务器配置
opencode.json 使用 `.opencode/scripts/mcp_python.sh` 作为 Python 启动器，运行时自动检测 `.venv/bin/python3`（Unix）或 `.venv/Scripts/python.exe`（Windows）：
```json
"command": [".opencode/scripts/mcp_python.sh", ".opencode/mcp-servers/grsai-server/server.py"]
```

> 包装脚本自动检测平台路径，无需手动配置 `{env:*}` 或 `.env`。

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


