# 横版七视图 Prompt 模板（备选）

> **按需加载**：此文件仅当角色设定或调用方明确要求横版七视图（如需要表情参考）时才读取。默认使用 `rules/common.md` 中的竖版三视图模板，无需加载本文件。

Prompt 必须严格使用下方模板，逐字替换 `{}` 占位符。**禁止**自己编写新的 Prompt 格式，**禁止**改为单视图/单角度描述。

与竖版三视图的差异：aspectRatio 为 `16:9`，包含 7 个视图（左半侧半身近景 + 右上表情三连图 + 右下全身三视图），而非 3 个视图。

```
Create a {opening_decl}.

This is a {opening_type},
not {opening_neg_1},
not {opening_neg_2},
not {opening_neg_3}.

{identity_ref}

The image contains seven photographic references of the same character.

Layout:

The image is divided into two equal halves: the left side occupies exactly 50% of the frame width, and the right side occupies exactly 50% of the frame width.

Left side:
A cinematic portrait of the character,
from the top of the head down to the elbow joints,
showing the face, head, neck, shoulders, chest, and upper torso down to just above the navel,
with both arms visible down to the elbow joints,
filling the entire left half of the frame.
The face and upper body are large and prominent,
photographed like a {layout_portrait_style} with dramatic intimacy.

Upper right:
The upper one-third of the right side contains three facial expression references:
happy, sad, angry.
The same character identity must be preserved across all expressions.
These are also close-up headshots, face only.

Lower right:
The lower two-thirds of the right side contains three full-body costume continuity references showing the character's body and costume only:
front view, side view, back view.
The head and face must not be visible in these three costume references.
Frame the shots from the neck down,
focusing on costume silhouette, garment structure, fabric layers, body proportions, and costume details.

The character identity, hairstyle, and costume continuity must remain consistent with the portrait and expression references,
but the lower-right costume views should intentionally exclude the head area.

The character must maintain:
same identity, same costume, same body proportions, same hairstyle continuity in the visible references.

The reference should look like {output_format},
not a designed poster or graphic layout.

Character:
{character}

Appearance:
{appearance}

Hair and Costume:
{hair_costume}

Photography style:
{photo_style}
Shot at 85mm f4 with moderate depth of field, face and upper body sharply in focus, background gently blurred, maintaining clear detail from face to mid-torso.

Lighting:
{lighting}

Background:
{background}

Avoid:
{avoid_style},
text, labels, captions, logos, watermarks, frames, decorative elements, graphic layout, beauty retouching, perfect symmetry.
```

## 横版七视图与竖版三视图的差异对照

| 维度 | 竖版三视图（默认） | 横版七视图（备选） |
|------|-------------------|-------------------|
| aspectRatio | `9:16` | `16:9` |
| 视图数 | 3 | 7 |
| 构图 | 上下分屏（top 50% / bottom 50%） | 左右分屏（left 50% / right 50%） |
| 上/左侧 | 半身近景肖像（头顶至肘部） | 半身近景肖像（头顶至肘部） |
| 下/右侧 | 全身正面 + 背面两视图并排（无头部） | 右上：表情三连图（happy/sad/angry）；右下：全身前/侧/后三视图（无头部） |
| 表情参考 | 无 | 有（3 种表情） |

> 参数取值来源、`{appearance}` 段构建规则、`{character}` 段构建规则等与竖版三视图完全相同，见 `rules/common.md` 的「参数说明」段。
