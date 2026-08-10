---
name: FlatIllustration
description: 扁平插画风分镜图
keywords: 扁平插画, 矢量插画, flat design, vector illustration, UI插画, 极简插画, flat art, minimalist illustration
production_type: a flat illustration style animation cinematic frame
neg_1: live-action photography
neg_2: 3D render
neg_3: realistic painting
style_anchor: |
  Flat illustration style animation.
  Clean vector-inspired shapes with minimal line work.
  Stylized geometric character design.
  Modern editorial illustration aesthetic.
style_footer: |
  Clean geometric shapes.
  Limited color palette with intentional accent colors.
  Minimal texture, smooth flat surfaces.

  The image should feel like a polished editorial illustration sequence.
camera_language: |
  Use flat illustration composition grammar:

  - clean graphic composition with intentional negative space
  - minimal depth, flat layering through color separation
  - geometric perspective with stylized proportions
  - bold color blocking for visual hierarchy
  - minimal camera movement, design-focused framing
  - simplified character performance through pose and silhouette

  Output exactly one single cinematic still that fills the entire canvas.
  Do not create multi-panel, grid, collage, comic-strip, or storyboard-sheet layouts.
quality: |
  Premium flat illustration quality.

  Clean vector-style shapes.
  Consistent character proportions.
  Controlled limited color palette.
  Smooth flat color fills.
  Intentional negative space.
  Modern editorial aesthetic.
avoid: |
  Photorealistic appearance.
  Live-action photography.
  3D render.
  CGI.
  Detailed texture.
  Gradient shading.
  Realistic lighting.
  Complex line work.
  Concept art.
  Anime style.
  Inconsistent character identity.
  Different clothing.
  Different locations.
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

扁平插画、矢量插画、flat design、vector illustration、UI插画、极简插画、flat art、minimalist illustration

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

扁平插画风格的氛围/色调/光线描述需转为英文插画语义：

| 中文 | 英文 |
|------|------|
| 扁平化 | Flat design, no depth shading |
| 矢量风 | Vector-style clean shapes |
| 极简 | Minimalist, reduced visual elements |
| 几何 | Geometric, shape-based composition |
| 莫兰迪色 | Morandi palette, muted desaturated tones |
| 高级灰 | Sophisticated gray palette |
| 留白 | Intentional negative space, breathing room |
| 色块 | Color blocking, solid flat fills |
| 层次感 | Layered through color separation, not depth |
| 编辑风 | Editorial illustration style, magazine aesthetic |
