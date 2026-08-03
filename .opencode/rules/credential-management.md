# 凭证管理

本系统涉及三类凭证，分布在 `.opencode/credentials/` 和 `~/.libtv/` 下。

---

## 凭证总览

| 凭证 | 文件 | 使用方 | 用途 |
|------|------|--------|------|
| libtv | `~/.libtv/credentials.json` → 项目副本 `.opencode/credentials/credentials.json` | `video-director` | 视频生成（通过 `$LIBTV_CONFIG_DIR` 指向 `.opencode/credentials/`） |
| GRSAI 媒体生成 | `.opencode/credentials/media_gen_config.json` | `art-director` / MCP 服务器 | 图像生成、COS 上传 |

> MCP 服务器优先读环境变量，降级读 `media_gen_config.json`，字段与 art-director 完全一致。

---

## libtv 凭据

### 获取与同步

```bash
# 登录（浏览器方式）
libtv login web --open

# 同步到项目副本（登录后必须手动执行）
cp ~/.libtv/credentials.json .opencode/credentials/credentials.json
```

> `libtv login` 写入 `~/.libtv/credentials.json`，**不会自动同步**到项目目录。两个副本需保持一致。

### Token 过期刷新

```bash
libtv logout
libtv login web --open
cp ~/.libtv/credentials.json .opencode/credentials/credentials.json
```

### 字段

`usertoken` / `useruuid` / `webid` / `savedAt` / `activeAccountId`

### 常见问题

- **文件名**：`$LIBTV_CONFIG_DIR` 指向目录后，libtv 查找的是 `credentials.json`（非 `libtv_credentials.json`）。
- **多账号**：`libtv account list` → `libtv account use <id>` 切换到有权限的团队账号。
- **团队画布**：个人账号无法访问团队空间，需切换到团队账号。

---

## GRSAI 媒体生成凭据

文件：`.opencode/credentials/media_gen_config.json`

| 字段组 | 字段 | 说明 |
|--------|------|------|
| GRSAI API | `GRSAI_API_KEY` / `GRSAI_API_HOST` / `GRSAI_MODEL` | API 密钥、服务地址、默认模型 |
| OSS 存储 | `GRSAI_OSS_ID` / `GRSAI_OSS_PATH` | OSS 空间 ID、路径前缀 |
| 腾讯云 COS | `TENCENT_COS_SECRET_ID` / `TENCENT_COS_SECRET_KEY` / `TENCENT_COS_BUCKET` / `TENCENT_COS_REGION` / `TENCENT_COS_SIGNED_URL` / `TENCENT_COS_EXPIRE_SECONDS` | COS 密钥、存储桶、地域、签名配置 |
| 火山引擎 | `ARK_API_KEY` / `ARK_BASE_URL` | ARK API 密钥、服务地址 |

### 更新方式

管理员手动编辑 `media_gen_config.json`，MCP 服务器和 art-director 下次读取时自动生效。

---

## 首次部署

```bash
# 1. libtv 登录并同步
libtv login web --open
cp ~/.libtv/credentials.json .opencode/credentials/credentials.json

# 2. 放入 GRSAI 凭据（从安全备份或项目成员获取）
# 确保 .opencode/credentials/media_gen_config.json 就位

# 3. MCP 服务器自动使用 media_gen_config.json，无需额外配置
```

---

## 职责

| 角色 | 职责 |
|------|------|
| Orchestrator | 不直接管理凭据，仅路由任务给子 Agent |
| video-director | 通过 `$LIBTV_CONFIG_DIR` 加载 libtv 凭据 |
| art-director | 直接读取 `media_gen_config.json` |
| MCP 服务器 | 优先环境变量，降级读 `media_gen_config.json` |
| 各 Agent | 启动时自行校验凭据文件完整性，缺失时报错 |

---

## 安全

1. `.opencode/credentials/` 必须加入 `.gitignore`
2. 开发与生产环境使用不同 API Key
3. GRSAI API Key 和 COS Secret Key 定期轮换
4. 各 Agent 仅读取自己需要的凭据文件
