# 自动化管线脚本

`scripts/run_video_pipeline.py` 将标准视频导演工作流封装为一条命令，一站式完成「上传参考图 → 创建节点 → 建组 → 运行 → 下载视频」。

## 参数列表

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--build` | ✅ | 启动完整流程 |
| `--project <名>` | ✅ | 项目名，对应 `project/<名>/` |
| `--episode <号>` | ✅ | 剧集号，如 `EP01` |
| `--canvas-uuid <UUID>` | ❌ | 画布 UUID（不传时自动从 project_config.json 的 episodes 映射查找） |
| `--groups <N...>` | ✅ | 组号列表，如 `7 8 9` |
| `--refs "组N:类型_名,类型_名"` | ❌ | 参考图映射，可重复；仅上传指定的参考图（按需上传） |
| `--voice-refs <角色1,角色2,...>` | ❌ | 音色参考角色列表，如 `吉小泰,妈妈,女儿`；仅上传指定角色的音色参考，未指定时跳过 |
| `--run` | ❌ | 建组后执行运行 |
| `--download` | ❌ | 运行后自动轮询并下载视频到 `project/<项目>/<剧集>/视频/` |
| `--output-dir <路径>` | ❌ | 自定义下载目录（默认见 `--download`） |
| `--poll-interval <秒>` | ❌ | 轮询间隔（默认 30） |
| `--poll-timeout <秒>` | ❌ | 轮询超时（默认 600） |
| `--model <modelName>` | ❌ | 视频模型中文名（如 `Seedance 2.0 VIP`）；libtv 1.1.1+ 直接使用该值，禁止传 modelKey |
| `--ratio <值>` | ❌ | 画面比例（默认 `16:9`） |
| `--resolution <值>` | ❌ | 分辨率（默认 `480p`） |
| `--sound <on/off>` | ❌ | 音频开关（默认 `on`） |
| `--storyboard-mode <模式>` | ❌ | 分镜模式：`detailed`（组{N}.json）或 `simplified`（组{N}.md），覆盖 project_config.json |
| `--no-group` | ❌ | 跳过建组步骤，仅创建独立节点不创建编组；与 `--run` 不兼容 |

## 使用示例

```bash
python .opencode/skills/video-director-libtv/scripts/run_video_pipeline.py --build ^
  --project "项目名" --episode EP01 ^
  --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 ^
  --refs "组7:场景_现代南京,角色_一岛" ^
  --run --download
```

仅创建节点不建组（`--no-group`）：

```bash
python .opencode/skills/video-director-libtv/scripts/run_video_pipeline.py --build ^
  --project "项目名" --episode EP01 ^
  --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 ^
  --refs "组7:场景_现代南京,角色_一岛" ^
  --no-group
```

## 输出产物

```
project/<项目>/<剧集>/视频/
├── 组7.mp4
├── 组8.mp4
├── 组9.mp4
└── _manifest.json    ← 下载清单
```
