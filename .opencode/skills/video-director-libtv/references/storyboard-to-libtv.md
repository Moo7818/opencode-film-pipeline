# 映射规则：分镜组 → libtv video node

## 0. 参数来源总览

| 来源文件 | 路径 | 提供什么 |
|----------|------|----------|
| `project_config.json` | `.meta/projects/{uuid}/project_config.json` | 全局视频参数（比例、模型、模式等） |
| 分组文件 | `project/<项目名>/<剧集号>/分镜/分组/组{N}.json` 或 `组{N}.md` | 本组生成参数（时长、分镜内容） |

**分组文件格式由 `storyboard_mode` 决定**：
- **详细模式**（`storyboard_mode=detailed`，默认）→ `组{N}.json`：结构化数据，包含 `组号`、`组时长`、`镜头列表` 等字段
- **精简模式**（`storyboard_mode=simplified`）→ `组{N}.md`：讲戏式 Markdown，读取全部内容作为视频生成提示词

`run_video_pipeline.py` 按模式选择性加载：优先级为 `--storyboard-mode` CLI 参数 > `project_config.json` 的 `storyboard_mode` 字段 > 默认 `detailed`。

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

**严禁修改原始分镜组文件内容。**

### 2.1 JSON 格式分组

**有参考图时**：

```
{引用行，由视频导演根据素材自行编写，如"掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}"}

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```

**无参考图时**：

```
画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```

### 2.2 MD 格式分组

**有参考图时**：

```
{引用行，由视频导演根据素材自行编写，如"掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}"}

画面严禁出现任何字幕，无配乐
---
{完整的组 MD 文件内容，读取全部内容，严禁修改}
```

**无参考图时**：

```
画面严禁出现任何字幕，无配乐
---
{完整的组 MD 文件内容，读取全部内容，严禁修改}
```

**MD 格式文件示例**（`组1.md`，精简模式产出）：
```markdown
组时长：7s
转场：摇镜过渡
镜头数：1

通用设定：
风格质感：水墨风人物动画风格
场景：春生茶肆（破茶馆状态）
光线：散射柔光从破窗和门口射入，光柱中有尘埃飞舞，室内偏暗灰褐色主调
色调：低饱和度水墨色调，灰褐色土黄色为主，宣纸质感背景
氛围：破败中带戏谑，冷清中埋希望。

破茶馆室内全景建立，掌柜穿越醒来从地板起身环顾漏雨房梁。

破茶馆室内，晨光从破窗斜射入内，光柱中尘埃飘浮，房梁滴水落入木盆，水墨画山水背景。镜头从全景缓慢下降至掌柜面部，平拍缓降推镜。掌柜仰面躺在木地板上画面中央偏下，猛地睁眼，一只手摸地板——木头的。他坐起身，抬头看漏雨房梁，一滴水落在额头。大脑空白，试图理清穿越前后的记忆断层——睁眼瞬间瞳孔收缩，眉头紧皱，视线先看天花板又看自己双手，最后望向漏雨的房梁方向，嘴微张欲言又止。柔光从破窗斜入形成光柱，尘埃在光中飞舞，房梁滴水处有细小光斑闪烁，室内暗部呈灰褐色，破败冷清但带喜剧感。雨滴落入木盆的啪嗒声、手摸木地板的摩擦声在寂静中格外清晰。

掌柜自言自语："上一秒还在改PPT，这一秒——我成掌柜了？"
```

> 精简模式的 MD 文件是讲戏式叙事，一段一镜，技术参数融入叙述。`组时长` 从首行 `组时长：Ns` 提取，`镜头数` 从 `镜头数：N` 行提取。全文直接作为 prompt 内容传入视频模型。

引用行格式为 `{名称}{类型}参考{{Image N}}`，如 `掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}`。分镜图引用为 `镜头{M}参考{{Image N}}`，视觉锚点引用为 `场{N}视觉锚点参考{{Image N}}`。

### 2.3 有音色参考时

当音色参考节点连入 video 节点时，可在引用行末尾追加音色引用。格式为 `{角色名}音色参考{{Audio N}}`，例如：

```
掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}，掌柜音色参考{{Audio 1}}
```

`{{Audio N}}` 编号遵循 `--left` 中 audio 节点的排列顺序。

### 2.4 `{{Image N}}` 编号规则

- `--left` 传入顺序决定编号，第一个 → `{{Image 1}}`
- `--prompt` 写入不会重算 `imageList`，可在创建后安全更新
- `{{Audio N}}` 是独立的编号体系，与 `{{Image N}}` 互不干扰。audio 节点在 `--left` 中的排列顺序决定 `{{Audio N}}` 编号。

