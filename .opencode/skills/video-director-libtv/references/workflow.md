# 工作流详细执行步骤

## 步骤 1：读取上下文

| 参数 | 来源 | 说明 |
|------|------|------|
| 项目根路径 | 由 Coordinator 传入 | `project/<项目名>/` |
| 剧集号 | 由 Coordinator 传入 | 如 `EP01`、`01` |
| 分镜分组路径 | `{项目根}/{剧集号}/分镜/分组/` | 包含 `组1.json` ~ `组{N}.json` |
| project_config.json | `.meta/projects/{uuid}/project_config.json` | 全局视频参数（字段定义见 `.opencode/schemas/project-config.json`） |

## 步骤 2：绑定画布并写入 canvas_uuid

如果 `project_config.json` 的 `canvas_uuid` 为空，视频导演首次运行时需读取 `.libtv/project.json` 获取 UUID，绑定后写回配置：

```bash
# 从 .libtv/project.json 读取画布 UUID
$canvasUuid = (Get-Content -Encoding UTF8 -Raw ".libtv/project.json" | ConvertFrom-Json).projectUuid

# 绑定画布（v1.1.1+ 还会同步写入画布所属的 workspaceId + teamId）
libtv project use $canvasUuid

# 将 UUID 写入 project_config.json
$configPath = ".meta/projects/{uuid}/project_config.json"
$config = Get-Content -Encoding UTF8 -Raw $configPath | ConvertFrom-Json
$config.canvas_uuid = $canvasUuid
$config | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $configPath
```

## 步骤 3：上传参考素材为画布资源节点

根据 `project_config.json` 的 `use_storyboard_images` 决定素材上传优先级：

- **`true`**：优先上传本组分镜图，再传角色/道具/场景参考图
- **`false`**：按角色 > 场景 > 道具 > 风格顺序上传

```bash
libtv upload "<素材显示名>" -t image -f "<本地绝对路径>"
```

**命名规则**：`{素材类型}_{序号}`，如 `角色参考_01`、`分镜图_组1`。

## 步骤 4：创建 video 节点（两种方式）

### 4.1 字段映射

| JSON 字段 | 映射目标 | 说明 |
|-----------|----------|------|
| `组号` | node displayName | 如 `组1` |
| `组时长` | `--set duration` | 组的时长（秒） |

### 4.2 Prompt 格式

有参考图时：
```
请参考{自然描述}{{Image 1}}、{自然描述}{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}

自然描述根据参考图文件名而定，如 `一岛角色相貌参考{{Image 1}}、现代南京长江边场景参考{{Image 2}}`
```

无参考图时跳过引用行和空行。

### 4.3 `{{Image N}}` 编号规则

`--left` 顺序决定 `{{Image N}}` 编号的基础规则不变。**v1.1.1+ 变化**：

- **`--left`/`--right` 改为 ensure 模式**：只确保列出的节点已连线，**不会删除**已在画布上但未列出的边
- 需要增删已有连线时，使用 `--left-add <节点>` / `--left-rm <节点>`（增量追加/移除）
- `--prompt` 写入不会重算 `imageList`，可以安全地在创建后更新 prompt

### 4.4 `{{Node "..."}}` prompt 占位符（v1.1.1+）

v1.1.1+ 支持 `{{Node "节点名"}}` 语法替代 `{{Image N}}`，直接在 prompt 中按**节点展示名**引用已连线上游节点，无需关心 Image N 的实际编号：

```bash
# 用 {{Node "节点名"}} 替代 {{Image N}}
libtv node "组1" --prompt "请参考场景氛围{{Node \"场景参考_01\"}}和角色形象{{Node \"角色参考_01\"}}进行画面生成"
```

当画布内节点名唯一时推荐使用，更直观可控。如遇重名，可先用 `libtv node <名>` 查询其 `nodeKey`，再用 `{{Node <nodeKey>}}` 精确锚定。

### 4.5 方式一：一次性创建

直接在 `create` 命令中写入含引用行的完整 prompt：

```bash
libtv node create "组1" -t video \
  --prompt "请参考场景氛围{{Image 1}}和角色形象{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容}" \
  --set model=Seedance 2.0 VIP \
  --set modeType=mixed2video \
  --set count=1 \
  --set ratio=16:9 \
  --set duration=5 \
  --set enableSound=on \
  --left 场景参考_01 --left 角色参考_01
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
  --left 场景参考_01 --left 角色参考_01 --left 道具参考_01
```

**阶段 2** — 查询 `imageList` 后 `--prompt` 写入引用行：

```bash
# 查询节点，确认 imageList 顺序
libtv node "组1"

# 根据 imageList 顺序写入引用行（--prompt 不会重算顺序）
libtv node "组1" --prompt "请参考场景氛围{{Image 1}}、角色形象{{Image 2}}和道具样式{{Image 3}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}"
```

### 4.7 重要约束

- **创建到运行之间不要打开 Web UI 查看画布**，否则会触发服务端重排
- `--prompt` 写入不会触发重算，两阶段安全
- **不对 JSON 内容做任何修改、缩写、重排或格式化**
- 分镜组 JSON 原样拷贝到 prompt 中

## 步骤 5：批量分组运行

```bash
libtv group create "<剧集号>视频组" --node <组1> --node <组2>
libtv group "<剧集号>视频组" --run
```

**v1.1.1+ 行为变化**：`group --run` 现在是**阻塞等待命令**，CLI 内部会提交任务、轮询进度，并在全部节点完成后输出终态 JSON 到 stdout 后退出。stderr 约每 3 分钟输出一条 `[run-group]` 进度日志。

外部脚本 / agent **直接等待该命令退出**，不要后台运行、不要加超时、不要额外轮询。

## 步骤 6：轮询等待生成完成

> **v1.1.1+**：如果步骤 5 使用了 `--run`，步骤 6 可以跳过——`group --run` 已阻塞等待完成。需单独查询结果时：

```bash
libtv node "<组名>"
```

输出中包含 `data.url`（视频 URL）和 `data.results`（生成结果列表）。

## 步骤 7：报告 Coordinator 归档

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
