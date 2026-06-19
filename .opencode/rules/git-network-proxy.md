# Git/GitHub 网络代理（中国网络环境经验）

在中国网络环境下，GitHub 常因防火墙无法直连，错误如 `Connection was reset` 或 `Could not connect to server`。

## 核心解法：SSH（可靠绕过 HTTPS 封锁）

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

## 替代方案：本地代理

如有代理服务运行在 localhost：
```powershell
git -c http.proxy=http://127.0.0.1:9674 -c https.proxy=http://127.0.0.1:9674 push
```
永久配置：`git config --global http.proxy http://127.0.0.1:9674`（取消用 `--unset`）
