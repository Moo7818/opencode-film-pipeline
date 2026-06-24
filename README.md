# opencode-film-pipeline

基于 OpenCode AI Agent 框架的影视/动画制作管线工作区。集成监制（Producer）、编剧（Script Writer）、分镜导演（Storyboard Director）、美术指导（Art Director）、视频导演（Video Director）等 AI Agent，覆盖从剧本解析到成片输出的全流程。

## 目录结构

```
.opencode/          # OpenCode 配置（只读）— skills / MCP servers / rules / schemas
project/            # 业务项目目录 — 每个子目录代表一个独立客户/业务线
doc/                # 项目文档与经验总结
temp/               # 临时文件（禁止删除）
```

## 核心技能

| Skill | 职责 |
|-------|------|
| Producer | 剧本解析，提取角色/场景/道具设定，生成分集剧本 |
| Script Writer | 剧本创作与润色 |
| Storyboard Generator | 分镜脚本拆解，生成结构化分镜任务 |
| Art Director | 角色/场景/道具参考图及分镜图生成（GRSAI） |
| Video Director | 分镜视频化与 AI 视频生成（libtv） |
| Project Coordinator | 项目生命周期管理与产物追踪 |

## 快速开始

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv sync

# 启动 OpenCode
opencode
```

## 依赖

- Python 3.13.11（uv 管理）
- CAD 处理：cadquery, ezdxf
- 文档处理：python-docx, pypdf, pdfplumber
- 图像处理：Pillow, matplotlib
- MCP 协议支持

## 许可

MIT
