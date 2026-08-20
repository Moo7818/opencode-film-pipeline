# 自动化管线脚本

`scripts/run_video_pipeline.py` 将标准视频导演工作流封装为**三阶段**命令：`--plan`（计划）→ `--build`（构建）→ `--run`（运行 + 下载）。

> **构建与运行分离**：`--run` 必须在 `--build` 完成后单独调用，避免单次工具调用被长时间视频生成阻塞（生成可达数十分钟）。

## 三阶段模式（互斥，必选其一）

| 模式 | 作用 | 前置 |
|------|------|------|
| `--plan` | 生成执行计划：各组参考图/音色**自动匹配**结果 + 可直接复制的 `--refs`/`--voice-refs` 建议参数。**纯本地解析，不调用 libtv**，无需画布/模型 | 分组文件就绪 |
| `--build` | 并发上传参考素材 → 并发创建 video 节点（upsert 幂等）→ 幂等建组。**不运行生成** | `--plan` 可选先行 |
| `--run` | 运行已有分组（阻塞等待终态 JSON）→ 解析终态提取 URL → 并发下载 + 写 `_manifest.json` | 须先 `--build` |

## 参数列表

| 参数 | 适用模式 | 必填 | 说明 |
|------|:--------:|:----:|------|
| `--plan` / `--build` / `--run` | — | ✅ 三选一 | 模式互斥；同时指定 `--build --run` 会报错并提示分两步调用 |
| `--project <名>` | 全部 | ✅ | 项目名，对应 `project/<名>/` |
| `--episode <号>` | 全部 | ❌ | 剧集号（默认 `EP01`） |
| `--canvas-uuid <UUID>` | build/run | ✅ | 画布 UUID；由 agent 从 `meta_query(scope=config)` 读出 `config.episodes.{剧集号}.canvas_uuid` 后显式传入 |
| `--groups <N...>` | 全部 | ✅ | 组号列表，如 `7 8 9`；**顺序即分组的整组执行顺序** |
| `--model <modelName>` | build | ✅ | 视频模型中文名（如 `Seedance 2.0 VIP`），禁止传 modelKey |
| `--storyboard-mode <模式>` | build/plan | ✅ | `detailed`（组{N}.json）或 `simplified`（组{N}.md） |
| `--reference-image-mode <模式>` | build/plan | ✅ | `visual_anchor` / `storyboard_images` / `none`，控制分镜图/视觉锚点自动扫描 |
| `--refs "组N:类型_名,..."` | build/plan | ❌ | 显式参考图映射，可重复；**显式指定的组不做自动匹配** |
| `--voice-refs <角色...>` | build/plan | ❌ | 音色参考角色列表；未指定时跳过音色上传 |
| `--no-auto-refs` | build/plan | ❌ | 关闭自动匹配：未显式 `--refs` 的组以纯文生视频生成（旧行为） |
| `--ratio` / `--resolution` / `--sound` | build | ❌ | 画面比例（默认 `16:9`）/ 分辨率（默认 `480p`，Minimax 系自动映射 `768P`）/ 音频开关（默认 `on`） |
| `--no-group` | build | ❌ | 跳过建组，仅创建独立节点；与 `--run` 模式不兼容 |
| `--group-name <名>` | build/run | ❌ | 自定义分组名（默认 `{剧集}_组N_N_N`） |
| `--download` | run | ❌ | 运行完成后并发下载视频到 `project/<项目>/<剧集>/视频/` 并写 `_manifest.json` |
| `--output-dir <路径>` | run | ❌ | 自定义下载目录 |
| `--max-workers <N>` | 全部 | ❌ | 并发线程数（默认 4，上限 8） |
| `--refresh-cache` | build | ❌ | 忽略画布节点缓存，强制全量拉取重建 |
| `--poll-interval` / `--poll-timeout` | run | ❌ | 终态未覆盖节点的查询重试间隔/超时（默认 5s / 600s） |

## 使用示例（三步）

```bash
# 1) 计划：审核各组参考图/音色自动匹配结果（可选但推荐）
python .opencode/skills/video-director-libtv/scripts/run_video_pipeline.py --plan ^
  --project "项目名" --episode EP01 --groups 7 8 9 ^
  --storyboard-mode detailed --reference-image-mode visual_anchor

# 2) 构建：并发上传 → 并发建节点（upsert）→ 幂等建组；未显式 --refs 的组按计划自动匹配
python .opencode/skills/video-director-libtv/scripts/run_video_pipeline.py --build ^
  --project "项目名" --episode EP01 ^
  --canvas-uuid <画布UUID> --model "Seedance 2.0 VIP" ^
  --storyboard-mode detailed --reference-image-mode visual_anchor ^
  --groups 7 8 9 --ratio 16:9 --resolution 480p --sound on ^
  --refs "组7:场景_现代南京,角色_一岛" ^
  --voice-refs 吉小泰

# 3) 运行 + 下载（单独调用，阻塞等待终态后解析 URL 并发下载）
python .opencode/skills/video-director-libtv/scripts/run_video_pipeline.py --run ^
  --project "项目名" --episode EP01 --canvas-uuid <画布UUID> ^
  --groups 7 8 9 --download
```

仅创建节点不建组（`--build --no-group`，之后无法用 `--run` 运行）。

## 参考图自动匹配规则

未显式指定 `--refs` 的组按以下确定性规则自动匹配（`--plan` 可预演结果）：

- **角色/道具**：素材名（文件名，节点名格式 `类型_名称`）出现在组内容（JSON 全文 / MD 原文）中即匹配
- **场景**：仅 `reference_image_mode=none` 时参与（分镜图/视觉锚点已含场景信息）
- **最长名去重**：名称 A 是另一匹配名 B 的子串时丢弃 A（如「掌柜」⊂「大掌柜」）
- **叠加模式自动素材**：`visual_anchor` 单锚点场自动连线 / `storyboard_images` 按组号自动连线（多阶段锚点仍需 `--refs` 显式指定）
- **音色建议**（仅 `--plan` 输出）：角色名出现在台词语料中且本地有音色文件

## 幂等与状态缓存

| 机制 | 行为 |
|------|------|
| 节点 upsert | `node create` 失败（同名已存在）自动回退默认子命令 update（同套 prompt/set/--left）；重跑改参安全 |
| `--left` ensure 语义 | update 不删除未列出的旧边；需清理旧连线用 `libtv node <名> --left-rm <旧上游>` 或删节点重建 |
| 幂等建组 | 用 `libtv group "<名>"`（有则绑定、无则新建），重跑不再产生 `_v2` |
| 画布节点缓存 | 落盘 `.opencode/cache/video-director/<canvas_uuid>.json`，重跑跳过已上传素材；画布被外部修改后用 `--refresh-cache` 重建 |

## 输出产物

```
project/<项目>/<剧集>/视频/
├── 组7.mp4
├── 组8.mp4
├── 组9.mp4
└── _manifest.json    ← 下载清单（含 groupName/status/nodes/failed）
```
