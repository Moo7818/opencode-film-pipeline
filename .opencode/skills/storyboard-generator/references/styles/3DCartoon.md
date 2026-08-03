---
name: 3DCartoon
description: 3D卡通动画风格分镜图
keywords: 3D卡通, 皮克斯, 迪士尼, Pixar, Disney, 3D动画, 3D stylized, 三维动画, 3D拟人化, 3D喜剧
production_type: a 3D animated film storyboard
neg_1: live-action photography
neg_2: 2D illustration
neg_3: concept art
style_anchor: |
  Pixar/Disney style 3D character animation.
  Stylized but emotionally authentic character design.
  Premium 3D animation production quality.
  Expressive character performance with subtle detail.
style_footer: |
  Rich material rendering.
  Warm subsurface scattering on skin.
  Stylized but physically grounded lighting.

  The image should feel like a frame from a high-budget 3D animated feature film.
camera_language: |
  Use 3D animation film grammar:

  - intentional composition with depth layering
  - cinematic camera angles inspired by live-action
  - natural perspective with stylized proportions
  - dynamic framing for emotional impact
  - subtle focus transition
  - expressive character animation performance

  Do not make the frames look like separate illustrations.
  They must look like consecutive animation frames from the same production.
quality: |
  Premium 3D animation render quality.

  Stylized skin with subsurface scattering.
  Detailed fabric simulation.
  Rich material textures.
  Expressive character features.
  Cinematic depth of field.
  Professional color grading.
  High dynamic range.
avoid: |
  Photorealistic appearance.
  Live-action photography.
  2D flat illustration.
  Concept art.
  Game cinematic style.
  Real human skin.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Low-poly models.
  Flat shading.
  Watermarks.
  Logos.
  Unwanted text.
---

## 适用场景

通用设定中 `风格` / `风格质感` 字段包含以下关键词时匹配：

3D卡通、皮克斯、迪士尼、Pixar、Disney、3D动画、3D stylized、三维动画、3D拟人化、3D喜剧

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

3D卡通风格的氛围/色调/光线描述需转为英文动画渲染语义：

| 中文 | 英文 |
|------|------|
| 暖黄光 | Warm yellow lighting |
| 冷青白 | Cool cyan-white light |
| 高饱和 | High saturation, vibrant palette |
| 拟人化 | Anthropomorphic, stylized character features |
| 喜剧质感 | Comedy tone, expressive exaggeration |
| 电影级光照 | Cinematic lighting, film-quality illumination |
| 灶台自发光 | Self-emitting practical light from stove |
| 金属高光 | Metallic highlights, reflective surfaces |
| 情感余韵 | Lingering emotional warmth |
| 反差萌 | Cute contrast, charming juxtaposition |
