# 视频模型参考

## 模型选择策略

**永远以在线实时查询为准**，不依赖离线文档。

```bash
# 列出所有可用视频模型
libtv model search --type video

# 查看特定模型的完整 schema（含 modeType、settings、rules）
libtv model <modelKey>
```

## 当前可用视频模型

> 以下列表为 `libtv model search --type video` 的快照（2026-06-19），以实际输出为准。

| modelKey | modelName | 说明 | VIP |
|----------|-----------|------|-----|
| `star-video2` | Seedance 2.0 VIP | 最强视频模型，15s音画同步 | ✅ |
| `star-video2-fast` | Seedance 2.0 Fast VIP | 最强视频模型快速版，15s音画同步 | ✅ |
| `happy-horse-1` | Happy Horse 1.0 | 阿里最新视频模型，支持多参生成 | |
| `kling-v3-omni` | Kling O3 | 视频编辑模型，参考一致性，音画同出，多镜头 | ✅ |
| `kling-video-o3` | Kling 3.0 | 视频生成模型，高质感，支持多镜头 | ✅ |
| `kling-video-o1` | Kling O1 | 可灵一代编辑模型，支持多模态输入 | ✅ |
| `wanx2.7-video` | Wan 2.7 | 全能参考，支持修改视频画面、剧情、环境 | |
| `wanxiang-v2-6` | Wan 2.6 | 音画同步，多机位镜头，最长15s | |
| `MiniMax-Hailuo-2.3` | Hailuo 2.3 | 善于表达动作、表情、镜头，更高质感 | |
| `MiniMax-Hailuo-2.3-Fast` | Hailuo 2.3 Fast | 善于表达动作、表情、镜头，更快速 | |
| `seedance-1.5-pro` | Seedance1.5 Pro | 音画同步，多机位镜头，最长12s | |
| `doubao-seedance-pro` | Seedance 1.0 Pro | 高精度提示词理解，40秒生成1080P | ✅ |
| `doubao-seedance-lite` | Seedance 1.0 Lite | 轻量快速，日常视频生成 | ✅ |
| `kling-v2-6` | Kling 2.6 | 视频生成，直出音画同步 | ✅ |
| `kling-v2-5-turbo-pro` | Kling 2.5 | 速度快、效果稳定、性价比高 | ✅ |
| `kling-2.1` | Kling 2.1 | 支持首尾帧，图生视频 | ✅ |
| `kling-v3-motion-control` | Kling3.0 动作迁移 | 动作控制，需输入1图+1视频 | ✅ |
| `midjourney-video` | MJ Video | 图生视频效果稳定 | ✅ |
| `MiniMax-Hailuo-o2` | Hailuo 02 | 画质稳定，适合运动特效场景 | |
| `viduq2` | Vidu Q2 | 多图主体参考 | ✅ |
| `viduq2-pro` | Vidu Q2 Pro | Vidu Q2 Pro | ✅ |
| `viduq2-turbo` | Vidu Q2 Turbo | Vidu Q2 Turbo | ✅ |
| `viduq3-pro` | Vidu Q3 Pro | 支持主体参考 | ✅ |
| `omnihuman-1.5` | OmniHuman 1.5 | 多模态数字人视频生成 | ✅ |
| `wanxiang-plus` | Wan 2.2 | 支持特效、玩法千变万化 | |
| `wanxiang-preview` | Wan 2.5 | 支持特效、直出音画同步 | |
| `pixverse-v5.5` | Pixverse V5.5 | 支持特效、玩法丰富 | ✅ |
| `pixverse-v5` | Pixverse V5 | 支持特效、玩法丰富 | ✅ |

## 模型锁定规则

- 此规则已在 workspace 规则中声明，所有视频生成任务必须遵守

## 常用模型对比

| 需求 | 推荐 modelKey | modeType | 说明 |
|------|--------------|----------|------|
| 分镜图→多模态参考视频 | `kling-v3-omni` | `mixed2video` | 参考图最多7张，支持音画同出 |
| 纯文生视频 | `star-video2` | `text2video` | 质量最佳 |
| 图生视频 | `kling-video-o3` | `singleImage2video` | 高质感 |
| 动效视频 | `star-video2-fast` | `mixed2video` | 快速出片 |

## modeType 常见枚举

| 枚举值 | 文案 | 说明 |
|--------|------|------|
| `text2video` | 文生视频 | 仅凭文字生成 |
| `singleImage2video` | 图生视频 | 单张参考图 |
| `frames2video` | 首尾帧 | 首帧+尾帧 |
| `image2video` | 图片参考 | 多图参考 |
| `videoEdit2video` | 视频编辑 | 编辑已有视频 |
| `audio2video` | 音频驱动 | 音频驱动画面 |
| `mixed2video` | 全能参考 | 图文混合参考 |

## schema 注意事项

每个模型的 schema 决定其支持哪些参数。关键字段：

| 字段 | 说明 | 取值示例 |
|------|------|----------|
| `ratio` | 画面比例 | `16:9` / `9:16` / `1:1` |
| `resolution` | 分辨率（部分模型支持） | `480p` / `720p` |
| `duration` | 时长（秒） | 各模型 min/max 不同 |
| `enableSound` | 是否生成音频 | `on` / `off` |
| `quality` | 生成品质 | `low` / `high` / `4k` |
| `modeType` | 生成模式 | 见上表 |
| `scene` | 业务场景（v1.1.1+） | 由 `libtv model <modelKey>` 决定 |
| `count` | 生成条数 | 通常为 `1` |
