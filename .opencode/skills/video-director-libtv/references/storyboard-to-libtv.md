# 映射规则：分镜组 JSON → libtv video node

## 0. 参数来源总览

| 来源文件 | 路径 | 提供什么 |
|----------|------|----------|
| `project_config.json` | `.meta/projects/{uuid}/project_config.json` | 全局视频参数（比例、模型、模式等） |
| 分组/组{N}.json | `project/<项目名>/<剧集号>/分镜/分组/组{N}.json` | 本组生成参数（时长、分镜内容） |

字段定义以 `.opencode/schemas/project-config.json` 为唯一来源。

---

## 1. 字段对应表

| 分镜组 JSON 字段 | libtv 参数 | 说明 |
|------------------|------------|------|
| `组号` | node displayName | 如 `组1` |
| `组时长` | `--set duration=<秒>` | 需转为整数 |

| project_config.json 字段 | libtv 参数 | 说明 |
|--------------------------|-----------|------|
| `aspect_ratio` | `--set ratio=<值>` | 如 `16:9` |
| `resolution` | `--set resolution=<值>` | 映射为 `480p` / `720p` |
| `model` | `--set model=<值>` | 视频模型 modelName（中文名，如 `Seedance 2.0 VIP`）；libtv 1.1.1+ 直接使用该字段值作为 modelName，**不做 modelKey → modelName 转换**。**禁止填 modelKey**（如 `kling-v3-omni`、`star-video2`），读取后直接用作 `--set model` 的值 |
| `mode` | `--set modeType=<值>` | 生成模式，如 `mixed2video`、`text2video` |
| `enable_sound` | `--set enableSound=on/off` | `true` → `on`，`false` → `off` |
| — | `--set scene=<值>` | v1.1.1+ 模型 schema 可选业务场景字段，由 `libtv model <modelKey>` 决定

---

## 2. Prompt 组装规则

**严禁修改原始分镜组 JSON 内容。**

### 2.1 有参考图时

```
{引用行，由视频导演根据素材自行编写，如"请参考角色相貌{{Image 1}}和场景{{Image 2}}进行画面生成"}

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```
自然描述根据参考图文件名语义生成，如 `一岛角色相貌参考{{Image 1}}、现代南京长江边场景参考{{Image 2}}`

### 2.1.1 有音色参考时

当音色参考节点连入 video 节点时，可在 prompt 末尾追加音色引用行。引用措辞由视频导演自行编写，例如：

```
请参考角色形象{{Image 1}}和场景氛围{{Image 2}}进行画面生成，角色音色请参考{{Audio 1}}
```

`{{Audio N}}` 编号遵循 `--left` 中 audio 节点的排列顺序。

### 2.2 无参考图时

```
画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```

### 2.3 `{{Image N}}` 编号规则

- `--left` 传入顺序决定编号，第一个 → `{{Image 1}}`
- `--prompt` 写入不会重算 `imageList`，可在创建后安全更新
- `{{Audio N}}` 是独立的编号体系，与 `{{Image N}}` 互不干扰。audio 节点在 `--left` 中的排列顺序决定 `{{Audio N}}` 编号。

### 2.4 `{{Node "..."}}` 占位符（v1.1.1+ 推荐）

v1.1.1+ 支持按**节点展示名**引用已连线上游节点，不再依赖 `{{Image N}}` 编号：

```bash
"请参考场景氛围{{Node \"场景参考_01\"}}和角色形象{{Node \"角色参考_01\"}}进行画面生成"
```

- 节点名在画布内唯一时优先使用此方式
- 遇重名先用 `libtv node <名>` 查询 `nodeKey`，改用 `{{Node <nodeKey>}}`

---

## 3. 时长计算

```python
def get_duration(group_json):
    raw = group_json.get("组时长", "5")
    try:
        return max(4, min(15, int(raw)))
    except (ValueError, TypeError):
        shots = group_json.get("镜头列表", [])
        if shots:
            return max(4, min(15, sum(int(s.get("时长", 5)) for s in shots)))
        return 5
```

---

## 4. 分辨率映射

`project_config.json` 的 `resolution` 字段映射为 libtv `--set resolution`：

| 配置值 | `-s resolution` |
|--------|----------------|
| `480p` | `480p` |
| `720p` | `720p` |
| `1080p` / `2K` / `4K` | `720p` |

---

## 5. 音频映射

`project_config.json` 的 `enable_sound` 字段（boolean）映射为 libtv `--set enableSound`：

| project_config | libtv |
|----------------|-------|
| `true` | `on` |
| `false` | `off` |

音频的**最终开关**由组级音频判定（`should_enable_sound`）与全局 `enable_sound` 共同决定：组级有台词/音效时强制开启，否则使用全局配置。组级判定逻辑见第 6 节。

---

## 6. 参考素材映射

### 6.1 选取策略

`project_config.json` 的 `use_storyboard_images` 决定视频导演以何种优先级选取参考素材连线到 video 节点：

| use_storyboard_images | 优先级顺序 |
|:---------------------:|-----------|
| `true` | 分镜图 > 角色参考 > 道具参考 > 场景参考 |
| `false` / 未设置 | 角色参考 > 场景参考 > 道具参考 > 风格参考 |

> **音色参考**：当 `enable_sound=true` 且分镜组包含台词时，额外选取对应角色的音色参考作为素材源，不参与上述优先级排序。

### 6.1.1 内容过滤规则

