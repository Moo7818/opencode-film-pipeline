---
name: Realistic3DCGI
description: 写实3D CGI风格分镜图
keywords: 写实3D, 电影特效, CGI, realistic 3D, VFX, photoreal CGI, 3D写实, 电影级3D, 3D特效
production_type: a photorealistic 3D CGI film cinematic frame
neg_1: 2D illustration
neg_2: flat cartoon
neg_3: concept art
style_anchor: |
  Photorealistic 3D CGI animation.
  Film-quality visual effects rendering.
  Physically based materials and lighting.
  Cinematic realism achieved through 3D rendering technology.
style_footer: |
  Physically accurate light transport.
  Realistic material response under complex lighting.
  Subtle atmospheric effects and volumetric depth.

  The image should feel like a frame from a high-budget CGI film or VFX sequence.
camera_language: |
  Use cinematic 3D CGI film grammar:

  - physically accurate camera simulation with real lens characteristics
  - realistic depth of field and focus control
  - dynamic camera movement with stabilized compositing
  - cinematic framing matching live-action film standards
  - subtle camera shake for realism when appropriate
  - naturalistic character animation with motion capture quality

  Output exactly one single cinematic still that fills the entire canvas.
  Do not create multi-panel, grid, collage, comic-strip, or storyboard-sheet layouts.
quality: |
  Photorealistic 3D CGI render quality.

  Physically based material rendering.
  Accurate light propagation and shadows.
  Realistic skin with subsurface scattering.
  Detailed environment with high-resolution textures.
  Atmospheric depth with volumetric effects.
  Professional cinematic color grading.
  High dynamic range.
avoid: |
  2D flat illustration.
  Cartoon style.
  Anime style.
  Concept art.
  Low-poly models.
  Flat shading.
  Visible wireframes.
  Game engine artifacts.
  Plastic-looking skin.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Artificial lighting.
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

写实3D、电影特效、CGI、realistic 3D、VFX、photoreal CGI、3D写实、电影级3D、3D特效

## 与 LiveAction 的区别

LiveAction 是真人实拍影视风格，强调真实演员和实景拍摄；Realistic3DCGI 是 3D 渲染达到写实效果的风格，可以是全 CGI 角色或 VFX 合成场景。

## 与 3DCartoon 的区别

3DCartoon 是皮克斯/迪士尼风格化 3D 动画，角色夸张卡通化；Realistic3DCGI 追求照片级真实感，角色和环境都接近真实。

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

写实3D CGI风格的氛围/色调/光线描述需转为英文渲染语义：

| 中文 | 英文 |
|------|------|
| 物理渲染 | Physically based rendering, PBR materials |
| 次表面散射 | Subsurface scattering on skin and organic surfaces |
| 全局光照 | Global illumination, realistic light bounce |
| 体积光 | Volumetric lighting, god rays, atmospheric depth |
| 动作捕捉 | Motion capture quality character animation |
| 影视级 | Film-quality, cinematic production grade |
| 材质精度 | High-resolution material detail, accurate texture mapping |
| 环境遮蔽 | Ambient occlusion, contact shadows |
| 色调映射 | Tone mapping, cinematic color science |
| 景深 | Depth of field, cinematic focus control |
