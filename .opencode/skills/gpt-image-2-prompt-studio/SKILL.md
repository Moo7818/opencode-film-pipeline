---
name: gpt-image-2-prompt-studio
description: >
  GPT Image 2 提示词工作室 — 基于 awesome-gpt-image-2-API-and-Prompts 仓库
  （16.6k stars）的 775+ 条高质量 Prompt 模板库，覆盖 7 种视觉类别
  （海报/角色/人像/UI/电商/广告/对比），支持 11 种语言、{argument}
  参数化模板、批量任务表生成。
  当用户提到以下内容时务必触发此 skill：GPT Image 2 / gpt-image-2 的
  提示词或案例或模板或画廊、awesome-gpt-image-2 仓库、prompt 模板库、
  需要参考案例生成图像、想用现成的 prompt 出图、提到底层模型是
  gpt-image-2 的任何图像生成需求、搜索/浏览 prompt 案例、
  说"从那堆模板里找一个"或"参考那个案例"。即使是"用 GPT Image 2
  随便生成一张"也应加载以推荐合适模板。不限于以上列举。
---

# GPT Image 2 提示词工作室

本 skill 桥接 [awesome-gpt-image-2-API-and-Prompts](https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts) 仓库（775+ 条 GPT-Image-2 高质量 Prompt）与 art-director 生图管线。提供仓库管理、模板搜索、参数化替换、任务表生成全流程。

## 核心原则

1.  **按需读取，不预加载** — 仓库中单个 `.md` 文件可达 500KB。通过轻量 `catalog.json` 索引定位后，用 Read 工具精确读取目标段落。
2.  **LLM 理解 Prompt 内容** — 不依赖正则解析 Prompt 文本。索引只存元数据（标题、类别、语言、行号范围），具体 Prompt 由 LLM 从源 Markdown 直接读取并理解。
3.  **与 art-director 协作** — 本 skill 只负责输出 JSON 任务表。实际生成图像时调用 art-director skill 的 `batch_generator.py`。

## 前置条件

- `awesome-gpt-image-2-API-and-Prompts` 仓库已克隆到本地
- `catalog.json` 索引已构建（构建过一次后只需在仓库更新后重建）
- Python 3.10+（与项目 uv/.venv 一致）

## 仓库路径约定

脚本默认在以下位置查找仓库：

```
{skill_base_dir}/../../temp/awesome-gpt-image-2-API-and-Prompts/
```

可通过以下方式覆盖：

```bash
# 环境变量
$env:REPO_PATH = "D:\path\to\repo"

# 或直接在脚本命令行传 --repo-path
```

## 工作流程

### 1. 仓库管理

首次使用或需要更新时运行：

```powershell
# 克隆（首次）
python {scripts_dir}/sync_repo.py

# 更新到最新
python {scripts_dir}/sync_repo.py --update
```

> 仓库不会自动更新。当你发现案例数量明显落后于仓库主页（16.6k stars）时，提示用户手动更新。

### 2. 构建/更新索引

仓库同步后需重建索引。首次和每次更新后执行：

```powershell
python {scripts_dir}/build_index.py --repo-path <repo_path>
```

这会扫描 `cases/` 下所有 `.md` 文件，提取元数据到 `references/catalog.json`。

> **🚫 禁止直接读取 `catalog.json`**——该文件体积大（48KB+），全量加载会浪费大量上下文。Agent 只能通过 CLI 命令查询。

### 3. 搜索与浏览

必须通过 `build_index.py` 的 CLI 查询命令搜索，**禁止直接 Read `catalog.json`**。

**索引概览（唯一允许内联的摘要，仅统计信息）：**

| 类别 | 中文名 | EN 数量 | 总数(含多语言) | 含参数模板 |
|------|--------|---------|---------------|-----------|
| `poster` | 海报与插画 | 220 | 1200 | 20 |
| `portrait` | 人像与摄影 | 172 | 1152 | 18 |
| `character` | 角色设计 | 15 | 15 | 4 |
| `ui` | UI 与界面 | 99 | 504 | 23 |
| `ecommerce` | 电商 | 28 | 103 | 12 |
| `ad-creative` | 广告创意 | 31 | 181 | 15 |
| `comparison` | 对比与社区 | 72 | 302 | 4 |

> 以上数据来自最后一次构建时的 catalog.json 统计，仅用于让 Agent 判断哪个类别可能有用户需要的结果。具体搜索必须走 CLI。

**CLI 查询命令（禁止直接 Read catalog.json）：**

```powershell
# 只看统计信息（推荐先看这个了解整体分布）
python {scripts_dir}/build_index.py --stats

# 列出某个类别的所有案例（返回 case_id + 标题）
python {scripts_dir}/build_index.py --list-category poster --lang en

# 按关键词搜索标题
python {scripts_dir}/build_index.py --search "film" --category portrait --lang en
```

**搜索顺序（禁止直接 Read catalog.json）：**

