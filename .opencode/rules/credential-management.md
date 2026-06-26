# 凭证管理流程

本影视生产管线系统中涉及多种凭证，分布在项目目录的不同位置。本文档统一说明各凭证的用途、位置、获取方式及维护流程。

---

## 1. 凭证类型概览

| 凭证 | 位置 | 使用方 | 用途 |
|------|------|--------|------|
| libtv 凭据 | `~/.libtv/credentials.json`（全局） / `.opencode/credentials/libtv_credentials.json`（项目副本） | `video-director` | 视频生成 |
| GRSAI 媒体生成凭据 | `.opencode/credentials/media_gen_config.json` | `art-director` | 图像生成 |
| GRSAI MCP 服务器凭据 | `.opencode/mcp-servers/grsai-server/credentials.json` | MCP 服务器 `server.py` | MCP 接口鉴权 |

---

## 2. libtv 凭据

### 2.1 位置说明

- **全局默认位置**：`~/.libtv/credentials.json`（由 `libtv login` 命令自动生成）
- **项目工作副本 1**：`.opencode/credentials/libtv_credentials.json`
- **项目工作副本 2**：`.opencode/credentials/credentials.json`（与上同名副本，供兼容使用）

### 2.2 使用方

`video-director`（基于 libtv CLI 的视频导演 Skill），通过环境变量 `$env:LIBTV_CONFIG_DIR` 指向 `.opencode/credentials/` 目录来加载凭据。

### 2.3 获取方式

```powershell
# 方式一：浏览器登录（推荐）
libtv login web --open

# 方式二：手机号登录
libtv login phone -p "138xxxxxxxx"
```

### 2.4 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `usertoken` | string | 用户身份令牌 |
| `useruuid` | string | 用户 UUID |
| `webid` | string | Web 会话 ID |
| `savedAt` | string (ISO8601) | 凭据保存时间 |
| `activeAccountId` | int | 当前活跃账号 ID |

---

## 3. GRSAI 媒体生成凭据

### 3.1 位置

`.opencode/credentials/media_gen_config.json`

### 3.2 使用方

`art-director`（图像生成 Skill），在批量图像生成时读取该文件获取 API 配置与云存储配置。

### 3.3 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `GRSAI_API_KEY` | string | GRSAI 平台 API 密钥 |
| `GRSAI_API_HOST` | string | API 服务地址（如 `https://grsai.dakka.com.cn`） |
| `GRSAI_MODEL` | string | 默认模型（如 `gpt-image-2`） |
| `GRSAI_OSS_ID` | string | OSS 存储空间 ID |
| `GRSAI_OSS_PATH` | string | OSS 存储路径前缀（如 `file/images`） |
| `TENCENT_COS_SECRET_ID` | string | 腾讯云 COS 密钥 ID |
| `TENCENT_COS_SECRET_KEY` | string | 腾讯云 COS 密钥 Key |
| `TENCENT_COS_BUCKET` | string | COS 存储桶名称 |
| `TENCENT_COS_REGION` | string | COS 地域（如 `ap-nanjing`） |
| `TENCENT_COS_SIGNED_URL` | bool | 是否生成签名 URL |
| `TENCENT_COS_EXPIRE_SECONDS` | int | 签名 URL 有效期（秒） |
| `ARK_API_KEY` | string | 火山引擎 ARK API 密钥 |
| `ARK_BASE_URL` | string | 火山引擎 ARK 服务地址 |

---

## 4. GRSAI MCP 服务器凭据

### 4.1 位置

`.opencode/credentials/media_gen_config.json`（与 art-director 共用系统级凭证源）

### 4.2 加载优先级

1. **环境变量**（最高优先级）
2. **系统级凭据文件**（降级兜底）

MCP 服务器 `server.py` 启动时优先读取环境变量中的凭据，若环境变量不存在则读取 `.opencode/credentials/media_gen_config.json`。

### 4.3 字段说明