所有参考素材的选取必须基于**分组实际内容**，而非全局可用素材：

**角色过滤**：读取分组 JSON 的 `镜头列表`，检查 `场景描述` 和 `站位/调度` 中出现的角色名，只连线该分组实际出场的角色参考图。

**场景过滤**：读取分组所在场的 `场名称` 或 `通用设定.场景名称`，只连线该场景对应的场景参考图。

**道具过滤**：读取分组 JSON 的 `镜头列表`，检查 `场景描述` 和 `站位/调度` 中出现的道具名，只连线该分组实际使用的道具参考图。

**音色过滤**（见 §6.4）：只连线在分组中有台词的角色对应的音色参考。

示例：组1的 `场景描述` 中只提到"爸爸"和"妈妈"、以及"平板电脑"和"锅铲"，则只连线：
- 角色：吉小泰、妈妈 ✅
- 场景：客厅 ✅
- 道具：平板手机、锅铲 ✅
- 音色：吉小泰、妈妈（有台词）✅
- **不连线**：女儿 ❌、隐患清单 ❌

### 6.2 上传命名

| 素材类型 | 上传名 | 源路径 |
|----------|--------|--------|
| 角色参考图 | `角色参考_{序号}` | `temp/分组素材/{剧集号}/角色参考/*.png` |
| 场景参考图 | `场景参考_{序号}` | `temp/分组素材/{剧集号}/场景参考/*.png` |
| 道具参考图 | `道具参考_{序号}` | `temp/分组素材/{剧集号}/道具参考/*.png` |
| 分镜图 | `分镜图_{序号}` | `temp/分组素材/{剧集号}/分镜图/*.png` |
| 音色参考 | `音色_{角色名}` | `project/{项目名}/全局依赖/音色参考/{角色名}-音色参考.wav` |

### 6.3 连线示例

`--left` 顺序决定 `{{Image N}}` 编号。

**v1.1.1+ 注意**：`--left`/`--right` 改为 **ensure 模式**——只确保列出的节点已连线，不会删除未列出的已有边。需要增删时：
- 追加：`--left-add <节点>` / `--left-rm <节点>`
- 全量替换：先用 `--left-rm` 移除旧的、再加 `--left`（或 `--left-add`）新的

**分镜图模式（use_storyboard_images=true）：**
```bash
libtv node create "组1" -t video \
  --prompt "请参考本组分镜构图{{Image 1}}和场景氛围{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 分镜图_组1 --left 场景参考_01 \
  --left 音色_吉小泰   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

**非分镜图模式（use_storyboard_images=false）：**
```bash
libtv node create "组1" -t video \
  --prompt "请参考角色形象{{Image 1}}和场景氛围{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 角色参考_01 --left 场景参考_01 \
  --left 音色_吉小泰   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

### 6.4 音色参考选取逻辑

音色参考的选取与 `enable_sound` 配置及分镜组内容相关：

1. **前置条件**：仅当 `project_config.json` 的 `enable_sound=true` 时触发音色参考选取
2. **检查分镜内容**：读取分镜组 JSON 的 `镜头列表`，检查是否有非空的 `台词` 或 `音效` 字段
3. **匹配角色名**：从以下位置提取本组涉及的角色名：
   - **`台词` 字段**：格式为 `角色名：台词内容`，提取冒号前的角色名
   - **`场景描述` 字段**：提取其中出现的角色名称
   - **`站位/调度` 字段**：提取其中出现的角色名称
4. **查找音色文件**：在 `全局依赖/音色参考/` 目录下查找 `{角色名}-音色参考.wav` 文件
5. **上传并连线**：匹配到的音色参考通过 `libtv upload "音色_{角色名}" -t audio -f "..."` 上传，并通过 `--left 音色_{角色名}` 连入 video 节点
6. **使用 {{Audio N}} 引用**：音色参考在 prompt 中使用 `{{Audio N}}` 引用，`N` 为 `--left` 中 audio 节点的排列序号（从 1 开始）。`{{Audio N}}` 与 `{{Image N}}` 是独立的编号体系，互不干扰。

---

## 7. 组级音频判定

`project_config.json` 的 `enable_sound` 是全局开关，此函数根据分镜组内容做局部判定：

```python
def should_enable_sound(group_json):
    for shot in group_json.get("镜头列表", []):
        if shot.get("台词", "").strip() or shot.get("音效", "").strip():
            return True
    for kw in ["配音", "旁白", "音效", "对话", "配乐", "音乐"]:
        if kw in group_json.get("组叙事概述", ""):
            return True
    return False
```

---

## 8. 完整示例

```bash
# 创建/切换到项目工作区
libtv workspace create "吉泰安防" 2>/dev/null || libtv workspace use <workspaceId>

# 在当前工作区下创建画布
libtv project create "吉泰安防_EP01" --ratio 9:16

# 绑定画布
$canvasUuid = (Get-Content -Encoding UTF8 -Raw ".libtv/project.json" | ConvertFrom-Json).projectUuid
libtv project use $canvasUuid

libtv node create "组1" -t video \
  --prompt "请参考场景氛围{{Image 1}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1,\"组叙事概述\":\"火焰测试\"}" \
  --set model=Seedance 2.0 VIP \
  --set modeType=mixed2video \
  --set count=1 \
  --set ratio=16:9 \
  --set resolution=720p \
  --set duration=5 \
  --set enableSound=on \
  --left 场景参考_01
```