1. 先用 `--stats` 了解整体分布
2. 用 `--search` 在索引中按关键词匹配标题
3. 若用户指定了语言但该语言版本不在索引中，自动回退到英文
4. 向用户展示匹配的 case 列表（case_id + 标题 + 有无参数）
5. 根据匹配的 `file` + `line_range`，用 Read 精确读取对应 `.md` 文件的**少量行**（offset + limit 指向具体 case）

### 4. 读取完整 Prompt

用户选定一个 case 后，使用 Read 工具从对应 `.md` 文件的 `line_range` 读取内容。例如：

```powershell
Read filePath="<repo_path>/cases/poster.md" offset=145 limit=30
```

或者调用 parse_prompt.py：

```powershell
python {scripts_dir}/parse_prompt.py --repo-path <repo_path> --case poster_case42 --lang zh-CN
```

从读取的内容中理解 Prompt 文本，注意该仓库的 Prompt 有以下常见变体：

| 变体 | 说明 | 处理方式 |
|------|------|----------|
| **纯文本** | 英文/中文/日文自然语言描述 | 直接使用 |
| **`{argument}` 参数** | `{argument name="x" default="y"}` 模板标记 | 询问用户参数值，或用默认值替换 |
| **多 Prompt** | `Prompt 1:` / `Prompt 2:` | 询问用户需要哪个，或全部保留 |
| **`--ar` 标志** | `--ar 9:16` 等宽高比 | 提取宽高比，转为 `aspectRatio` 字段 |
| **JSON 结构** | 少数 case 含 JSON 格式提示 | 保持 JSON 完整性，作为单条 prompt |

### 5. 参数化模板处理

当用户选中的 case 包含 `{argument name=... default=...}` 语法时：

1. 用 Python 或字符串匹配提取所有参数名和默认值
2. 向用户逐一询问替换值（或接受用户提前传入的 `--set` 值）
3. 未提供的参数使用默认值
4. 输出替换后的完整 Prompt

**示例：**
```
原始: "Create a {argument name="city" default="Boston"} poster..."
替换: "Create a Guangzhou poster..."
```

### 6. 生成任务表

生成 art-director 兼容的 JSON 任务表：

```json
[
  {
    "prompt": "（完整的参数替换后的 Prompt）",
    "model": "gpt-image-2",
    "aspectRatio": "2160x3840"
  }
]
```

aspectRatio 使用像素格式（如 `"1024x1024"`、`"2160x3840"`）。从 Prompt 内容或用户要求推断宽高比：
- 若 Prompt 含 `--ar 9:16` 等标志，按模型配置映射
- 若用户指定了尺寸（如"竖版"、"横版"），选择合适的比例
- 默认 `"1024x1024"`（1:1）

### 7. 交给 art-director 执行

任务表生成后，使用 art-director skill 执行批量生图：

```bash
python {art_dir}/script/batch_generator.py \
  --tasks tasks.json \
  --model gpt-image-2 \
  --output-dir "中间产物/提示词画廊" \
  --project-dir "你的项目路径"
```

> **注意**：不要自己调用 API。art-director 的 `batch_generator.py` 会处理并发提交、轮询、下载、日志等。本 skill 只生产任务表 JSON。

### 8. 常见用户需求模式

| 用户说 | 你的做法 |
|--------|----------|
| "找一些 xxx 风格的模板" | 搜索 catalog，列出匹配结果 |
| "用那个 xxx 案例生成一张" | 读取对应 case 的 Prompt，填参数，生成任务表，调用 art-director |
| "帮我看看有什么海报模板" | 列出 poster 类别的案例标题列表 |
| "这个模板的参数帮我填一下" | 提取 {argument} 列表，交互式询问并替换 |
| "批量生成 5 个人像案例" | 从 portrait 分类选 5 个，逐一处理参数，合并到一张任务表 |
| "仓库更新了，重建索引" | 运行 sync_repo.py --update 然后 build_index.py |

## 目录结构参考

```
{skill_base_dir}/
├── SKILL.md                    ← 本文件
├── scripts/
│   ├── sync_repo.py            ← 仓库克隆/更新（手动调用）
│   ├── build_index.py          ← 构建 catalog.json 索引
│   └── parse_prompt.py         ← 按需读取 Prompt + 参数替换
└── references/
    └── catalog.json            ← 构建后的索引缓存（运行时生成）
```

可用 `{scripts_dir}` 表示 `{skill_base_dir}/scripts/`。

## 设计原理

- **为什么索引只存元数据？** cases/ 目录中单个 .md 文件可达 500KB（如 poster.md）。将所有 Prompt 文本编入索引会导致 catalog.json 膨胀到数十 MB。索引只存 case_id、行号范围、标题等轻量字段，具体 Prompt 按需读取。
- **为什么不用正则解析 Prompt？** 仓库实际包含 5 种以上的 Prompt 格式变体（纯文本、中文、日文、多 Prompt 编号、JSON 结构）。正则覆盖全部变体既脆弱又难以维护。LLM 直接理解内容更可靠。
- **为什么分两步（选模板 → 执行生图）？** 模板选择和参数填充需要用户交互确认。分开执行让用户在每个环节都有控制权，避免一次性生成不符合预期的结果。
