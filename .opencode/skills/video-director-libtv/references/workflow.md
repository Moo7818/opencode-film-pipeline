# 工作流详细执行步骤

## 步骤 1：读取上下文

| 参数 | 来源 | 说明 |
|------|------|------|
| 项目根路径 | 由 Coordinator 传入 | `project/<项目名>/` |
| 剧集号 | 由 Coordinator 传入 | 如 `EP01`、`01` |
| 分镜分组路径 | `{项目根}/{剧集号}/分镜/分组/` | 包含 `组1.json` ~ `组{N}.json` 或 `组1.md` ~ `组{N}.md` |
| project_config.json | `.meta/projects/{uuid}/project_config.json` | 全局视频参数（字段定义见 `.opencode/schemas/project-config.json`） |

**分组文件格式**：支持两种格式：
- **JSON 格式**（`组{N}.json`）：结构化数据，原样拷贝完整 JSON 内容到 prompt
- **MD 格式**（`组{N}.md`）：Markdown 格式的分镜脚本，读取 MD 文件的全部内容作为视频生成提示词

读取分组文件时，优先查找 JSON 格式，如不存在则查找 MD 格式。两种格式不可混用。

## 步骤 2a：创建/切换到项目工作区（workspace）

每个项目应有独立的 libtv workspace。首次运行时需创建工作区，后续运行时切换到已有工作区：

```bash
# 检查是否已有项目的工作区（从 project_config.json 或 .libtv/project.json 读取 workspaceId）
# 如果没有，创建一个新的工作区
libtv workspace create "{项目名}"

# 切换到工作区（写入 .libtv/project.json 的 workspaceId）
libtv workspace use <workspaceId>
```

> **说明**：`libtv workspace create` 会创建新工作区并返回 workspaceId。创建后需执行 `libtv workspace use` 完成绑定。

## 步骤 2b：创建/绑定画布（canvas）

如果 `project_config.json` 的 `canvas_uuid` 为空，视频导演需要在当前 workspace 下创建新画布：

```bash
# 在当前工作区下创建画布
# 画布名称建议格式：{项目名}_{剧集号}
libtv project create "画布名称" --ratio 9:16
```

创建画布后，从输出中获取画布 UUID，绑定并写入配置：

```bash
# 读取新创建的画布 UUID
$canvasUuid = (Get-Content -Encoding UTF8 -Raw ".libtv/project.json" | ConvertFrom-Json).projectUuid

# 绑定画布（v1.1.1+ 还会同步写入画布所属的 workspaceId + teamId）
libtv project use $canvasUuid

# 将 UUID 写入 project_config.json
$configPath = ".meta/projects/{uuid}/project_config.json"
$config = Get-Content -Encoding UTF8 -Raw $configPath | ConvertFrom-Json
$config.canvas_uuid = $canvasUuid
$config | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $configPath
```

如果 `canvas_uuid` 已存在，直接使用 `libtv project use <canvas_uuid>` 绑定。

## 步骤 3：上传参考素材为画布资源节点

脚本 `scan_project_refs` 扫描全局依赖目录，**仅上传 `--refs` 中实际指定的**角色/场景/道具/风格参考图到画布（复用检测，已存在的不重复上传）。未在 `--refs` 中指定的素材**不会上传**，避免无关素材占用画布。参考图的**选取与连线由 Agent 在步骤 4 通过 `--refs` 显式指定**。

> **`use_storyboard_images` 不影响上传**：该字段仅作为 Agent 选取参考图时的优先级参考（详见 `storyboard-to-libtv.md` §6.1），不改变脚本的上传行为。

### ⛔ 选角参考图禁令

**视频生成绝对不能使用选角参考图**（`{角色名}_选角.png`）。选角资产是 Tier 1 资产（白T恤+灰背景），仅用于角色面部特征确立。脚本 `scan_project_refs` 已自动过滤 `_选角.png` 文件，不会上传到画布。Agent 在手动指定 `--refs` 时也必须确保不引用选角资产，应使用 Tier 2 妆造资产（`{角色名}_默认.png` 或 `{角色名}_{妆造名}.png`）。

```bash
libtv upload "<素材显示名>" -t image -f "<本地绝对路径>"
```

**命名规则**：`{素材类型}_{名称}`，如 `角色_掌柜`、`场景_茶馆`、`分镜_组1`。

