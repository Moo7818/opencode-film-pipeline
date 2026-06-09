# 自动化管线脚本

`scripts/run_video_pipeline.py` 将标准视频导演工作流封装为一条命令，一站式完成「上传参考图 → 创建节点 → 建组 → 运行 → 下载视频」。

## 参数列表

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--build` | ✅ | 启动完整流程 |
| `--project <名>` | ✅ | 项目名，对应 `project/<名>/` |
| `--episode <号>` | ✅ | 剧集号，如 `EP01` |
| `--canvas-uuid <UUID>` | ✅ | 画布项目 UUID |
| `--groups <N...>` | ✅ | 组号列表，如 `7 8 9` |
| `--refs "组N:类型_名,类型_名"` | ❌ | 参考图映射，可重复 |
| `--run` | ❌ | 建组后执行运行 |
| `--download` | ❌ | 运行后自动轮询并下载视频到 `project/<项目>/<剧集>/视频/` |
| `--output-dir <路径>` | ❌ | 自定义下载目录（默认见 `--download`） |
| `--poll-interval <秒>` | ❌ | 轮询间隔（默认 30） |
| `--poll-timeout <秒>` | ❌ | 轮询超时（默认 600） |
| `--model <key>` | ❌ | 视频模型（默认 `star-video2`） |
| `--ratio <值>` | ❌ | 画面比例（默认 `16:9`） |
| `--resolution <值>` | ❌ | 分辨率（默认 `480p`） |
| `--sound <on/off>` | ❌ | 音频开关（默认 `on`） |

## 使用示例

```bash
python .opencode/skills/video-director-libtv/scripts/run_video_pipeline.py --build ^
  --project "项目名" --episode EP01 --canvas-uuid <UUID> ^
  --groups 7 8 9 --model star-video2 --ratio 16:9 ^
  --refs "组7:场景_现代南京,角色_一岛" ^
  --run --download
```

## 输出产物

```
project/<项目>/<剧集>/视频/
├── 组7.mp4
├── 组8.mp4
├── 组9.mp4
└── _manifest.json    ← 下载清单
```