### 2.5 `{{Node "..."}}` 占位符（v1.1.1+ 推荐）

v1.1.1+ 支持按**节点展示名**引用已连线上游节点，不再依赖 `{{Image N}}` 编号：

```bash
"场景参考{{Node \"场景参考_01\"}}、角色参考{{Node \"角色参考_01\"}}"
```

- 节点名在画布内唯一时优先使用此方式
- 遇重名先用 `libtv node <名>` 查询 `nodeKey`，改用 `{{Node <nodeKey>}}`

---

## 3. 时长计算

### JSON 格式分组

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

### MD 格式分组

MD 格式分组的时长从文件首行 `组时长：Ns` 提取（由 `load_group_file` 函数处理）。如缺失则回退到默认值 5 秒，并经 `calc_duration` 限制在 4-15 秒范围内。

```python
# load_group_file 从 MD 首行提取组时长
duration_match = re.search(r"组时长[：:]\s*(\d+)", raw_md)
group = {"_format": "md", "_raw_content": raw_md, "组时长": duration_match.group(1) if duration_match else "5"}
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

### ⛔ 选角参考图禁令

**视频生成绝对不能使用选角参考图**（`{角色名}_选角.png`）。

选角参考图是 Tier 1 资产，角色身着白色短袖 T 恤、站在灰色无影墙前，仅用于确立角色面部特征和体型轮廓。将其用于视频生成会导致：
- 角色穿着与剧情不符的白色 T 恤
- 画面背景变为灰色无影墙，破坏场景氛围
- 妆造信息丢失（选角资产不含服装、配饰）

脚本 `scan_project_refs` 已自动过滤 `_选角.png` 文件，不会上传到画布。Agent 在手动指定 `--refs` 时也必须确保不引用选角资产。

### 6.1 选取策略（由 Agent 判断）

**参考图的选取由视频导演 Agent 根据分组内容自行判断**，脚本不做自动匹配。Agent 需读取每个分组的实际内容，判断该组出场的角色、所在场景、使用的道具，然后通过 `--refs` 参数显式指定。**仅 `--refs` 中指定的参考图会被上传到画布**，未指定的素材不会上传，避免无关素材占用画布。

`project_config.json` 的 `reference_image_mode` 决定脚本自动扫描哪种参考图并按需上传：

| reference_image_mode | 自动扫描目录 | 匹配方式 | 优先级顺序 |
|:--------------------:|------------|----------|-----------|
| `visual_anchor`（默认） | `{剧集号}/分镜/视觉锚点/` | 仅当该场只有一张锚点图（无阶段后缀）时按组文件的场号自动匹配；同场多阶段锚点时，由 Agent 读取视觉锚点_任务表.json 按组的镜头范围语义匹配对应阶段锚点，通过 `--refs` 显式指定；脚本不做自动匹配 | 视觉锚点 > 角色参考 > 道具参考 > 场景参考 |
| `storyboard_images` | `{剧集号}/分镜/分镜图/` | 按组号匹配分镜图 | 分镜图 > 角色参考 > 道具参考 > 场景参考 |
| `none` | 不自动扫描 | — | 角色参考 > 场景参考 > 道具参考 > 风格参考 |

> **向后兼容**：未设置 `reference_image_mode` 时，根据 `use_storyboard_images` 推断（`true`→`storyboard_images`，`false`/未设置→`visual_anchor`）。

> **音色参考**：当 `enable_sound=true` 且分镜组包含台词时，额外选取对应角色的音色参考作为素材源，不参与上述优先级排序。

### 6.1.1 Agent 判断规则

Agent 在为每个分组选取参考素材时，必须基于**分组实际内容**：

**角色判断**：读取分组的镜头列表/叙事文本，检查实际出场的角色名，只选取该分组出场的角色参考图（Tier 2 妆造资产，如 `{角色名}_默认.png` 或 `{角色名}_{妆造名}.png`）。

**场景判断**：读取分组所在场的场景名称，只选取该场景对应的场景参考图。

**道具判断**：读取分组的镜头列表/叙事文本，检查实际使用的道具名，只选取该分组使用的道具参考图。

**音色判断**（见 §6.4）：只选取在分组中有台词的角色对应的音色参考。

**视觉锚点选取（阶段匹配）**：当组所在场有多张阶段锚点图（如 `视觉锚点_场1A`、`视觉锚点_场1B`）时，脚本不做自动匹配。Agent 读取 `{剧集号}/分镜/视觉锚点_任务表.json`，对每个分组读取组文件的场号与镜号起始，在任务表中找到同场锚点任务，根据 `shot_range` 判定该组镜头落在哪个阶段，通过 `--refs` 指定对应阶段锚点节点名（如 `--refs "组2:视觉锚点_场1A,角色_掌柜"`）。仅当该场只有一张锚点图（无阶段后缀）时，脚本按场号自动连线（向后兼容）。

**`--refs` 格式**：`--refs "组N:类型_名,类型_名"`，如 `--refs "组1:角色_掌柜,场景_春生茶肆,道具_茶壶"`

示例：组1的内容中只提到"爸爸"和"妈妈"、以及"平板电脑"和"锅铲"，则只指定：
- 角色：吉小泰、妈妈 ✅
- 场景：客厅 ✅
- 道具：平板手机、锅铲 ✅
- 音色：吉小泰、妈妈（有台词）✅
- **不选取**：女儿 ❌、隐患清单 ❌、选角参考图 ❌

### 6.2 上传命名

| 素材类型 | 节点名格式 | 源路径 |
|----------|-----------|--------|
| 角色参考图 | `角色_{名称}` | `全局依赖/角色设定/角色参考图/*.png`（自动过滤 `_选角.png`） |
| 场景参考图 | `场景_{名称}` | `全局依赖/场景设定/场景参考图/*.png` |
| 道具参考图 | `道具_{名称}` | `全局依赖/道具设定/道具参考图/*.png` |
| 分镜图 | `分镜_组{N}_镜{M}` | `{剧集号}/分镜/分镜图/组{N}_镜{M}.png` |
| 视觉锚点图 | `视觉锚点_场{N}{阶段?}`（如 `视觉锚点_场1`、`视觉锚点_场1A`） | `{剧集号}/分镜/视觉锚点/锚点_场{N}{阶段?}_{场景名}.png`（如 `锚点_场1A_断供报信.png`） |
| 音色参考 | `音色_{角色名}` | `全局依赖/音色参考/{角色名}-音色参考.{ext}` 或 `{角色名}音色.{ext}`（`.wav` `.mp3` `.m4a` `.ogg` `.flac`） |

### 6.3 连线示例

`--left` 顺序决定 `{{Image N}}` 编号。参考图按类型排序：**分镜图（按镜号）→ 视觉锚点（按场号）→ 角色 → 道具 → 音色**。场景通常不引用（分镜图/视觉锚点已含场景信息）。

**v1.1.1+ 注意**：`--left`/`--right` 改为 **ensure 模式**——只确保列出的节点已连线，不会删除未列出的已有边。需要增删时：
- 追加：`--left-add <节点>` / `--left-rm <节点>`
- 全量替换：先用 `--left-rm` 移除旧的、再加 `--left`（或 `--left-add`）新的

**视觉锚点模式（reference_image_mode=visual_anchor，默认）：**
```bash
libtv node create "组1" -t video \
  --prompt "场1视觉锚点参考{{Image 1}}、掌柜角色参考{{Image 2}}、茶友簿道具参考{{Image 3}}，掌柜音色参考{{Audio 1}}

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 视觉锚点_场1 \
  --left 角色_掌柜 --left 道具_茶友簿 \
  --left 音色_掌柜   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

> 视觉锚点图由脚本自动扫描 `{剧集号}/分镜/视觉锚点/` 目录并上传。**仅当该场只有一张锚点图（无阶段后缀）时**脚本按组文件的场号自动连线；同场多阶段锚点时脚本不做自动匹配，Agent 须通过 `--refs` 显式指定对应阶段锚点节点名，再通过 `--refs` 指定角色和道具参考。

**视觉锚点多阶段示例（同场多阶段锚点，reference_image_mode=visual_anchor）：**

场1 拆分为 1A、1B 两个阶段锚点（`视觉锚点_场1A`、`视觉锚点_场1B`），组2 镜头落在阶段 1A（`shot_range` 判定），Agent 显式指定阶段锚点：

```bash
libtv node create "组2" -t video \
  --prompt "场1A视觉锚点参考{{Image 1}}、掌柜角色参考{{Image 2}}、茶友簿道具参考{{Image 3}}，掌柜音色参考{{Audio 1}}

画面严禁出现任何字幕，无配乐
---
{\"组号\":2}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 视觉锚点_场1A \
  --left 角色_掌柜 --left 道具_茶友簿 \
  --left 音色_掌柜   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

> 组1 镜头落在阶段 1B（`视觉锚点_场1B`）时，`--refs` 相应写 `组1:视觉锚点_场1B,...`，连线 `--left 视觉锚点_场1B`。脚本对多阶段锚点场不做自动匹配，避免把不覆盖该组镜头的阶段锚点错连进来。

**分镜图模式（reference_image_mode=storyboard_images）：**
```bash
libtv node create "组1" -t video \
  --prompt "镜头1参考{{Image 1}}、镜头2参考{{Image 2}}、镜头3参考{{Image 3}}、掌柜角色参考{{Image 4}}、茶友簿道具参考{{Image 5}}，掌柜音色参考{{Audio 1}}

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 分镜_组1_镜1 --left 分镜_组1_镜2 --left 分镜_组1_镜3 \
  --left 角色_掌柜 --left 道具_茶友簿 \
  --left 音色_掌柜   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

> 分镜图由脚本自动扫描 `{剧集号}/分镜/分镜图/` 目录并上传，无需在 `--refs` 中手动指定。Agent 只需通过 `--refs` 指定角色和道具参考。

**无参考图模式（reference_image_mode=none）：**
```bash
libtv node create "组1" -t video \
  --prompt "掌柜角色参考{{Image 1}}、茶馆场景参考{{Image 2}}

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 角色_掌柜 --left 场景_春生茶肆 \
  --left 音色_掌柜   # 可选：音色参考连线，prompt 中用 {{Audio 1}} 引用
```

### 6.4 音色参考选取逻辑（由 Agent 判断）

**音色参考的选取由视频导演 Agent 根据分组内容自行判断**，脚本不做自动匹配，也不做自动全量扫描。

1. **Agent 判断**：Agent 读取每个分组的实际内容，判断哪些角色在本组有台词，通过 `--voice-refs` 参数显式指定需要的音色参考
2. **查找音色文件**：在 `全局依赖/音色参考/` 目录下查找音频文件（支持两种命名模式：`{角色名}-音色参考.{ext}` 和 `{角色名}音色.{ext}`，格式 `.wav` `.mp3` `.m4a` `.ogg` `.flac`）
3. **上传并连线**：音色参考通过 `libtv upload "音色_{角色名}" -t audio -f "..."` 上传，所有已上传的音色参考统一连入每个组
4. **使用 {{Audio N}} 引用**：音色参考在 prompt 中使用 `{{Audio N}}` 引用，`N` 为 `--left` 中 audio 节点的排列序号（从 1 开始）。`{{Audio N}}` 与 `{{Image N}}` 是独立的编号体系，互不干扰。

> **仅按需上传**：未指定 `--voice-refs` 时，脚本跳过音色参考上传，不会自动扫描目录全量上传。

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

### 8.1 JSON 格式分组

```bash
# 创建/切换到项目工作区
libtv workspace create "吉泰安防" 2>/dev/null || libtv workspace use <workspaceId>

# 在当前工作区下创建画布
libtv project create "吉泰安防_EP01" --ratio 9:16

# 绑定画布
$canvasUuid = (Get-Content -Encoding UTF8 -Raw ".libtv/project.json" | ConvertFrom-Json).projectUuid
libtv project use $canvasUuid

libtv node create "组1" -t video \
  --prompt "场景参考{{Image 1}}

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

### 8.2 MD 格式分组（精简模式）

使用 `run_video_pipeline.py --storyboard-mode simplified` 直接加载 `组{N}.md` 文件：

```bash
# 精简模式完整流程（自动读取 project_config.json 的 storyboard_mode，
# 也可用 --storyboard-mode simplified 显式指定）
python ".opencode/skills/video-director-libtv/scripts/run_video_pipeline.py" --build ^
  --project "吉泰安防" --episode EP01 ^
  --groups 1 2 3 --model "Seedance 2.0 VIP" --ratio 16:9 ^
  --storyboard-mode simplified ^
  --refs "组1:场景_破茶馆,角色_掌柜" ^
  --run --download
```

脚本内部流程：
1. `load_storyboard_mode()` 读取 `project_config.json` 或 CLI 参数确定模式为 `simplified`
2. `load_group_file()` 加载 `组{N}.md`，从首行提取 `组时长`，全文存入 `_raw_content`
3. `build_prompt()` 将 MD 全文作为 prompt 内容（附带引用行和约束行）
4. `calc_duration()` 从 `组时长` 字段提取时长并限制在 4-15 秒
