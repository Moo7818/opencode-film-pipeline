# opencode-film-pipeline

基于 [OpenCode](https://opencode.ai) AI Agent 框架构建的影视/动画制作管线工作区。通过编排多个专业 AI Agent（角色导演、分镜导演、美术指导、视频导演等），覆盖从剧本解析、角色/场景/道具设定提取、视觉资产生成，到分镜拆解、AI 视频生成的全流程生产。

## 目录结构

```
├── .opencode/              # OpenCode 配置（只读）
│   ├── skills/             #   17 个技能包（agent 能力模块）
│   ├── mcp-servers/        #   MCP 服务器（GRSAI 图像生成 API）
│   ├── schemas/            #   共享 JSON Schema（图像生成、项目配置）
│   ├── rules/              #   Agent 行为规则（主控、网络代理）
│   ├── scripts/            #   启动脚本与校验器
│   └── credentials/        #   API 凭证（加密存储）
├── project/                # 业务项目目录（每个子目录为一个独立客户项目）
├── doc/                    # 项目文档与经验总结
├── temp/                   # 临时文件（禁止删除）
├── .meta/                  # 项目元数据（stages, events, manifest）
├── .libtv/                 # LibTV 画布绑定状态
├── .github/                # CI / GitHub Actions
├── AGENTS.md               # 全局 Agent 行为规范
└── opencode.json           # OpenCode 主配置（agent 定义、MCP、权限）
```

## 管线架构

### 6 阶段制作管线

| 阶段 | 负责 Agent | 产出 |
|------|-----------|------|
| **① 项目初始化** | Coordinator | 项目结构、全局配置 (`project_config.json`) |
| **② 监制提取设定** | Producer | 角色/场景/道具设定、分集剧本、原始剧本结构化 |
| **③ 全局视觉资产生成** | Character/Set/Prop Director | 角色四视图、场景参考图、道具六视图任务 JSON |
| **④ 拆解分镜** | Storyboard Director | 场→组→镜三级结构化 JSON 分镜脚本 |
| **⑤ 剧集级参考图** | Art Director | 基于分镜的角色/场景/道具剧集级参考图 |
| **⑥ 视频生成** | Video Director | libtv 画布项目 → video 节点 → AI 视频成片 |

### Agent 架构

```
Orchestrator（总指挥）── 调度分发，禁止越权
  ├── Coordinator        项目统筹
  ├── Producer           监制（剧本解析+设定提取）
  ├── Writer             编剧（创作/润色）
  ├── Character Director 角色导演（角色参考图）
  ├── Set Designer       置景师（场景参考图）
  ├── Prop Maker         道具师（道具参考图）
  ├── Art Director       美术指导（图像生成执行）
  ├── Storyboard Director分镜导演（分镜拆解）
  └── Video Director     视频导演（AI 视频生成）
```

## 技能清单（17 个）

| 技能 | 功能 |
|------|------|
| **producer** | 原始剧本解析，提取角色/场景/道具设定，生成分集剧本，支持联网检索历史资料 |
| **script-writer** | 剧本/脚本创作润色，支持电影/动画/短视频/广告/游戏等类型 |
| **roles-ref-generator** | 角色四视图/群像展示图任务 JSON 生成，支持全局/剧集/群像三模式 |
| **scene-ref-generator** | 场景俯瞰+三宫格参考图任务 JSON 生成 |
| **prop-ref-generator** | 道具 2×2 四宫格/六视图参考图任务 JSON 生成 |
| **art-director** | 图像生成执行器：通过 GRSAI 平台并发提交任务→轮询→下载→OSS 持久化 |
| **storyboard-generator** | 分集剧本 → 场→组→镜三级结构化 JSON 分镜脚本 |
| **video-director-libtv** | 分镜组 JSON → libtv video 节点 → AI 视频生成全流程 |
| **project-coordinator** | 项目创建/阶段推进/产物追踪/打包归档/注销 |
| **cadstack** | CAD 自动化：自然语言→FreeCAD/AutoCAD/SolidWorks/Fusion 360 脚本 |
| **docx** | Word 文档创建、编辑、格式排版 |
| **pdf** | PDF 读取、合并、拆分、OCR、表单、水印 |
| **gpt-image-2-prompt-studio** | 775+ GPT Image 2 高质量 Prompt 模板库，7 类视觉场景 |
| **libtv-cli** | LibTV 画布 CLI 完整命令手册 |
| **cross-platform-adapter** | Windows/Unix 跨平台脚本兼容（路径、编码、临时文件） |
| **bom-fixer** | UTF-8 BOM 检测去除、GBK 乱码修复 |
| **skill-creator** | 技能创建/迭代/评测/benchmark |

## MCP 服务器

### GRSAI Server（唯一 MCP 服务器）
- **协议**：FastMCP 标准范式
- **能力**：LLM 对话 + 图像生成（`gpt-image-2` 等模型）
- **架构**：`server.py` → `grsai_client.py`（API 调用）+ `cos_client.py`（腾讯云 COS 持久化）
- **启动**：通过 `.venv/Scripts/python.exe` 直接调用，避免中间层超时问题
- **工作流**：`submit`（提交任务）→ `poll`（轮询结果，最长 300s）→ `download`（本地保存+OSS 上传）

## 图像生成 Schema

所有图像生成任务遵循统一 JSON Schema（`image-generation.json`）：

```json
{
  "tasks": [
    {
      "prompt": "提示词（必填）",
      "model": "gpt-image-2",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "filename": "output.png",
      "images": ["参考图URL"]
    }
  ],
  "model": "gpt-image-2",
  "output_path": "./output",
  "oss_path": "project/xxx/reference/"
}
```

## 快速开始

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建虚拟环境并安装依赖
uv sync

# 3. 配置 credentials
#    将 credentials.json 放入 .opencode/mcp-servers/grsai-server/

# 4. 重启 opencode 使 MCP 配置生效
opencode
```

## 环境要求

| 项目 | 值 |
|------|-----|
| Python | 3.13.11（uv 管理） |
| OS | Windows / macOS / Linux |
| Shell | PowerShell 7+（Windows）/ bash（Unix） |
| 关键依赖 | Pillow, pypdf, pdfplumber, python-docx, cadquery, ezdxf, matplotlib, mcp |
| 图像平台 | GRSAI（需 API Key） |
| 视频平台 | LibTV（需 API Key） |
| OSS | 腾讯云 COS（可选，用于持久化存储） |

## 编码规范

- **中文推理与对话**：所有 Agent 使用中文
- **PowerShell UTF-8**：所有文件读写显式指定 `-Encoding UTF8`
- **白名单 .gitignore**：仅跟踪 README.md、AGENTS.md、opencode.json、`.opencode/`、`doc/`
- **禁止删除**：`temp/` 下任何文件
- **配置只读**：`.opencode/` 仅通过 skill-engineer 修改

## Git 分支策略

- `main` — 稳定分支
- `refactor/agent-config` — 当前开发分支
- `merge-local-refactor` — 本地合并分支

## 经验参考

`doc/` 目录记录了项目实战经验，包含管线流程优化、角色设定管理、画风统一、图像生成实践、分镜生成经验、Agent 协作模式等关键教训。

## 许可

MIT