与 [GRSAI 媒体生成凭据](#3-grsai-媒体生成凭据) 完全一致。

---

## 5. 流程

### 5.1 首次部署凭证（新机器 / 新项目）

在新机器或新项目上首次部署时，按以下顺序配置：

```powershell
# 步骤 1：libtv 登录
libtv login web --open

# 步骤 2：将 libtv 凭据复制到项目工作副本
Copy-Item -Path "$env:USERPROFILE\.libtv\credentials.json" -Destination ".opencode\credentials\libtv_credentials.json"
Copy-Item -Path "$env:USERPROFILE\.libtv\credentials.json" -Destination ".opencode\credentials\credentials.json"

# 步骤 3：确认 GRSAI 媒体生成凭据已就位
# 从安全备份或项目成员获取 media_gen_config.json 放入 .opencode/credentials/

# 步骤 4：MCP 服务器自动使用 media_gen_config.json，无需额外配置
```

### 5.2 libtv 重新登录（Token 过期 / 手动刷新）

当 `video-director` 报告 libtv token 过期或鉴权失败时，按以下步骤刷新：

```powershell
# 步骤 1：登出旧会话
libtv logout

# 步骤 2：重新登录
libtv login web --open

# 步骤 3：同步到项目工作副本
Copy-Item -Path "$env:USERPROFILE\.libtv\credentials.json" -Destination ".opencode\credentials\libtv_credentials.json" -Force
Copy-Item -Path "$env:USERPROFILE\.libtv\credentials.json" -Destination ".opencode\credentials\credentials.json" -Force

# 步骤 4：验证同步结果
Get-Content -Encoding UTF8 -Path ".opencode\credentials\libtv_credentials.json"
```

> **注意**：`copy` 命令用 `-Force` 参数覆盖旧文件。两个项目副本需保持一致。

### 5.3 日常更新

| 场景 | 操作 | 由谁触发 |
|------|------|---------|
| libtv token 过期 | 执行 5.2 节重新登录流程 | `video-director` 报错 → `orchestrator` 调度 |
| GRSAI API Key 更换 | 更新 `media_gen_config.json`（MCP 服务器自动读取） | 管理员手动 |
| 腾讯云 COS 配置变更 | 更新 `media_gen_config.json`（MCP 服务器自动读取） | 管理员手动 |
| MCP 服务器重启 | 自动读取最新凭据文件（无需额外操作） | 自动 |

---

## 6. 职责分工

### 6.1 职责链

```
用户 → Orchestrator（路由） → 对应子 Agent（使用凭据执行）
```

- **Orchestrator**：不直接管理或读取凭据文件，仅负责将任务路由给对应子 Agent
- **video-director**：使用 `$env:LIBTV_CONFIG_DIR` 指向的 libtv 凭据
- **art-director**：读取 `.opencode/credentials/media_gen_config.json` 获取 GRSAI 配置
- **MCP server.py**：使用环境变量或 `.opencode/credentials/media_gen_config.json`

### 6.2 各 Agent 使用的凭据

| Agent | 凭据文件 | 环境变量 |
|-------|---------|---------|
| `video-director` | `.opencode/credentials/libtv_credentials.json` （或 `credentials.json`） | `$env:LIBTV_CONFIG_DIR=.opencode/credentials/` |
| `art-director` | `.opencode/credentials/media_gen_config.json` | 无（直接读文件） |
| MCP 服务器 | `.opencode/credentials/media_gen_config.json` | 同名环境变量覆盖 |

### 6.3 谁负责管理

| 任务 | 执行者 | 说明 |
|------|--------|------|
| 首次部署凭证 | 项目成员 / DevOps 手动执行 | 按 5.1 节流程 |
| libtv token 刷新 | `video-director` 检测到过期 → 通知用户 → 用户/管理员手动执行 5.2 | CLI 交互式登录需人工操作 |
| GRSAI 凭据更新 | 管理员手动更新 `media_gen_config.json` | MCP 服务器自动读取 |
| 凭据文件完整性检查 | 各子 Agent 启动时自行校验 | 文件缺失时报错提示 |

---

## 7. 安全注意事项

1. **不要提交凭据到 Git**：确保 `.opencode/credentials/` 已加入 `.gitignore`
2. **区分环境**：开发环境与生产环境使用不同的 API Key，不要混用
3. **定期轮换**：GRSAI API Key 和 COS Secret Key 应定期更换
4. **最小权限**：各 Agent 只读取自己需要的凭据文件，不跨权限访问
