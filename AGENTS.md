# 全局行为规则

所有 agent 使用中文推理和对话。

## Python 环境
- 虚拟环境路径：`.venv/`（项目根目录）
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
- `.opencode/` 配置目录只读，业务文件放 `project/`


## 配置与技能修改规则
- `.opencode/` 下的所有 skill/agent/config 文件必须通过 `system-engineer` 子 agent（调试 skill 时自动加载 `skill-creator` 技能，调试 MCP Server 时自动加载 `mcp-builder` 技能）修改，任何 agent 不得直接操作

## 子 Agent 职责边界
- 每个子 agent **只完成自己分内的事**，不得越权替其他 agent 执行任务
- coordinator 只做元数据管理（创建项目、修改 stages/manifest/events、打包归档），**不参与任何内容制作**
- 内容制作（角色/场景/道具参考图任务表、分镜脚本、生图、视频生成等）必须由对应的专业子 agent 完成

## Git/GitHub 网络代理

中国网络环境下 GitHub 网络配置方法见 [.opencode/rules/git-network-proxy.md](.opencode/rules/git-network-proxy.md)。

## 凭证管理

系统凭证（libtv 凭据、GRSAI 媒体生成密钥、MCP 服务器凭据）的完整管理流程见 [.opencode/rules/credential-management.md](.opencode/rules/credential-management.md)。

### libtv 凭证常见问题

1. **文件名不匹配**：`$env:LIBTV_CONFIG_DIR` 指向 `.opencode/credentials/` 后，libtv 查找的是该目录下的 **`credentials.json`**，而非 `libtv_credentials.json`（后者供 MCP 启动器使用）。登录后必须：
   ```powershell
   Copy-Item -Path "~/.libtv/credentials.json" -Destination ".opencode/credentials/credentials.json" -Force
   ```

2. **多账号切换**：用户可能有个人+多个团队账号，需先 `libtv account list` 查看可用账号，再用 `libtv account use <accountId>` 切换到有权限的团队账号。画布如果属于团队空间，个人账号无法访问。

3. **登录后凭证不同步**：`libtv login web --open` 写入 `~/.libtv/credentials.json`，不会自动同步到 `.opencode/credentials/`，必须手动复制。


