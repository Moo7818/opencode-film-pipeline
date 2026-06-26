# MCP 服务器管理框架

## 核心理念

所有工具统一以 **MCP 服务器** 形式接入系统。系统只需要补足两个管理能力：

1. **虚拟环境管理** — 每个 MCP 服务器可拥有独立 `.venv`
2. **模型/大文件管理** — 统一存储位置，支持配置外置盘

## 目录结构

```
.opencode/
├── mcp-servers/              # MCP 服务器（自包含：代码 + 虚拟环境）
│   ├── grsai-server/         #   自研：图像生成
│   │   ├── server.py
│   │   ├── .venv/            #     本服务器的虚拟环境
│   │   └── credentials.json
│   │
│   ├── indextts-2/           #   第三方：语音合成
│   │   ├── server.py         #     FastMCP 封装层（薄）
│   │   ├── requirements.txt  #     该服务器独有的依赖
│   │   ├── .venv/            #     本服务器的虚拟环境
│   │   └── .env              #     配置（模型路径等）
│   │
│   └── ...                   #   更多 MCP 服务器（每个自带 .venv/）
│
├── mcp-storage/              # ← 模型/大文件（不入 git，可配置外置盘）
│   ├── indextts-2/
│   │   └── checkpoints/      #     ~9 GB
│   └── ...
│
└── scripts/
    └── mcp/                  # 管理脚本
        ├── install.ps1       #   安装：创建 venv + 装依赖 + 下载模型
        ├── list.ps1          #   列出所有服务器
        └── remove.ps1        #   卸载
```

## 管理操作

### 安装一个 MCP 服务器

```powershell
.opencode/scripts/mcp/install.ps1 -Name indextts-2 `
    -Source D:\IndexTTS-2-Demo `
    -Requirements .opencode/mcp-servers/indextts-2/requirements.txt `
    -Models @{ "checkpoints" = "https://modelscope.cn/..." }
```

做的事情：
1. 在 `.opencode/mcp-servers/indextts-2/.venv/` 创建虚拟环境
2. 安装依赖
3. 下载模型到 `.opencode/mcp-storage/indextts-2/`
4. 生成 `.opencode/mcp-servers/indextts-2/.env`

### 注册到 opencode.json

```json
{
  "mcp": {
    "indextts-2": {
      "type": "local",
      "command": [
        ".opencode/mcp-servers/indextts-2/.venv/Scripts/python.exe",
        ".opencode/mcp-servers/indextts-2/server.py"
      ],
      "env": {
        "MODEL_DIR": ".opencode/mcp-storage/indextts-2"
      }
    }
  }
}
```

### 模型存储配置

`mcp-storage/` 的路径可通过符号链接或环境变量指向外置盘：

```powershell
# 方式 1：符号链接
New-Item -ItemType SymbolicLink -Path .opencode/mcp-storage `
    -Target D:\model-storage

# 方式 2：环境变量
$env:MCP_STORAGE_ROOT = "D:\model-storage"
```

## IndexTTS-2 落地步骤

### 1. 创建 MCP 封装

`.opencode/mcp-servers/indextts-2/server.py`：

```python
from mcp.server.fastmcp import FastMCP
from indextts.infer_v2 import IndexTTS2
import os

mcp = FastMCP("indextts-2")

model_dir = os.getenv("MODEL_DIR", "checkpoints")
tts = IndexTTS2(
    model_dir=model_dir,
    cfg_path=os.path.join(model_dir, "config.yaml"),
)

@mcp.tool()
def tts_synthesize(text: str, voice_ref: str, output_path: str) -> str:
    """文本转语音"""
    return tts.infer(
        spk_audio_prompt=voice_ref,
        text=text,
        output_path=output_path,
    )

mcp.run()
```

### 2. 安装

```powershell
# 进入服务器目录创建虚拟环境
cd .opencode/mcp-servers/indextts-2
uv venv

# 安装依赖
.venv/Scripts/pip install -r requirements.txt

# 下载模型（通过管理脚本）
.opencode/scripts/mcp/install.ps1 indextts-2
```

### 3. 在 opencode.json 中注册

添加到现有 `mcp` 段即可。

## 与现有系统的关系

| 现有元素 | 变化 |
|----------|------|
| `.opencode/mcp-servers/grsai-server/` | 不变，它已经是 MCP 服务器 |
| `opencode.json` 的 `mcp` 段 | 直接追加新服务器 |
| `tools/` 目录 | 不再需要（方案简化后废除） |
| `AGENTS.md` 中 `.opencode/` 只读规则 | 脚本层面需将 `.opencode/mcp-servers/*/.venv/` 和 `.opencode/mcp-storage/` 加入 `.gitignore`，明确为可写区域 |
