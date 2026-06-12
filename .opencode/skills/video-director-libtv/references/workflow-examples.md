# 常见场景命令序列

**通用约定**：
- `<项目UUID>` = 画布项目 UUID（`libtv project list` 可查）
- 所有命令在**画布所在工作目录**下执行

---

## 场景 1：纯文生视频

```bash
libtv project use <项目UUID>

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
libtv project use <项目UUID>

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

需要先确认 `imageList` 顺序再写引用时使用。

```bash
libtv project use <项目UUID>

libtv upload "场景_办公室" -t image -f "temp/场景参考.png"
libtv upload "角色_经理" -t image -f "temp/角色参考.png"
libtv upload "道具_电脑" -t image -f "temp/道具参考.png"

# 阶段1：创建节点 + 连线（占位 prompt）
libtv node create "组1" -t video \
  --prompt "画面严禁出现任何字幕，无配乐
---
{\"组号\":1}" \
  --set model=Seedance 2.0 VIP --set modeType=mixed2video \
  --set count=1 --set ratio=16:9 --set duration=5 \
  --set enableSound=on \
  --left 场景_办公室 --left 角色_经理 --left 道具_电脑

# 阶段2：查询 imageList 顺序
libtv node "组1"
# 输出 imageList 顺序决定了 {{Image 1}}{{Image 2}}{{Image 3}}

# 根据实际顺序写入引用行（--prompt 不会重算顺序）
libtv node "组1" --prompt "请参考办公室场景{{Image 1}}、经理角色形象{{Image 2}}和电脑道具样式{{Image 3}}进行画面生成

画面严禁出现任何字幕，无配乐
---
{\"组号\":1}"

libtv group create "EP01视频" --node 组1
libtv group "EP01视频" --run
```

---

## 场景 4：批量多组处理

```bash
libtv project use <项目UUID>

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
| 绑定项目 | `libtv project use <UUID>` |
| 上传参考图 | `libtv upload "<名>" -t image -f "<路径>"` |
| 创建节点（一次性） | `libtv node create "<名>" -t video --prompt "完整prompt含引用行" --set ... --left ...` |
| 创建节点（阶段1） | `libtv node create "<名>" -t video --prompt "占位" --set ... --left ...` |
| 查询 imageList | `libtv node "<名>"` |
| 更新 prompt（阶段2） | `libtv node "<名>" --prompt "完整prompt含引用行"` |
| 建分组 | `libtv group create "<组名>" --node <节点1>` |
| 整组运行 | `libtv group "<组名>" --run` |
| 删除节点 | `libtv node delete "<名>"` |
| 查看模型 | `libtv model search --type video` |
