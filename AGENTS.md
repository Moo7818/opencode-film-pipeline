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

## PowerShell 编码规范（Windows）
所有 PowerShell 命令优先通过 `pwsh`（PowerShell 7.6.2）执行，其默认 UTF-8 无代码页问题：
```powershell
pwsh -Command "命令"
```
若必须在 PowerShell 5 中执行，先执行 `chcp 65001` 切换活动代码页到 UTF-8：
```powershell
chcp 65001; 要执行的命令
```

### ⚠️ `bash tool` 调用注意事项
bash tool 的 shell 已经是 pwsh，因此：
- **禁止嵌套** `pwsh -Command "..."`，直接执行命令即可
- 传中文参数必须用**单引号**包裹（如 `-Name '中文名'`），阻止外层 pwsh 展开
- 设置环境变量在同一作用域用 `$env:KEY='val'`，勿传入内层命令

```powershell
# ✅ 正确：直接在 bash tool 中执行
$env:PYTHONIOENCODING='utf-8'; & script.ps1 -Name '项目名称' -Path 'D:\路径\含中文\文件.wav'

# ❌ 错误：嵌套 pwsh 会导致 $env: 被外层展开
pwsh -Command "$env:PYTHONIOENCODING='utf-8'; & script.ps1"
```

所有文件读写必须显式指定 `-Encoding UTF8`：
- 读取：`Get-Content -Encoding UTF8 -Raw "路径"`
- 写入：`Set-Content -Encoding UTF8 "路径" -Value "内容"`
- Python：`open("路径", "r", encoding="utf-8")` / `open("路径", "w", encoding="utf-8")`
- JSON：`ConvertTo-Json -Depth 10` / `json.dump(data, f, ensure_ascii=False, indent=2)`

## 配置与技能修改规则
- `.opencode/` 下的所有 skill/agent/config 文件必须通过 `skill-engineer` 子 agent（其加载 `skill-creator` 技能）修改，任何 agent 不得直接操作

## 子 Agent 职责边界
- 每个子 agent **只完成自己分内的事**，不得越权替其他 agent 执行任务
- coordinator 只做元数据管理（创建项目、修改 stages/manifest/events、打包归档），**不参与任何内容制作**
- 内容制作（角色/场景/道具参考图任务表、分镜脚本、生图、视频生成等）必须由对应的专业子 agent 完成

## Git/GitHub 网络代理

中国网络环境下 GitHub 网络配置方法见 [.opencode/rules/git-network-proxy.md](.opencode/rules/git-network-proxy.md)。

## 凭证管理

系统凭证（libtv 凭据、GRSAI 媒体生成密钥、MCP 服务器凭据）的完整管理流程见 [.opencode/rules/credential-management.md](.opencode/rules/credential-management.md)。


