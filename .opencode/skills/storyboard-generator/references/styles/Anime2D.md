---
name: Anime2D
description: 日系2D动画风格分镜图
keywords: 日系动漫, 二次元, anime, 新海诚, 京阿尼, 吉卜力2D, 番剧, 日漫, Japanese animation, cel animation
production_type: a Japanese anime-style 2D animation cinematic frame
neg_1: live-action photography
neg_2: 3D render
neg_3: concept art
style_anchor: |
  Traditional Japanese anime-style 2D hand-drawn animation.
  Clean cel-shaded character art with expressive line work.
  Cinematic anime composition inspired by theatrical anime films.
  Emotionally driven visual storytelling with stylized backgrounds.
style_footer: |
  Painterly anime background art.
  Clean character linework with flat color shading.
  Expressive eye animation and micro-expression detail.

  The image should feel like a frame from a high-budget theatrical anime film.
camera_language: |
  Use anime film grammar:

  - intentional composition with dynamic angles
  - layered depth through background painting and character separation
  - dramatic perspective with artistic license
  - cinematic framing inspired by live-action techniques
  - selective focus through color and line density
  - expressive character performance with exaggerated emotion

  Output exactly one single cinematic still that fills the entire canvas.
  Do not create multi-panel, grid, collage, comic-strip, or storyboard-sheet layouts.
  Continuity across shots is provided by reference images, not by packing multiple shots into one image.
quality: |
  Premium theatrical anime production quality.

  Clean cel-shaded character art.
  Painterly background with atmospheric depth.
  Consistent character proportions.
  Expressive facial animation.
  Cinematic color grading.
  Dynamic lighting effects.
avoid: |
  Photorealistic appearance.
  Live-action photography.
  3D render.
  CGI.
  Digital painting with realistic textures.
  Concept art.
  Game cinematic style.
  Western cartoon style.
  Plastic textures.
  Modern objects in historical settings.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Over-rendered shading.
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

日系动漫、二次元、anime、新海诚、京阿尼、吉卜力2D、番剧、日漫、Japanese animation、cel animation

## 与 InkAnimation 的区别

InkAnimation 是中国传统水墨动画风格，强调笔墨晕染和留白；Anime2D 是日系赛璐璐动画风格，强调干净线条和扁平色彩。

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

日系动漫风格的氛围/色调/光线描述需转为英文动画语义：

| 中文 | 英文 |
|------|------|
| 赛璐璐 | Cel-shaded, flat color rendering |
| 新海诚风 | Makoto Shinkai inspired luminous skies and detailed backgrounds |
| 京阿尼风 | Kyoto Animation inspired soft lighting and delicate character detail |
| 热血 | Passionate, high-energy dramatic tone |
| 治愈 | Healing, gentle, warm emotional atmosphere |
| 暗黑 | Dark, moody, psychological atmosphere |
| 空灵 | Ethereal, otherworldly atmosphere |
| 逆光 | Backlit, rim lighting effect |
| 眼神光 | Eye catchlight, expressive gaze |
| 樱花/光斑 | Sakura petals / light particles floating in air |
| 云层光影 | Dramatic cloud formations with volumetric light |
| 情绪色调 | Emotional color grading, mood-driven palette |
