---
name: GameCinematic
description: 游戏CG过场动画风格分镜图
keywords: 游戏CG, 游戏过场, 最终幻想, GTA, Rockstar, FF, game cinematic, game cutscene, 游戏预告片, 3A游戏, AAA game
production_type: a game cinematic cutscene storyboard
neg_1: flat 2D illustration
neg_2: concept art
neg_3: amateur animation
style_anchor: |
  AAA game cinematic cutscene quality.
  High-end real-time rendering aesthetic with film-quality post-processing.
  Stylized realism balanced between photorealism and game art direction.
  Premium game production value with dramatic character performance.
style_footer: |
  Game engine quality rendering with cinematic post-processing.
  Stylized realistic materials with optimized artistic detail.
  Dramatic lighting design for emotional storytelling.

  The image should feel like a frame from a high-budget AAA game cinematic.
camera_language: |
  Use game cinematic film grammar:

  - dramatic cinematic camera angles optimized for screen composition
  - smooth controlled camera movement with in-engine stabilization
  - depth of field with bokeh shaped for visual appeal
  - dynamic framing matching AAA game cutscene standards
  - subtle motion blur for cinematic feel
  - high-quality character animation with performance capture detail

  Do not make the frames look like separate illustrations.
  They must look like consecutive cutscene frames from the same game production.
quality: |
  AAA game cinematic render quality.

  Stylized realistic character rendering.
  High-detail environment with optimized texture quality.
  Dramatic cinematic lighting.
  Post-processing quality color grading.
  Screen-ready composition.
  High dynamic range with tone mapping.
avoid: |
  Flat 2D illustration.
  Cartoon style.
  Anime style.
  Concept art.
  Low-poly models.
  Visible game UI elements.
  HUD overlays.
  Wireframe models.
  Unrendered assets.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Plastic skin.
  Watermarks.
  Logos.
  Unwanted text.
---

## 适用场景

通用设定中 `风格` / `风格质感` 字段包含以下关键词时匹配：

游戏CG、游戏过场、最终幻想、GTA、Rockstar、FF、game cinematic、game cutscene、游戏预告片、3A游戏、AAA game

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

游戏CG风格的氛围/色调/光线描述需转为英文游戏渲染语义：

| 中文 | 英文 |
|------|------|
| 3A级 | AAA production quality, premium game visual standard |
| 实时渲染 | Real-time rendering aesthetic with ray-traced reflections |
| 性能捕捉 | Performance capture, facial animation detail |
| 后处理 | Post-processing, bloom, color grading, screen-space effects |
| 美术风格 | Art direction, stylized realism game aesthetic |
| 镜头语言 | Cinematic camera language, film-quality cutscene direction |
| 体积雾 | Volumetric fog, atmospheric scattering |
| 屏幕空间反射 | Screen-space reflections, SSR |
| 景深虚化 | Depth of field bokeh, cinematic focus falloff |
| 动态模糊 | Motion blur, cinematic frame motion |
| 伽马校正 | Gamma corrected color, sRGB color space |
| HUD无 | No HUD, no UI overlays, clean cinematic frame |
