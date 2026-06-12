# 全局行为规则

所有 agent 使用中文推理和对话。

## Python 环境
- 虚拟环境路径：`.venv/`（项目根目录下）
- Python 版本：3.13.11（uv 管理）
- 激活：`.venv\Scripts\activate`（Windows） / `source .venv/bin/activate`（Unix）
- 运行 Python 脚本时务必使用 `.venv\Scripts\python.exe`（Windows）或在已激活的 venv 内执行
- 依赖管理：`uv sync` 同步，`uv add <包>` 新增

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

**排查与解决：**

1. **检查本地代理端口**（常见：7890/7891 Clash、1080/10808 v2ray、9674 等）：
   ```powershell
   Test-NetConnection -ComputerName 127.0.0.1 -Port 9674 -WarningAction SilentlyContinue
   ```
2. **检查 Windows 系统代理**（可能已配但未启用）：
   ```powershell
   Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -Name ProxyServer -ErrorAction SilentlyContinue
   Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -Name ProxyEnable -ErrorAction SilentlyContinue
   ```
   `ProxyEnable = 1` 为启用，`0` 为禁用。
3. **临时使用代理**：
   ```powershell
   git -c http.proxy=http://127.0.0.1:9674 -c https.proxy=http://127.0.0.1:9674 push
   ```
4. **永久配置代理**：
   ```powershell
   git config --global http.proxy http://127.0.0.1:9674
   git config --global https.proxy http://127.0.0.1:9674
   ```
5. **取消代理**（切换到不需代理的网络时）：
   ```powershell
   git config --global --unset http.proxy
   git config --global --unset https.proxy
   ```


