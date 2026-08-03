---
name: InkAnimation
description: 水墨风人物动画风格分镜图
keywords: 水墨, 水墨风, 水墨动画, 国画, ink-wash, Chinese ink painting, 水墨风人物动画
production_type: a Chinese ink-wash animation storyboard
neg_1: live-action photography
neg_2: 3D render
neg_3: concept art
style_anchor: |
  Traditional Chinese ink-wash painting animation.
  Hand-painted brush stroke aesthetic.
  Xuan paper texture as visual foundation.
  Artistic expression through ink gradient and negative space.
style_footer: |
  Calligraphic ink gradients.
  Natural ink bleeding and diffusion.
  Balanced composition between painted subjects and empty space.

  The image should feel like a hand-crafted ink-wash animation frame.
camera_language: |
  Use traditional animation film grammar:

  - intentional composition with negative space
  - layered depth through ink density
  - natural perspective with artistic license
  - cinematic framing inspired by classical Chinese painting
  - subtle focus through ink gradation
  - expressive character animation

  Do not make the frames look like separate illustrations.
  They must look like consecutive animation frames from the same production.
quality: |
  Authentic ink-wash painting texture.

  Natural brush stroke variation.
  Organic ink diffusion.
  Xuan paper fiber texture.
  Hand-painted atmosphere.
  Consistent ink density.
  Artistic color restraint.
avoid: |
  Photorealistic appearance.
  Live-action photography.
  3D render.
  CGI.
  Digital painting.
  Concept art.
  Game cinematic style.
  Anime style.
  Plastic textures.
  Modern objects.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Over-saturated colors.
  Artificial lighting.
  Watermarks.
  Logos.
  Unwanted text.
---

## 适用场景

通用设定中 `风格` / `风格质感` 字段包含以下关键词时匹配：

水墨、水墨风、水墨动画、国画、ink-wash、Chinese ink painting、水墨风人物动画

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

水墨风格的氛围/色调/光线描述需转为英文水墨画语义：

| 中文 | 英文 |
|------|------|
| 灰褐主调 | Earthy gray-brown dominant tone |
| 低饱和度 | Low saturation, muted palette |
| 留白 | Negative space, intentional empty areas |
| 宣纸纹理 | Xuan paper texture, rice paper grain |
| 淡墨 | Light ink wash, diluted brush strokes |
| 浓墨 | Dense ink, heavy brush strokes |
| 水墨晕染 | Ink bleeding and diffusion |
| 远山 | Distant mountains in faded ink |
| 写意 | Expressive freehand brushwork |
| 工笔 | Fine brushwork detail |
| 留白空间 | Breathing space, unpainted areas |
