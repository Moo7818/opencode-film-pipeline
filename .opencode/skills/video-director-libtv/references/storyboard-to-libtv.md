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
| `model` | `--set model=<值>` | 视频模型 modelKey |
| `mode` | `--set modeType=<值>` | 生成模式，如 `mixed2video`、`text2video` |
| `enable_sound` | `--set enableSound=on/off` | `true` → `on`，`false` → `off` |
| — | `--set scene=<值>` | v1.1.1+ 模型 schema 可选业务场景字段，由 `libtv model <modelKey>` 决定

---

## 2. Prompt 组装规则

**严禁修改原始分镜组 JSON 内容。**

### 2.1 有参考图时

```
请参考{自然描述}{{Image 1}}、{自然描述}{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```
自然描述根据参考图文件名语义生成，如 `一岛角色相貌参考{{Image 1}}、现代南京长江边场景参考{{Image 2}}`

### 2.2 无参考图时

```
画面严禁出现任何字幕，无配乐
---
{完整的组 JSON 内容，原样拷贝，严禁修改}
```

### 2.3 `{{Image N}}` 编号规则

- `--left` 传入顺序决定编号，第一个 → `{{Image 1}}`
- `--prompt` 写入不会重算 `imageList`，可在创建后安全更新

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

### 6.2 上传命名

| 素材类型 | 上传名 | 源路径 |
|----------|--------|--------|
| 角色参考图 | `角色参考_{序号}` | `temp/分组素材/{剧集号}/角色参考/*.png` |
| 场景参考图 | `场景参考_{序号}` | `temp/分组素材/{剧集号}/场景参考/*.png` |
| 道具参考图 | `道具参考_{序号}` | `temp/分组素材/{剧集号}/道具参考/*.png` |
| 分镜图 | `分镜图_{序号}` | `temp/分组素材/{剧集号}/分镜图/*.png` |

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
  --left 分镜图_组1 --left 场景参考_01
```

**非分镜图模式（use_storyboard_images=false）：**
```bash
libtv node create "组1" -t video \
  --prompt "请参考角色形象{{Image 1}}和场景氛围{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --left 角色参考_01 --left 场景参考_01
```

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
