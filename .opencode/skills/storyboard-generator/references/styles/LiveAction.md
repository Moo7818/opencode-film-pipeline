---
name: LiveAction
description: 真人影视剧风格分镜图
keywords: 真人实拍, 真人摄影, 照片级真实, live-action, historical drama, 电影级质感, 真人影视剧
production_type: a live-action film pre-production cinematic frame
neg_1: concept art
neg_2: illustration
neg_3: a fantasy painting
style_anchor: |
  Live-action film.
  Real human actors.
  High-end cinema production quality.
  Historical realism combined with subtle artistic expression.
style_footer: |
  Cinematic contrast.
  Natural shadows.
  Real material textures.

  The image should feel like a frame from a high-budget live-action production.
camera_language: |
  Use professional film grammar:

  - intentional composition
  - realistic depth
  - natural camera perspective
  - cinematic framing
  - subtle focus transition
  - authentic actor performance

  Output exactly one single cinematic still that fills the entire canvas.
  Do not create multi-panel, grid, collage, comic-strip, or storyboard-sheet layouts.
  Continuity across shots is provided by reference images, not by packing multiple shots into one image.
quality: |
  Ultra realistic live-action cinema frame.

  Natural skin texture.
  Real fabric folds.
  Authentic material textures.
  Realistic environment.
  Subtle film grain.
  Professional color grading.
  High dynamic range but natural contrast.
avoid: |
  AI generated appearance.
  Digital painting.
  Concept art.
  3D render.
  Game cinematic style.
  Anime.
  Fantasy costume.
  Modern objects.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Plastic skin.
  Overly perfect faces.
  Artificial lighting.
  Excessive visual effects.
  Watermarks.
  Logos.
  Unwanted text.
  Subtitles or captions burned into the image.
  Lower-thirds or title cards.
  On-screen dialogue text.
  Shot numbers or frame labels on the image.
  Multi-panel layout.
  Comic grid or manga panels.
  Collage or contact sheet.
  2x2 or any N×M grid of shots.
  Split-screen.
  Storyboard sheet layout.
---

## 适用场景

通用设定中 `风格` / `风格质感` 字段包含以下关键词时匹配：

真人实拍、真人摄影、照片级真实、live-action、historical drama、电影级质感、真人影视剧

## 默认匹配

当通用设定未明确指定风格或无法匹配其他风格文件时，默认使用此风格。

## CINEMATIC QUALITY 段构建

Agent 从通用设定提取以下字段，与 front-matter 参数组合构建 CINEMATIC QUALITY 段：

```
CINEMATIC QUALITY:

{style_anchor}

{通用设定.全局氛围基调 → 英文}
{通用设定.全局色彩调性 → 英文}
{通用设定.全局光线基调 → 英文}

{style_footer}

Camera principles:
{camera_language}

{quality}
```

### 翻译指引

通用设定中的中文氛围/色调/光线描述需转为英文电影语义：

| 中文 | 英文 |
|------|------|
| 暖色调 | Warm color palette |
| 冷色调 | Cool color palette |
| 低饱和度 | Low saturation |
| 高对比 | High contrast |
| 自然光 | Natural daylight |
| 暖光 | Warm light |
| 顶光 | Overhead lighting |
| 侧光 | Side lighting |
| 逆光 | Backlight |
| 氛围光 | Atmospheric light |
| 柔和 | Soft, diffused |
| 戏剧性 | Dramatic |
| 写实 | Realistic |
| 怀旧 | Nostalgic |
