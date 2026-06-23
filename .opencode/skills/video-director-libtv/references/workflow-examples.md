# 常见场景命令序列

**通用约定**：
- `<画布UUID>` = 画布 UUID（`libtv project list` 可查）
- 所有命令在**画布所在工作目录**下执行
- 以下命令基于 `libtv` **v1.1.1+**。关键变化：`group --run` 现为**阻塞等待**命令，CLI 内部完成轮询后退出

---

## 场景 1：纯文生视频

```bash
# 创建/切换到项目工作区
libtv workspace create "项目名" 2>/dev/null || libtv workspace use <workspaceId>

libtv project use <画布UUID>

libtv node create "组1" -t video \
  --prompt "画面严禁出现任何字幕，无配乐
---
{\"组号\":1,\"组叙事概述\":\"城市天际线航拍\"}" \
  --set model=Seedance 2.0 VIP \
  --set modeType=text2video \
  --set count=1 \
  --set ratio=16:9 \
  --set resolution=720p \
  --set duration=5 \
  --set enableSound=on

libtv group create "EP01视频" --node 组1
libtv group "EP01视频" --run
```

---

## 场景 2：有参考图（一次性创建）

```bash
# 创建/切换到项目工作区
libtv workspace create "项目名" 2>/dev/null || libtv workspace use <workspaceId>

libtv project use <画布UUID>

libtv upload "场景参考" -t image -f "temp/场景参考.png"
libtv upload "角色参考" -t image -f "temp/角色参考.png"

# --left 顺序 = {{Image N}} 编号
libtv node create "组1" -t video \
  --prompt "请参考场景氛围{{Image 1}}和角色形象{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP \
  --set modeType=mixed2video \
  --set count=1 \
  --set ratio=16:9 \
  --set duration=5 \
  --set enableSound=on \
  --left 场景参考 --left 角色参考

libtv group create "EP01视频" --node 组1
libtv group "EP01视频" --run
```

---

## 场景 3：有参考图（两阶段）

需要先确认 `imageList` 顺序再写引用时使用。也可改用 `{{Node "..."}}` 省去编号确认（见下文）。

```bash
# 创建/切换到项目工作区
libtv workspace create "项目名" 2>/dev/null || libtv workspace use <workspaceId>

libtv project use <画布UUID>

libtv upload "场景_办公室" -t image -f "temp/场景参考.png"
libtv upload "角色_经理" -t image -f "temp/角色参考.png"
libtv upload "道具_电脑" -t image -f "temp/道具参考.png"

# 上传音色参考（如有角色音色 WAV 文件）
libtv upload "音色_经理" -t audio -f "project/项目名/全局依赖/音色参考/经理-音色参考.wav"

# 阶段1：创建节点 + 连线（占位 prompt）
libtv node create "组1" -t video \
  --prompt "画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --set count=1 --set ratio=16:9 --set duration=5 \
  --set enableSound=on \
  --left 场景_办公室 --left 角色_经理 --left 道具_电脑 \
  --left 音色_经理   # 音色参考连线，prompt 中用 {{Audio 1}} 引用

# 方案 A：查询 imageList 顺序后写引用（兼容旧版）
libtv node "组1"
# 输出 imageList 顺序决定了 {{Image 1}}{{Image 2}}{{Image 3}}

# 根据实际顺序写入引用行（--prompt 不会重算顺序）
libtv node "组1" --prompt "请参考办公室场景{{Image 1}}、经理角色形象{{Image 2}}和电脑道具样式{{Image 3}}进行画面生成，角色音色请参考{{Audio 1}}

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}"

# 方案 B（v1.1.1+）：直接用 {{Node "节点名"}}，无需查询顺序
libtv node "组1" --prompt \
  "请参考办公室场景{{Node \"场景_办公室\"}}、经理角色形象{{Node \"角色_经理\"}}和电脑道具样式{{Node \"道具_电脑\"}}进行画面生成"

libtv group create "EP01视频" --node 组1
libtv group "EP01视频" --run
```

> **音色参考说明**：音色参考（WAV 格式的角色语音样本文件）在以下场景应上传到画布并连线：
> - `project_config.json` 的 `enable_sound=true`
> - 分镜组中包含该角色的台词或音效
>
> 音色参考文件存放路径为 `project/{项目名}/全局依赖/音色参考/{角色名}-音色参考.wav`，上传类型为 `audio`。在 prompt 中使用 `{{Audio N}}` 引用音色参考，`N` 为 `--left` 中 audio 节点的排列序号。

---

## 场景 4：批量多组处理

```bash
# 创建/切换到项目工作区
libtv workspace create "项目名" 2>/dev/null || libtv workspace use <workspaceId>

libtv project use <画布UUID>

libtv upload "场景参考" -t image -f "temp/场景参考.png"
libtv upload "角色参考" -t image -f "temp/角色参考.png"

# && 串联，任一失败则停止
libtv node create "组1" -t video \
  --prompt "请参考场景氛围{{Image 1}}和角色形象{{Image 2}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --set count=1 --set ratio=16:9 --set duration=5 \
  --set enableSound=on \
  --left 场景参考 --left 角色参考 \
  && \
libtv node create "组2" -t video \
  --prompt "请参考场景氛围{{Image 1}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":2}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --set count=1 --set ratio=16:9 --set duration=5 \
  --set enableSound=on \
  --left 场景参考 \
  && \
libtv node create "组3" -t video \
  --prompt "画面严禁出现任何字幕，无配乐
---
{\"组号\":3}" \
  --set model=Seedance 2.0 VIP --set modeType=text2video \
  --set count=1 --set ratio=16:9 --set duration=5 \
  --set enableSound=off

libtv group create "EP01视频" --node 组1 --node 组2 --node 组3
libtv group "EP01视频" --run
```

---

## 命令速查表

| 操作 | 命令 |
|------|------|
| 绑定画布 | `libtv project use <UUID>` |
| 上传参考图 | `libtv upload "<名>" -t image -f "<路径>"` |
| 上传音色参考 | `libtv upload "音色_{角色名}" -t audio -f "project/{项目}/全局依赖/音色参考/{角色名}-音色参考.wav"` |
| 创建节点（一次性） | `libtv node create "<名>" -t video --prompt "完整prompt含引用行" --set ... --left ...` |
| 创建节点（阶段1） | `libtv node create "<名>" -t video --prompt "占位" --set ... --left ...` |
| 查询 imageList | `libtv node "<名>"` |
| 更新 prompt（阶段2） | `libtv node "<名>" --prompt "完整prompt含引用行"` |
| 使用 `{{Node "..."}}`（v1.1.1+） | `libtv node "<名>" --prompt "...{{Node \"上游节点名\"}}..."` |
| 增量追加左连线 | `libtv node "<名>" --left-add <节点名>` |
| 增量移除左连线 | `libtv node "<名>" --left-rm <节点名>` |
| 建分组 | `libtv group create "<组名>" --node <节点1>` |
| 整组运行（**阻塞等待**） | `libtv group "<组名>" --run` |
| 删除节点 | `libtv node delete "<名>"` |
| 查看模型 | `libtv model search --type video` |