**音色参考上传**（由 Agent 通过 `--voice-refs` 显式控制）：
脚本**仅上传 `--voice-refs` 中指定的角色**音色文件，不做自动全量扫描。未指定 `--voice-refs` 时跳过音色参考上传。

文件命名支持两种模式（自动识别）：
- `{角色名}-音色参考.{ext}`（如 `吉小泰-音色参考.wav`）
- `{角色名}音色.{ext}`（如 `掌柜音色.wav`、`皇帝音色.mp3`）

支持的音频格式：`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`

```bash
libtv upload "音色_吉小泰" -t audio -f "project/{项目名}/全局依赖/音色参考/吉小泰-音色参考.wav"
```
上传命名规则：`音色_{角色名}`（如 `音色_吉小泰`、`音色_掌柜`）。

上传后的音色参考节点通过 `--left 音色_{角色名}` 连线到对应 video 节点。音色参考属于 audio 类型素材，使用 `{{Audio N}}` 在 prompt 中引用，其中 `N` 为 `--left` 中 audio 节点的排列序号（从 1 开始）。所有 image 节点在前、audio 节点在后排列 `--left` 参数，确保 `{{Image N}}` 和 `{{Audio N}}` 编号互不干扰。

## 步骤 4：创建 video 节点（两种方式）

### 4.1 字段映射

| JSON 字段 | 映射目标 | 说明 |
|-----------|----------|------|
| `组号` | node displayName | 如 `组1` |
| `组时长` | `--set duration` | 组的时长（秒） |

### 4.2 Prompt 格式

有参考图时，参考以下格式拼接 prompt：

引用行示例：`吉小泰角色参考{{Image 1}}、现代家庭客厅场景参考{{Image 2}}`

**JSON 格式分组**的实际 prompt 结构：
```
{引用行（可选，格式为"xx参考{{Image N}}"）}

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```

**MD 格式分组**的实际 prompt 结构：
```
{引用行（可选，格式为"xx参考{{Image N}}"）}

画面严禁出现任何字幕，无配乐
---
{完整的组 MD 文件内容，读取全部内容，严禁修改}
```

> 引用行格式统一为 `{名称}{类型}参考{{Image N}}`，如 `掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}`。分镜图特殊处理：`分镜图仅作辅助参考（光影、色调）{{Image N}}`，且当引用中包含分镜图时，追加 `具体细节以角色/场景/道具参考图为准`。

无参考图时跳过引用行和空行。

### 4.3 `{{Image N}}` 编号规则

`--left` 顺序决定 `{{Image N}}` 编号的基础规则不变。**v1.1.1+ 变化**：

- **`--left`/`--right` 改为 ensure 模式**：只确保列出的节点已连线，**不会删除**已在画布上但未列出的边
- 需要增删已有连线时，使用 `--left-add <节点>` / `--left-rm <节点>`（增量追加/移除）
- `--prompt` 写入不会重算 `imageList`，可以安全地在创建后更新 prompt

### 4.3.1 `{{Audio N}}` 编号规则（v1.1.1+）

audio 类型节点的 `{{Audio N}}` 编号规则：

1. `--left` 中 audio 节点的排列顺序决定 `{{Audio N}}` 编号，第一个 audio 节点 → `{{Audio 1}}`
2. `{{Audio N}}` 与 `{{Image N}}` 是独立的编号体系，互不影响
3. 推荐将所有 image 节点排在 `--left` 前面、所有 audio 节点排在后面，使两类编号都清晰可读
4. 在 prompt 中使用 `{{Audio 1}}` 引用第一个音色参考

示例 prompt：
```
掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}，掌柜音色参考{{Audio 1}}
```

### 4.4 `{{Node "..."}}` prompt 占位符（v1.1.1+）

v1.1.1+ 支持 `{{Node "节点名"}}` 语法替代 `{{Image N}}`，直接在 prompt 中按**节点展示名**引用已连线上游节点，无需关心 Image N 的实际编号：

```bash
# 用 {{Node "节点名"}} 替代 {{Image N}}
libtv node "组1" --prompt "场景参考{{Node \"场景参考_01\"}}、角色参考{{Node \"角色参考_01\"}}"
```

当画布内节点名唯一时推荐使用，更直观可控。如遇重名，可先用 `libtv node <名>` 查询其 `nodeKey`，再用 `{{Node <nodeKey>}}` 精确锚定。

