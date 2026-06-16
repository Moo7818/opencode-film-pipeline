# 全局行为规则

所有 agent 使用中文推理和对话。

## Python 环境
- 虚拟环境路径：`.venv/`（项目根目录下）
- Python 版本：3.13.x（uv 管理）
- 依赖管理：`uv sync` 同步，`uv add <包>` 新增

### 初次使用初始化
```bash
# 1. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 初始化虚拟环境并生成 .env
./scripts/setup_venv.sh

# 3. 重启 opencode 使 MCP 配置生效
```

### 跨平台虚拟环境路径
| 平台 | Python 路径 | 激活方式 |
|------|------------|---------|
| macOS/Linux | `.venv/bin/python3` | `source .venv/bin/activate` |
| Windows (Git Bash/WSL) | `.venv/Scripts/python.exe` | `.venv/Scripts/activate` |

### MCP 服务器配置
opencode.json 中使用环境变量引用 Python 路径，由 `.env` 文件提供：
```json
"command": ["{env:VENV_PYTHON}", ".opencode/mcp-servers/grsai-server/server.py"]
```
运行 `./scripts/setup_venv.sh` 会自动生成正确的 `.env` 文件。

## 文件操作规则
- 项目业务文件存放在 `project/` 目录下
- `temp/` 路径下的任何文件**禁止删除**
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
所有文件读写必须显式指定 `-Encoding UTF8`：
- 读取：`Get-Content -Encoding UTF8 -Raw "路径"`
- 写入：`Set-Content -Encoding UTF8 "路径" -Value "内容"`
- Python：`open("路径", "r", encoding="utf-8")` / `open("路径", "w", encoding="utf-8")`
- JSON：`ConvertTo-Json -Depth 10` / `json.dump(data, f, ensure_ascii=False, indent=2)`

## 配置与技能修改规则
- `.opencode/` 下的所有 skill/agent/config 文件必须通过 `skill-engineer` 子 agent（其加载 `skill-creator` 技能）修改，任何 agent 不得直接操作

## Git/GitHub 网络代理（中国网络环境经验）

在中国网络环境下，GitHub 常因防火墙无法直连，错误如 `Connection was reset` 或 `Could not connect to server`。

**核心解法：SSH（可靠绕过 HTTPS 封锁）**

HTTPS 到 `github.com:443` 通常被墙，但 `ssh.github.com:443` 及 `api.github.com:443` 一般可通过。推荐将远程仓库切换到 SSH 方式：

1. **生成 SSH 密钥**（如没有）：
   ```powershell
   ssh-keygen -t ed25519 -C "你的邮箱" -f "$env:USERPROFILE\.ssh\id_ed25519"
   ```
2. **将公钥添加为 Deploy Key**（通过 `api.github.com`，HTTPS 被墙时仍可用）：
   ```powershell
   $pubkey = Get-Content -Raw "$env:USERPROFILE\.ssh\id_ed25519.pub" | ForEach-Object { $_.Trim() }
   $body = @{ title = "Deploy-Key"; key = $pubkey; read_only = $false } | ConvertTo-Json -Compress
   Set-Content -Encoding ASCII -NoNewline -Path "$env:TEMP\deploy-key.json" -Value $body
   gh api --method POST /repos/所有者/仓库名/keys --input "$env:TEMP\deploy-key.json"
   ```
3. **配置 SSH 走 443 端口**（写入 `~/.ssh/config`）：
   ```
   Host github.com
     HostName ssh.github.com
     Port 443
     User git
     IdentityFile ~/.ssh/id_ed25519
   ```
4. **切换远程 URL 并推送**：
   ```powershell
   git remote set-url origin git@github.com:所有者/仓库名.git
   git push
   ```

**替代方案：本地代理**（如有代理服务运行在 localhost）：
```powershell
git -c http.proxy=http://127.0.0.1:9674 -c https.proxy=http://127.0.0.1:9674 push
```
永久配置：`git config --global http.proxy http://127.0.0.1:9674`（取消用 `--unset`）


