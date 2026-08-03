---
name: Western2D
description: 欧美2D卡通动画风格分镜图
keywords: 欧美卡通, 美式动画, Cartoon Network, Adventure Time, Rick and Morty, Western cartoon, 2D cartoon, flat cartoon, 卡通网络
production_type: a Western-style 2D cartoon animation storyboard
neg_1: live-action photography
neg_2: 3D render
neg_3: anime style
style_anchor: |
  Western 2D cartoon animation style.
  Bold outline character design with flat color fills.
  Expressive exaggerated character performance.
  Playful and dynamic visual comedy composition.
style_footer: |
  Bold clean outlines.
  Flat vibrant color palette.
  Graphic shape-driven composition.

  The image should feel like a frame from a high-quality Western 2D animated series.
camera_language: |
  Use Western cartoon animation grammar:

  - bold graphic composition with strong silhouettes
  - dynamic camera angles for comedic or dramatic effect
  - flat staging with minimal depth layering
  - exaggerated perspective for emotional impact
  - snap-cut composition style
  - expressive character posing and exaggeration

  Do not make the frames look like separate illustrations.
  They must look like consecutive animation frames from the same cartoon series.
quality: |
  Premium Western 2D animation quality.

  Bold consistent character outlines.
  Flat clean color fills.
  Expressive character posing.
  Graphic background design.
  Consistent character model sheets.
  Vibrant but controlled color palette.
avoid: |
  Photorealistic appearance.
  Live-action photography.
  3D render.
  CGI.
  Anime style.
  Japanese cel animation.
  Concept art.
  Realistic textures.
  Gradient shading.
  Soft lighting.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Watermarks.
  Logos.
  Unwanted text.
---

## 适用场景

通用设定中 `风格` / `风格质感` 字段包含以下关键词时匹配：

欧美卡通、美式动画、Cartoon Network、Adventure Time、Rick and Morty、Western cartoon、2D cartoon、flat cartoon、卡通网络

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

欧美2D卡通风格的氛围/色调/光线描述需转为英文动画语义：

| 中文 | 英文 |
|------|------|
| 扁平色彩 | Flat color fills, no gradient shading |
| 粗描边 | Bold outlines, thick stroke weight |
| 鲜艳 | Vibrant, saturated cartoon palette |
| 夸张表情 | Exaggerated facial expressions, pushed posing |
| 喜剧 | Comedy tone, playful visual humor |
| 冒险 | Adventure tone, dynamic action composition |
| 几何构图 | Graphic geometric composition, shape-driven staging |
| 平面化 | Flat staging, minimal depth perspective |
| 高对比 | High contrast, bold color blocking |
| 波普风 | Pop-art inspired color and pattern |