### 4.5 方式一：一次性创建

直接在 `create` 命令中写入含引用行的完整 prompt。**必须使用临时 Python 脚本**传递 prompt（避免引号嵌套和长度限制，跨平台通用）：

```python
# temp/create_group1.py
#!/usr/bin/env python3
import os
import subprocess
import sys

os.environ["LIBTV_CONFIG_DIR"] = os.path.abspath(".opencode/credentials")

prompt = """场景参考{{Image 1}}、角色参考{{Image 2}}

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝}
"""

cmd = [
    "libtv", "node", "create", "组1", "-t", "video",
    "--prompt", prompt,
    "--set", "model=Seedance 2.0 VIP",
    "--set", "modeType=mixed2video",
    "--set", "count=1",
    "--set", "ratio=16:9",
    "--set", "duration=5",
    "--set", "enableSound=on",
    "--left", "场景参考_01", "--left", "角色参考_01",
    "--left", "音色_吉小泰",  # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
]

result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(1)
```

执行命令（跨平台一致）：
```bash
python3 temp/create_group1.py
```

### 4.6 方式二：两阶段（推荐）

需要验证顺序后再写引用时使用。

**阶段 1** — 创建节点（占位 prompt + `--left` 连线）：

```bash
libtv node create "组1" -t video \
  --prompt "画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP \
  --set modeType=mixed2video \
  --set count=1 \
  --set ratio=16:9 \
  --set duration=5 \
  --set enableSound=on \
  --left 场景参考_01 --left 角色参考_01 --left 道具参考_01 \
  --left 音色_吉小泰   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

**阶段 2** — 查询 `imageList` 后 `--prompt` 写入引用行：

```bash
# 查询节点，确认 imageList 顺序
libtv node "组1"

# 根据 imageList 顺序写入引用行（--prompt 不会重算顺序）
libtv node "组1" --prompt "场景参考{{Image 1}}、角色参考{{Image 2}}、道具参考{{Image 3}}

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}"
```

### 4.7 重要约束

- **创建到运行之间不要打开 Web UI 查看画布**，否则会触发服务端重排
- `--prompt` 写入不会触发重算，两阶段安全
- **不对 JSON 内容做任何修改、缩写、重排或格式化**
- 分镜组 JSON 原样拷贝到 prompt 中

## 步骤 5：[可选] 批量建组

```bash
libtv group create "<剧集号>视频组" --node <组1> --node <组2>
```

**默认行为**：仅执行建组操作，不自动运行视频生成。

**跳过建组**：使用 `--no-group` 参数可跳过建组步骤，仅创建独立节点。适用于需要手动编排节点或在画布中自行分组的场景。注意：`--no-group` 与 `--run` 不兼容（未建组无法通过 `group --run` 运行）。

## 步骤 6：[可选] 运行视频生成

**仅当用户明确要求时**才执行以下命令：

```bash
libtv group "<剧集号>视频组" --run
```

**v1.1.1+ 行为变化**：`group --run` 现在是**阻塞等待命令**，CLI 内部会提交任务、轮询进度，并在全部节点完成后输出终态 JSON 到 stdout 后退出。stderr 约每 3 分钟输出一条 `[run-group]` 进度日志。

外部脚本 / agent **直接等待该命令退出**，不要后台运行、不要加超时、不要额外轮询。

**用户触发方式**：
- 用户说"运行"、"执行"、"生成视频"等 → 执行 `group --run`
- 用户说"只建组"、"不要运行"、"先不执行" → 仅完成步骤5建组，跳过本步骤
- 默认情况（用户未明确说明） → 仅完成步骤5建组，跳过本步骤

## 步骤 7：轮询等待生成完成

> **v1.1.1+**：如果步骤 6 使用了 `--run`，步骤 7 可以跳过——`group --run` 已阻塞等待完成。需单独查询结果时：

```bash
libtv node "<组名>"
```

输出中包含 `data.url`（视频 URL）和 `data.results`（生成结果列表）。

## 步骤 8：报告 Coordinator 归档

```json
{
  "status": "success",
  "nodes": [
    {
      "displayName": "组1",
      "videoUrl": "https://...",
      "duration": 5
    }
  ],
  "totalGroups": 5,
  "视频组名": "EP01视频组"
}
```
