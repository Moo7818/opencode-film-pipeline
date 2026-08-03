---
name: Stylized3DCGI
description: 风格化3D CGI动画风格分镜图
keywords: 风格化3D, 蜘蛛侠平行宇宙, Spider-Verse,Into the Spider-Verse, 3D混合2D, hybrid 3D, stylized CGI, 美漫风3D, 3D漫画风
production_type: a stylized 3D CGI animation storyboard
neg_1: photorealistic 3D
neg_2: flat 2D cartoon
neg_3: concept art
style_anchor: |
  Stylized 3D CGI animation with mixed-media aesthetic.
  3D rendering combined with 2D graphic elements and comic book techniques.
  Bold visual style breaking conventional CGI realism.
  Expressive non-photorealistic rendering with artistic intent.
style_footer: |
  Hybrid rendering combining 3D depth with 2D graphic overlays.
  Bold color blocking with halftone and comic texture effects.
  Stylized line work and rim lighting on 3D models.

  The image should feel like a frame from an innovative stylized 3D animated film.
camera_language: |
  Use stylized 3D animation film grammar:

  - dynamic comic-inspired composition with bold angles
  - creative depth of field with stylized focus transitions
  - dynamic camera movement with exaggerated perspective
  - mixed-media framing combining 3D depth and 2D graphic panels
  - snap zoom and speed line effects for dramatic impact
  - expressive character animation with exaggerated posing

  Do not make the frames look like separate illustrations.
  They must look like consecutive frames from the same stylized 3D production.
quality: |
  Premium stylized 3D animation quality.

  Hybrid 3D/2D rendering technique.
  Bold graphic color palette.
  Comic-inspired texture overlays.
  Consistent stylized character design.
  Dynamic lighting with non-realistic color shifts.
  Intentional visual texture and pattern.
avoid: |
  Photorealistic appearance.
  Pure 2D flat animation.
  Standard cartoon style.
  Concept art.
  Realistic skin textures.
  Flat shading without depth.
  Game engine look.
  Inconsistent character identity.
  Different clothing.
  Different locations.
  Bland lighting.
  Watermarks.
  Logos.
  Unwanted text.
---

## 适用场景

通用设定中 `风格` / `风格质感` 字段包含以下关键词时匹配：

风格化3D、蜘蛛侠平行宇宙、Spider-Verse、Into the Spider-Verse、3D混合2D、hybrid 3D、stylized CGI、美漫风3D、3D漫画风

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

风格化3D CGI风格的氛围/色调/光线描述需转为英文渲染语义：

| 中文 | 英文 |
|------|------|
| 漫画风 | Comic book style, halftone dots, graphic overlays |
| 混合媒介 | Mixed media, 3D rendering with 2D graphic elements |
| 速度线 | Speed lines, motion graphic effects |
| 半调网点 | Halftone pattern, Ben-Day dots texture |
| 粗描边3D | Bold outline rendering on 3D models |
| 色彩偏移 | Color channel offset, chromatic aberration effect |
| 动态构图 | Dynamic composition, Dutch angles, forced perspective |
| 波普艺术 | Pop art inspired bold color and pattern |
| 丝网印刷 | Screen printing texture, posterized color |
| 抽帧 | Stepped animation, intentional frame rate reduction effect |
