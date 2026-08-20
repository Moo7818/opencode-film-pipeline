#!/usr/bin/env python3
"""分镜图任务表校验器 — 校验分镜图_任务表.json 的引用一致性

校验项：
1. JSON 语法正确性
2. 模型必须在允许集合内（nano-banana-2 / nano-banana-pro）
3. 分辨率必须在允许集合内（2K / 4K）
4. 画面比例必须为 16:9
5. mode 必须为 sequential 或 batch
6. sequential 任务必须有 id、group、scene；batch 视觉锚点任务必须有 id、scene、scene_name
7. 视觉锚点任务（batch 及 sequential）必须有 shot_range 字段（如 '1-7'），同场内多阶段 shot_range 不得重叠
8. sequential 场级参考帧链完整：同 scene 排序后第1帧无 depends_on，其后 depends_on=直接前帧
9. depends_on 引用的 id 必须存在于同场任务中
9. 含 depends_on 的 sequential 任务 images 必须包含 {{PREV_OUTPUT}}
10. batch 任务不得含 depends_on 或 {{PREV_OUTPUT}}；sequential 视觉锚点任务：首阶段无 depends_on 且不得含 {{PREV_OUTPUT}}，非首阶段必须含 depends_on（指向同场前一阶段任务）且 images 必须含 {{PREV_OUTPUT}}
11. images 路径必须为具体文件（非目录）或 {{PREV_OUTPUT}}
12. prompt 中 Image N: 映射块数量与 images 数组一致
13. Image N: 编号必须从 1 开始连续递增
14. 参考图优先级：首帧 角色→场景→道具→风格；后续帧 角色→前帧→场景→道具→风格
15. {{PREV_OUTPUT}} 须在全部角色之后、风格之前
16. prompt 包含必需的段落标题
17. FRAME DETAIL 包含 Purpose 和 Feeling 字段
18. 禁止焦距参数（35mm/50mm/85mm）
19. 禁止 "storyboard" 关键词（会导致宫格图生成）
20. 禁止 "frame N of M" 帧数声明（会导致宫格图生成）
21. 禁止网格/拼贴/分屏等布局词汇
22. 禁止未解析的模板占位符（{...} 格式）
23. cast 字段必填（可为 []）；每个 cast 名须匹配角色参考路径文件名
24. 角色参考数量 = Character Identity Anchor 数量 = cast 长度
25. visual_anchor batch 的身份锁必须包含 actor/person 连续性、脸部身份绝对优先、历史冲突处理和绑定式角色写法
26. visual_anchor batch 的背景人物必须包含 `not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`
27. prompt 必须含单帧画布声明
28. TEXT POLICY 必须含禁字幕约束
29. AVOID 必须含 multi-panel/layout 与 empty/lifeless pose 禁令；字幕仅由 TEXT POLICY 检查
30. （告警，不阻塞）元约束残留检测：prompt 不得含「提示词净化规范」11 类必删元约束（段落放置/编排指令、Decision rule、括号标签机制解释、编写者脑补禁令、编译器/流水线说明、中文事实保留指令、占位符机制解释、锚点职责定位从句与职责块、Mapping 内机制解释、道具配对说明括号）

CLI:
  python validate_task_table.py --check 视觉锚点_任务表.json --mode anchor
  python validate_task_table.py --check 分镜图_任务表.json --mode storyboard
  python validate_task_table.py --check 分镜图_任务表.json --verbose
  # --mode auto（默认）按任务特征自动识别：含 shot_range/scene_name → anchor
"""

import json
import os
import re
import sys
from pathlib import Path


# ─── 校验规则 ─────────────────────────────────────────────

# 允许模型集合（校验按集合放行；REQUIRED_MODEL 旧常量已废弃删除，避免与集合误导）
ALLOWED_MODELS = {"nano-banana-2", "nano-banana-pro"}

# 允许分辨率集合
ALLOWED_IMAGE_SIZES = {"2K", "4K"}

VALID_ASPECT_RATIOS = {"16:9"}

PREV_OUTPUT_PLACEHOLDER = "{{PREV_OUTPUT}}"

# 参考帧模式：前帧紧接角色之后，权重高于场景/道具/风格
REF_PRIORITY_FIRST = ["角色", "场景", "道具", "风格"]
REF_PRIORITY_SUBSEQUENT = ["角色", "前帧", "场景", "道具", "风格"]

REQUIRED_SECTIONS = [
    # SCENE CONTINUITY 允许 "SCENE CONTINUITY:" 或 "SCENE CONTINUITY (REFERENCE-FRAME MODE):"
    "SCENE CONTINUITY",
    "REFERENCE IMAGE MAPPING:",
    "FRAME DETAIL:",
    "TEXT POLICY:",
    "CINEMATIC QUALITY:",
    "AVOID:",
]

FOCAL_LENGTH_PATTERN = re.compile(r"\b(?:35|50|85)mm\b", re.IGNORECASE)

STORYBOARD_PATTERN = re.compile(r"\bstoryboard\b", re.IGNORECASE)

FRAME_COUNT_PATTERN = re.compile(r"frame\s+\d+\s+of\s+\d+", re.IGNORECASE)

# 宫格/拼贴：含模型常见诱发词
GRID_PATTERN = re.compile(
    r"\b(?:grid|multi-frame|multiple frames|multi-panel|multipanel|"
    r"collage|contact sheet|split-?screen|comic strip|manga panel|"
    r"four-panel|2\s*[x×]\s*2|3\s*[x×]\s*3|panel layout|tiled layout)\b|"
    r"网格|宫格|多格|四宫格|拼贴|分屏|连镜图",
    re.IGNORECASE,
)

UNRESOLVED_PLACEHOLDER_PATTERN = re.compile(r"\{(?![{])[^}]+\}")

# 单帧声明：至少命中一组
SINGLE_FRAME_PATTERNS = [
    re.compile(r"exactly one image", re.IGNORECASE),
    re.compile(r"single (?:photographic )?still", re.IGNORECASE),
    re.compile(r"fills the entire canvas", re.IGNORECASE),
    re.compile(r"single frame only", re.IGNORECASE),
]

# TEXT POLICY 禁字幕
SUBTITLE_BAN_IN_TEXT_POLICY = re.compile(
    r"(?:no\s+subtitles|without\s+subtitles|ban[^\n]{0,40}subtitle|"
    r"hard ban on burned-in|burned-in graphics)",
    re.IGNORECASE,
)

# AVOID 段应出现的关键禁令（小写匹配）
AVOID_MUST_CONTAIN_ANY = {
    "multi_panel": ["multi-panel", "multipanel", "comic grid", "collage", "2x2"],
    "empty_poses": ["empty or lifeless", "lifeless character poses"],
}

CHAR_ANCHOR_PATTERN = re.compile(
    r"Image\s+(\d+)\s*:\s*Character Identity Anchor",
    re.IGNORECASE,
)

IDENTITY_LOCK_PATTERN = re.compile(r"IDENTITY\s+LOCK", re.IGNORECASE)

# 只把实际提到 unreferenced/background character 的 prompt 视为背景人物场景。
# 单独的 "background people" 可能只是时代错位禁令，不应让纯空镜被强制加降权句。
BACKGROUND_CHARACTER_SIGNAL_PATTERN = re.compile(
    r"(?:unreferenced\s*/\s*background(?:\s+(?:character|characters|person|people))?|"
    r"unreferenced|background[- ](?:only|character|characters|person)|"
    r"unnamed\s+(?:background\s+)?(?:character|person|people))",
    re.IGNORECASE,
)

BACKGROUND_WEIGHT_REQUIREMENTS = (
    "not a referenced character",
    "background-only",
    "smaller visual weight",
    "secondary placement",
    "not a main character",
    "not a focal point",
    "never become the visual focus",
)


# ─── 元约束残留检测（「提示词净化规范」11 类必删项，告警不阻塞）─────

# 每项 = (类别名, 正则)。命中即告警：该内容属于智能体编写规范，
# 不应出现在最终提交给生图模型的 prompt 中（EP11 验证：删除后生成质量正常）。
META_CONSTRAINT_PATTERNS = [
    (
        "段落放置/编排指令",
        re.compile(
            r"write this block after[^\n.]*|in cast/images order|"
            r"in the order of the (?:cast|images) array",
            re.IGNORECASE,
        ),
    ),
    (
        "Decision rule 决策说明",
        re.compile(r"decision rule\s*:", re.IGNORECASE),
    ),
    (
        "括号标签机制解释",
        re.compile(r"binding content label|not a casting instruction", re.IGNORECASE),
    ),
    (
        "编写者脑补禁令",
        re.compile(
            r"do not let the role label[^\n.]*|infer new (?:faces|ages|hairstyles|smiles|body types)",
            re.IGNORECASE,
        ),
    ),
    (
        "编译器/流水线说明",
        re.compile(
            r"prompt compiler|the compiler (?:assembles|translates)|"
            r"does not embellish|source fidelity rule",
            re.IGNORECASE,
        ),
    ),
    (
        "中文事实保留指令",
        re.compile(
            r"keep chinese character names[^\n.]*|do not translate or rewrite them",
            re.IGNORECASE,
        ),
    ),
    (
        "占位符机制解释",
        re.compile(
            r"prev[_-]?output placeholder[^\n.]*|"
            r"the output from the previous (?:phase|frame) serves as|"
            r"immediately preceding frame[^\n.]*\(may be prior group\)",
            re.IGNORECASE,
        ),
    ),
    (
        "锚点职责定位从句",
        re.compile(
            r"a single establishing image that locks the scene[^\n.]*",
            re.IGNORECASE,
        ),
    ),
    (
        "锚点职责块",
        re.compile(r"anchor frame responsibilities\s*:", re.IGNORECASE),
    ),
    (
        "Mapping 内机制解释",
        re.compile(r"describes duty and source content", re.IGNORECASE),
    ),
    (
        "道具配对说明括号",
        re.compile(r"same props\s*\((?:每个道具|every prop|each prop)[^)]{0,100}\)", re.IGNORECASE),
    ),
]


def check_meta_residuals(data: dict) -> list[str]:
    """元约束残留检测（告警级，不阻塞）。

    扫描各 task 的 prompt，检测「提示词净化规范」必删 11 类元约束残留。
    命中仅告警：这些内容属于编写规范而非模型输入，删除后生成质量正常；
    校验通过与 exit code 仍由 errors 决定，告警不改变。
    """
    warnings = []
    if not isinstance(data, dict):
        return warnings
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return warnings
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        tid = task.get("id") or f"#{i + 1}"
        prompt = task.get("prompt", "")
        if not isinstance(prompt, str) or not prompt:
            continue
        for name, pattern in META_CONSTRAINT_PATTERNS:
            m = pattern.search(prompt)
            if m:
                snippet = m.group(0).strip()
                if len(snippet) > 70:
                    snippet = snippet[:70] + "…"
                warnings.append(
                    f"任务{tid}: 检测到元约束残留 [{name}]：{snippet!r}。"
                    "prompt 必须为纯画面描述语言，请按「提示词净化规范」删除该内容"
                )
    return warnings


# ─── 校验逻辑 ─────────────────────────────────────────────

def detect_table_type(data: dict) -> str:
    """按任务特征识别任务表类型：视觉锚点（任务含 shot_range/scene_name）或分镜图"""
    if not isinstance(data, dict):
        return "unknown"
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return "unknown"
    for t in tasks:
        if isinstance(t, dict) and ("shot_range" in t or "scene_name" in t):
            return "anchor"
    return "storyboard"


def _classify_ref(path: str) -> str:
    """根据路径判断参考图类型"""
    if path == PREV_OUTPUT_PLACEHOLDER:
        return "前帧"
    if "角色参考图" in path or "角色设定" in path:
        return "角色"
    if "场景参考图" in path or "场景设定" in path:
        return "场景"
    if "道具参考图" in path or "道具设定" in path:
        return "道具"
    if "风格" in path:
        return "风格"
    return "未知"


def _is_file_path(path: str) -> bool:
    """判断路径是否为文件路径（而非目录路径）或 {{PREV_OUTPUT}} 占位符"""
    if path == PREV_OUTPUT_PLACEHOLDER:
        return True
    if path.endswith("\\") or path.endswith("/"):
        return False
    basename = os.path.basename(path)
    if "." not in basename:
        return False
    return True


def _extract_reference_section(prompt: str) -> str:
    """提取 REFERENCE IMAGE MAPPING 段落（从 REFERENCE IMAGE MAPPING: 到下一个段标题）"""
    start = prompt.find("REFERENCE IMAGE MAPPING:")
    if start < 0:
        return ""
    end_markers = ["FRAME DETAIL:", "TEXT POLICY:", "CINEMATIC QUALITY:"]
    end = len(prompt)
    for marker in end_markers:
        pos = prompt.find(marker, start)
        if pos > 0:
            end = min(end, pos)
    return prompt[start:end]


def _extract_section(prompt: str, header: str, end_markers: list[str]) -> str:
    start = prompt.find(header)
    if start < 0:
        return ""
    end = len(prompt)
    for marker in end_markers:
        pos = prompt.find(marker, start + len(header))
        if pos > 0:
            end = min(end, pos)
    return prompt[start:end]


def _extract_image_refs(prompt: str) -> list[int]:
    """提取 REFERENCE IMAGES 段中的 Image {N}: 编号列表"""
    section = _extract_reference_section(prompt)
    if not section:
        return []
    matches = re.findall(r"Image\s+(\d+)\s*:", section, re.IGNORECASE)
    return [int(m) for m in matches]


def _count_char_anchors(prompt: str) -> int:
    section = _extract_reference_section(prompt)
    if not section:
        return 0
    return len(CHAR_ANCHOR_PATTERN.findall(section))


def _check_visual_anchor_identity_lock(
    prompt: str, images: list, cast: list | None, mode: str,
    is_visual_anchor: bool = False,
) -> list[str]:
    """校验 visual_anchor 的身份锁是否位于场景构建之前。

    仅对视觉锚点任务执行：batch 模式全部按视觉锚点处理；
    sequential 模式仅视觉锚点任务（含 shot_range/scene_name 字段）强制此段。
    分镜图 sequential 模板不强制此段，避免把两种参考图模式的输出契约混在一起。
    """
    if mode != "batch" and not is_visual_anchor:
        return []

    char_images = [p for p in images if _classify_ref(p) == "角色"]
    errors = []
    background_signal = BACKGROUND_CHARACTER_SIGNAL_PATTERN.search(prompt)
    if not char_images and not cast:
        if background_signal:
            low_prompt = prompt.lower()
            for phrase in BACKGROUND_WEIGHT_REQUIREMENTS:
                if phrase not in low_prompt:
                    errors.append(
                        "unreferenced/background character 缺少英文降权硬约束 "
                        f"[{phrase}]"
                    )
        return errors

    lock_match = IDENTITY_LOCK_PATTERN.search(prompt)
    scene_pos = prompt.lower().find("scene continuity")
    if not lock_match:
        errors.append(
            "visual_anchor prompt 缺少 IDENTITY LOCK — HIGHEST PRIORITY 段"
        )
        return errors

    lock_pos = lock_match.start()
    if scene_pos >= 0 and lock_pos > scene_pos:
        errors.append(
            "IDENTITY LOCK 必须位于 SCENE CONTINUITY 之前，先锁身份再构建空间"
        )

    lock_end = scene_pos if scene_pos >= 0 and scene_pos > lock_pos else len(prompt)
    lock_block = prompt[lock_pos:lock_end]
    low_lock = lock_block.lower()
    if "highest priority" not in low_lock:
        errors.append("IDENTITY LOCK 缺少 Highest priority 语义")
    if "reference priority" not in low_lock:
        errors.append("IDENTITY LOCK 缺少 Reference priority 顺序声明")
    if "sole identity source" not in low_lock:
        errors.append("IDENTITY LOCK 必须明确参考图是角色的 sole identity source")
    if "same specific person" not in low_lock:
        errors.append("IDENTITY LOCK 必须明确是参考图中的同一个具体人物")

    required_lock_phrases = {
        "recognizable as the same actor/person": "必须包含 actor/person 连续性：recognizable as the same actor/person",
        "actor continuity": "必须明确 actor continuity",
        "identity wins every conflict": "Reference priority 必须明确身份胜过环境/历史造型等冲突",
        "face identity has absolute priority": "必须声明 face identity has absolute priority",
        "historical appearance conflicts with reference identity": "必须包含历史外观与参考身份冲突时的决策规则",
        "preserve the reference identity": "历史冲突处理必须保留 reference identity",
        "modify only wardrobe, hairstyle, and setting": "历史冲突处理必须只修改 wardrobe、hairstyle、setting",
        "same people from the reference images": "必须声明参考角色是 same people from the reference images",
        "not similar-looking replacements": "必须禁止 similar-looking replacements",
        "do not alter facial identity": "必须禁止改变 facial identity",
        "facial structure": "必须禁止改变 facial structure",
        "skin features": "必须禁止改变 skin features",
        "body proportions": "必须禁止改变 body proportions",
        "change only clothing and hairstyle required": "必须声明 Change only clothing and hairstyle required",
        "must not create a new person": "必须声明服饰/发型/环境改变不得 create a new person",
        "do not generate a generic": "必须禁止按历史/职业原型生成 generic 角色",
    }
    for phrase, message in required_lock_phrases.items():
        if phrase not in low_lock:
            errors.append(f"IDENTITY LOCK 缺少 actor continuity 语义：{message}")

    # 每个角色图都必须在最前身份锁中有对应的 Reference Image N 绑定。
    image_indexes = [i + 1 for i, p in enumerate(images) if _classify_ref(p) == "角色"]
    for image_index in image_indexes:
        if not re.search(rf"Reference\s+Image\s+{image_index}\b", lock_block, re.IGNORECASE):
            errors.append(
                f"IDENTITY LOCK 缺少角色参考图 Reference Image {image_index} 的逐一绑定"
            )
        if not re.search(
            rf"(?:Reference\s+Image\s+{image_index}\s+character|"
            rf"the\s+character\s+from\s+Reference\s+Image\s+{image_index})",
            lock_block,
            re.IGNORECASE,
        ):
            errors.append(
                f"IDENTITY LOCK 缺少 Reference Image {image_index} 的绑定式角色写法"
                "（应先写图像，再写中文角色名/职责）"
            )
        if not re.search(
            rf"(?:Reference\s+Image\s+{image_index}\s+character|"
            rf"the\s+character\s+from\s+Reference\s+Image\s+{image_index})"
            rf"[\s\S]{{0,300}}recognizable\s+as\s+the\s+same\s+actor/person",
            lock_block,
            re.IGNORECASE,
        ):
            errors.append(
                f"IDENTITY LOCK 缺少 Reference Image {image_index} 的 actor/person recognizable 连续性句"
            )

    if re.search(r"\bALL\s+characters\b", prompt, re.IGNORECASE):
        errors.append(
            "不得使用 ALL characters 混合 referenced characters 与 unreferenced/background characters"
        )

    mapping = _extract_reference_section(prompt).lower()
    if char_images and "highest priority" not in mapping:
        errors.append("角色映射块缺少 Reference priority / Highest priority 语义")
    if any(_classify_ref(path) == "场景" for path in images) and "second priority" not in mapping:
        errors.append("场景映射块缺少 Second priority 语义")
    if any(_classify_ref(path) == "道具" for path in images) and "third priority" not in mapping:
        errors.append("道具映射块缺少 Third priority 语义")
    if any(_classify_ref(path) == "风格" for path in images) and "fourth priority" not in mapping:
        errors.append("风格映射块缺少 Fourth priority 语义")

    if background_signal:
        for phrase in BACKGROUND_WEIGHT_REQUIREMENTS:
            if phrase not in prompt.lower():
                errors.append(
                    "unreferenced/background character 缺少英文降权硬约束 "
                    f"[{phrase}]"
                )

    return errors


def _check_required_sections(prompt: str) -> list[str]:
    missing = []
    for section in REQUIRED_SECTIONS:
        if section not in prompt:
            missing.append(section)
    return missing


def _check_frame_purpose(prompt: str) -> list[str]:
    errors = []
    start = prompt.find("FRAME DETAIL:")
    if start < 0:
        return errors

    end_markers = ["TEXT POLICY:", "CINEMATIC QUALITY:", "AVOID:"]
    end = len(prompt)
    for marker in end_markers:
        pos = prompt.find(marker, start)
        if pos > 0:
            end = min(end, pos)

    frame_block = prompt[start:end]
    if not re.search(r"^Purpose\s*:", frame_block, re.MULTILINE | re.IGNORECASE):
        errors.append("FRAME DETAIL 缺少 Purpose 字段")
    if not re.search(r"^Feeling\s*:", frame_block, re.MULTILINE | re.IGNORECASE):
        errors.append("FRAME DETAIL 缺少 Feeling 字段")
    return errors


def _check_focal_length(prompt: str) -> list[str]:
    matches = FOCAL_LENGTH_PATTERN.findall(prompt)
    if matches:
        return [f"发现焦距参数 {matches}，禁止使用 35mm/50mm/85mm"]
    return []


def _strip_negative_and_avoid(prompt: str) -> str:
    """去掉 AVOID 段，以及否定句中的禁词，避免把禁令本身误判为违规。

    保留需检查的正文（OPENING 里 'not a multi-panel' 是否定声明，应剔除匹配）。
    """
    # 去掉整段 AVOID（禁令列表会枚举 multi-panel 等布局词）
    avoid_start = prompt.find("AVOID:")
    body = prompt if avoid_start < 0 else prompt[:avoid_start]

    # 去掉 TEXT POLICY 中的禁令枚举（含 subtitle 等）
    tp = body.find("TEXT POLICY:")
    if tp >= 0:
        cq = body.find("CINEMATIC QUALITY:", tp)
        end = cq if cq >= 0 else len(body)
        body = body[:tp] + body[end:]

    # 行级：明确否定/禁止的行不参与宫格/storyboard 阳性检测
    kept = []
    for line in body.splitlines():
        low = line.lower().strip()
        if not low:
            kept.append(line)
            continue
        if low.startswith(("not ", "no ", "never ", "do not ", "don't ", "avoid ")):
            continue
        if re.search(
            r"\b(?:not a|not an|no |never |without |ban |forbid|禁止|不要|而非)\b",
            low,
        ):
            continue
        if "—" in line and any(
            k in low for k in ("multi-panel", "grid", "collage", "storyboard", "split-screen")
        ):
            # OPENING 长句枚举禁布局
            continue
        kept.append(line)
    return "\n".join(kept)


def _check_storyboard_keyword(prompt: str) -> list[str]:
    body = _strip_negative_and_avoid(prompt)
    matches = STORYBOARD_PATTERN.findall(body)
    if matches:
        return [f'发现禁止关键词 "storyboard" {matches}，使用 "cinematic frame" 替代']
    return []


def _check_frame_count(prompt: str) -> list[str]:
    matches = FRAME_COUNT_PATTERN.findall(prompt)
    if matches:
        return [f"发现帧数声明 {matches}，禁止声明总帧数"]
    return []


def _check_grid_pattern(prompt: str) -> list[str]:
    body = _strip_negative_and_avoid(prompt)
    matches = GRID_PATTERN.findall(body)
    if matches:
        return [f"发现网格/拼贴相关词汇 {matches}，禁止 multi-panel/grid/collage/宫格等"]
    return []


def _check_unresolved_placeholders(prompt: str) -> list[str]:
    matches = UNRESOLVED_PLACEHOLDER_PATTERN.findall(prompt)
    if matches:
        return [f"发现未解析的模板占位符 {matches}，所有 {{...}} 占位符必须被替换为实际值"]
    return []


def _check_single_frame_declaration(prompt: str) -> list[str]:
    if any(p.search(prompt) for p in SINGLE_FRAME_PATTERNS):
        return []
    return [
        "缺少单帧画布声明：prompt 须含 "
        "'exactly one image' / 'single frame only' / 'fills the entire canvas' 等"
    ]


def _check_text_policy_subtitle_ban(prompt: str) -> list[str]:
    section = _extract_section(
        prompt,
        "TEXT POLICY:",
        ["CINEMATIC QUALITY:", "AVOID:"],
    )
    if not section:
        return ["缺少 TEXT POLICY 段，无法校验禁字幕"]
    if SUBTITLE_BAN_IN_TEXT_POLICY.search(section):
        return []
    # 宽松：段内同时出现 no 与 subtitle
    low = section.lower()
    if "subtitle" in low and ("no " in low or "not " in low or "ban" in low or "never" in low):
        return []
    return [
        "TEXT POLICY 缺少禁字幕约束（须含 No subtitles / Hard ban on burned-in graphics 等）"
    ]


def _check_avoid_bans(prompt: str) -> list[str]:
    section = _extract_section(prompt, "AVOID:", [])
    if not section:
        return ["缺少 AVOID 段"]
    low = section.lower()
    errors = []
    for key, options in AVOID_MUST_CONTAIN_ANY.items():
        if not any(opt in low for opt in options):
            errors.append(
                f"AVOID 段缺少 {key} 类禁令（须含其一: {', '.join(options)}）"
            )
    return errors


def _cast_name_in_path(name: str, path: str) -> bool:
    """角色中文名是否出现在参考图路径/文件名中"""
    if not name or not path:
        return False
    base = os.path.basename(path)
    # 直接包含；或去空白后包含
    if name in base or name in path:
        return True
    return False


def _validate_cast(task: dict, images: list, prompt: str, label: str, filename: str) -> list[str]:
    errors = []
    if "cast" not in task:
        errors.append(
            f"{label} ({filename}): 缺少 cast 字段"
            f"（本帧在场具名角色列表；纯空镜写 []）"
        )
        cast = None
    else:
        cast = task.get("cast")
        if not isinstance(cast, list):
            errors.append(f"{label} ({filename}): cast 必须为数组")
            cast = None
        else:
            for i, c in enumerate(cast):
                if not isinstance(c, str) or not c.strip():
                    errors.append(f"{label} ({filename}): cast[{i}] 必须为非空字符串")

    char_images = [p for p in images if _classify_ref(p) == "角色"]
    anchor_count = _count_char_anchors(prompt)

    if cast is not None and isinstance(cast, list):
        if len(cast) != len(char_images):
            errors.append(
                f"{label} ({filename}): cast 长度 {len(cast)} != 角色参考图数量 {len(char_images)}"
            )
        for name in cast:
            if not isinstance(name, str):
                continue
            if not any(_cast_name_in_path(name.strip(), p) for p in char_images):
                errors.append(
                    f"{label} ({filename}): cast 角色 [{name}] 未在 images 角色路径文件名中找到对应参考图"
                )

    if len(char_images) != anchor_count:
        errors.append(
            f"{label} ({filename}): 角色参考图数量 {len(char_images)} != "
            f"Character Identity Anchor 数量 {anchor_count}"
        )

    if cast is not None and isinstance(cast, list) and len(cast) != anchor_count:
        errors.append(
            f"{label} ({filename}): cast 长度 {len(cast)} != "
            f"Character Identity Anchor 数量 {anchor_count}"
        )

    return errors


def validate_task_table(data: dict, verbose=True, table_type: str = "auto") -> list[str]:
    """校验分镜图任务表，返回错误列表。

    table_type: anchor（视觉锚点_任务表）/ storyboard（分镜图_任务表）/ auto（自动识别）。
    显式指定类型与实际不符时报错；anchor 表内所有任务按视觉锚点规则校验，
    storyboard 表内任务禁止携带 shot_range/scene_name 字段。
    """
    errors = []

    if not isinstance(data, dict):
        return ["顶层结构不是对象"]

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        return ["缺少 tasks 数组或为空"]

    # 解析任务表类型（显式指定优先；不符即为错误，避免两套模式的规则互相产生噪音）
    detected = detect_table_type(data)
    if table_type == "auto":
        table_type = detected
    elif table_type != detected:
        errors.append(
            f"--mode {table_type} 与任务表实际类型不符（检测为 {detected}）。"
            "anchor=视觉锚点_任务表（任务含 shot_range/scene_name），"
            "storyboard=分镜图_任务表"
        )
    is_anchor_table = table_type == "anchor"

    mode = data.get("mode", "")
    if mode not in {"sequential", "batch"}:
        errors.append(
            f"mode [{mode or '(未设置)'}] 必须为 sequential 或 batch"
        )

    id_to_scene = {}
    id_to_task = {}
    for t in tasks:
        tid = t.get("id")
        if tid:
            id_to_scene[tid] = t.get("scene", "")
            id_to_task[tid] = t

    # sequential 模式建立场级参考帧链（分镜图），并校验视觉锚点阶段链
    # （shot_range 必填/不重叠、首阶段无 depends_on）；visual_anchor 的 batch 模式每场独立，不得误套链式约束
    if mode == "sequential":
        errors.extend(_validate_scene_chains(tasks))
        errors.extend(_validate_visual_anchor_sequential(tasks))

    for i, task in enumerate(tasks):
        task_id = task.get("id", "?")
        label = f"任务{task_id}" if task_id != "?" else f"任务{i+1}"
        filename = task.get("filename", "?")
        prompt = task.get("prompt", "")
        images = task.get("images", [])
        model = task.get("model", "")
        image_size = task.get("imageSize", "")
        depends_on = task.get("depends_on", "")
        group = task.get("group", "")
        scene = task.get("scene", "")

        # visual_anchor 任务特征：含 shot_range / scene_name 字段（分镜图任务无）。
        # anchor 表：缺这些字段的任务报错，且整表按视觉锚点规则校验；
        # storyboard 表：携带这些字段即报错（两套 schema 不得混用）。
        has_anchor_fields = "shot_range" in task or "scene_name" in task
        is_visual_anchor = is_anchor_table or has_anchor_fields
        if is_anchor_table and not has_anchor_fields:
            errors.append(
                f"{label} ({filename}): anchor 表中该任务缺少 shot_range/scene_name 字段"
                "（视觉锚点任务必填）"
            )
        if not is_anchor_table and has_anchor_fields:
            errors.append(
                f"{label} ({filename}): 分镜图任务表不得含 shot_range/scene_name 字段"
                "（这些属于视觉锚点_任务表）"
            )

        # 1. 模型校验
        effective_model = model or data.get("model", "")
        if effective_model and effective_model not in ALLOWED_MODELS:
            errors.append(
                f"{label} ({filename}): 模型 [{effective_model}] 无效，"
                f"允许值: {' / '.join(sorted(ALLOWED_MODELS))}"
            )

        # 2. 分辨率校验
        effective_size = image_size or data.get("imageSize", "")
        if effective_size and effective_size not in ALLOWED_IMAGE_SIZES:
            errors.append(
                f"{label} ({filename}): 分辨率 [{effective_size}] 无效，"
                f"允许值: {' / '.join(sorted(ALLOWED_IMAGE_SIZES))}"
            )

        # 3. 画面比例校验
        aspect = task.get("aspectRatio", "") or data.get("aspectRatio", "")
        if aspect and aspect not in VALID_ASPECT_RATIOS:
            errors.append(
                f"{label} ({filename}): 画面比例 [{aspect}] 无效，"
                f"仅支持 {' 或 '.join(sorted(VALID_ASPECT_RATIOS))}"
            )

        # 4. id 字段校验
        if not task.get("id"):
            errors.append(f"{label} ({filename}): 缺少 id 字段（任务表必填）")

        # 5. 模式专属字段校验
        if mode == "sequential" and not group:
            errors.append(f"{label} ({filename}): 缺少 group 字段（sequential 模式必填）")
        if is_visual_anchor and not task.get("scene_name"):
            errors.append(f"{label} ({filename}): 缺少 scene_name 字段（visual_anchor 任务必填）")
        if is_visual_anchor and not task.get("shot_range"):
            errors.append(f"{label} ({filename}): 缺少 shot_range 字段（visual_anchor 任务必填，如 '1-7'）")

        # 5b. scene 字段校验
        if not scene:
            errors.append(f"{label} ({filename}): 缺少 scene 字段（任务表必填）")

        # 6. depends_on 引用校验（场级串行：depends_on 必须在同一场内）
        if depends_on:
            if mode == "batch":
                errors.append(f"{label} ({filename}): batch 视觉锚点任务不得含 depends_on")
            elif depends_on not in id_to_task:
                errors.append(f"{label} ({filename}): depends_on [{depends_on}] 引用的任务不存在")
            elif id_to_scene.get(depends_on) != scene:
                errors.append(
                    f"{label} ({filename}): depends_on [{depends_on}] 引用的任务不在同一场"
                    f"（场级串行链要求同场）"
                )

        # 7. {{PREV_OUTPUT}} 一致性校验
        has_prev_output = PREV_OUTPUT_PLACEHOLDER in images
        if mode == "batch" and has_prev_output:
            errors.append(f"{label} ({filename}): batch 视觉锚点任务不得含 {PREV_OUTPUT_PLACEHOLDER}")
        if mode == "sequential" and depends_on and not has_prev_output:
            errors.append(f"{label} ({filename}): 含 depends_on 但 images 中缺少 {PREV_OUTPUT_PLACEHOLDER}")
        if mode == "sequential" and not depends_on and has_prev_output:
            errors.append(f"{label} ({filename}): 无 depends_on 但 images 中含 {PREV_OUTPUT_PLACEHOLDER}")

        # 8. images 路径校验
        if len(images) == 0:
            errors.append(
                f"{label} ({filename}): images 数组为空——分镜图必须引用角色/场景参考图。"
                f"请在任务表 JSON 中为每个 task 填写具体的参考图文件路径"
            )
        else:
            for j, img_path in enumerate(images):
                if not _is_file_path(img_path):
                    errors.append(
                        f"{label} ({filename}): images[{j+1}] [{img_path}] 是目录路径，"
                        f"必须为具体文件或 {PREV_OUTPUT_PLACEHOLDER}"
                    )

        # 9. 引用一致性校验 — Image N: 编号
        image_refs = _extract_image_refs(prompt)
        if len(image_refs) != len(images):
            errors.append(
                f"{label} ({filename}): 提示词含 {len(image_refs)} 个 Image N: 映射块，"
                f"但 images 数组有 {len(images)} 个，不一致"
            )
        elif image_refs:
            expected = list(range(1, len(images) + 1))
            if image_refs != expected:
                errors.append(
                    f"{label} ({filename}): Image N: 编号不连续或顺序错乱，"
                    f"期望 {expected}，实际 {image_refs}"
                )

        # 10. 必需段落校验
        missing_sections = _check_required_sections(prompt)
        if missing_sections:
            errors.append(
                f"{label} ({filename}): 缺少必需段落: {', '.join(missing_sections)}"
            )

        # 11. FRAME Purpose 校验
        for pe in _check_frame_purpose(prompt):
            errors.append(f"{label} ({filename}): {pe}")

        # 12. 焦距参数校验
        for fe in _check_focal_length(prompt):
            errors.append(f"{label} ({filename}): {fe}")

        # 13. storyboard 关键词校验
        for se in _check_storyboard_keyword(prompt):
            errors.append(f"{label} ({filename}): {se}")

        # 14. 帧数声明校验
        for fce in _check_frame_count(prompt):
            errors.append(f"{label} ({filename}): {fce}")

        # 15. 网格布局词汇校验
        for ge in _check_grid_pattern(prompt):
            errors.append(f"{label} ({filename}): {ge}")

        # 16. 未解析占位符校验
        for pe in _check_unresolved_placeholders(prompt):
            errors.append(f"{label} ({filename}): {pe}")

        # 17-19. cast / 角色锚 / 单帧 / 字幕 / AVOID
        for ce in _validate_cast(task, images, prompt, label, filename):
            errors.append(ce)

        for ie in _check_visual_anchor_identity_lock(
            prompt, images, task.get("cast"), mode, is_visual_anchor
        ):
            errors.append(f"{label} ({filename}): {ie}")

        for se in _check_single_frame_declaration(prompt):
            errors.append(f"{label} ({filename}): {se}")

        for te in _check_text_policy_subtitle_ban(prompt):
            errors.append(f"{label} ({filename}): {te}")

        for ae in _check_avoid_bans(prompt):
            errors.append(f"{label} ({filename}): {ae}")

        # 优先级排序：首帧无前帧；后续帧 角色→前帧→场景→道具→风格
        has_prev = PREV_OUTPUT_PLACEHOLDER in images
        priority_order = (
            REF_PRIORITY_SUBSEQUENT if mode == "sequential" and has_prev
            else REF_PRIORITY_FIRST
        )
        type_indices = {}
        for j, img_path in enumerate(images):
            ref_type = _classify_ref(img_path)
            if ref_type == "未知":
                continue
            type_indices.setdefault(ref_type, []).append(j)

        last_max_idx = -1
        for ref_type in priority_order:
            if ref_type not in type_indices:
                continue
            min_idx = min(type_indices[ref_type])
            if min_idx <= last_max_idx:
                errors.append(
                    f"{label} ({filename}): {ref_type}参考图出现在前序类型之前，"
                    f"优先级排序错误（期望顺序 {' → '.join(priority_order)}；"
                    f"{ref_type}最早位置 {min_idx} <= 前序最晚位置 {last_max_idx}）"
                )
            last_max_idx = max(last_max_idx, max(type_indices[ref_type]))

        # 前帧位置：全部角色之后、风格之前
        if has_prev:
            prev_idx = images.index(PREV_OUTPUT_PLACEHOLDER)
            char_indices = type_indices.get("角色", [])
            style_indices = type_indices.get("风格", [])
            if char_indices and prev_idx < max(char_indices):
                errors.append(
                    f"{label} ({filename}): {PREV_OUTPUT_PLACEHOLDER} 必须在全部角色参考图之后"
                )
            if style_indices and prev_idx > min(style_indices):
                errors.append(
                    f"{label} ({filename}): {PREV_OUTPUT_PLACEHOLDER} 必须在风格参考图之前"
                    f"（禁止垫在风格之后）"
                )

        # 角色与场景须在风格之前
        real_types = [_classify_ref(p) for p in images if p != PREV_OUTPUT_PLACEHOLDER]
        if "风格" in real_types:
            style_idx = real_types.index("风格")
            pre_style = real_types[:style_idx]
            if "角色" not in pre_style and (task.get("cast") or []):
                errors.append(f"{label} ({filename}): 角色参考图不在风格参考之前")
            if "场景" not in pre_style:
                errors.append(f"{label} ({filename}): 场景参考图不在风格参考之前")

    return errors


def _parse_group_shot(task_id: str) -> tuple[int, int]:
    """从 id '组-镜' 解析排序键；失败则 (0, 0)"""
    if not task_id or "-" not in str(task_id):
        return (0, 0)
    parts = str(task_id).split("-", 1)
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return (0, 0)


def _validate_scene_chains(tasks: list) -> list[str]:
    """校验每场内参考帧链：排序后首帧无依赖，其后 depends_on 等于直接前帧"""
    errors = []
    by_scene: dict[str, list] = {}
    for t in tasks:
        scene = str(t.get("scene", "") or "")
        if not scene:
            continue
        by_scene.setdefault(scene, []).append(t)

    for scene, scene_tasks in by_scene.items():
        ordered = sorted(
            scene_tasks,
            key=lambda t: (
                _parse_group_shot(t.get("id", "")),
                str(t.get("group", "")),
                str(t.get("id", "")),
            ),
        )
        if not ordered:
            continue

        first = ordered[0]
        first_id = first.get("id", "?")
        if first.get("depends_on"):
            errors.append(
                f"场{scene}: 链首帧 [{first_id}] 不应有 depends_on"
                f"（参考帧链每场仅一个无依赖起点）"
            )
        if PREV_OUTPUT_PLACEHOLDER in first.get("images", []):
            errors.append(
                f"场{scene}: 链首帧 [{first_id}] 不应包含 {PREV_OUTPUT_PLACEHOLDER}"
            )

        for prev, curr in zip(ordered, ordered[1:]):
            prev_id = prev.get("id", "")
            curr_id = curr.get("id", "?")
            dep = curr.get("depends_on", "")
            if dep != prev_id:
                errors.append(
                    f"场{scene}: 参考帧链断裂 — [{curr_id}] 的 depends_on "
                    f"应为直接前帧 [{prev_id}]，实际为 [{dep or '(空)'}]"
                )
            if PREV_OUTPUT_PLACEHOLDER not in curr.get("images", []):
                errors.append(
                    f"场{scene}: [{curr_id}] 在链中非首帧，images 必须含 "
                    f"{PREV_OUTPUT_PLACEHOLDER}"
                )

    return errors


def _parse_shot_range(shot_range) -> tuple[int, int] | None:
    """解析 shot_range 字符串 '1-7' → (1, 7)；格式非法或 start>end 返回 None"""
    if not isinstance(shot_range, str):
        return None
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", shot_range)
    if not m:
        return None
    start, end = int(m.group(1)), int(m.group(2))
    if start > end:
        return None
    return (start, end)


def _validate_visual_anchor_sequential(tasks: list) -> list[str]:
    """校验 sequential 视觉锚点任务：shot_range 必填、同场多阶段不重叠、首阶段无 depends_on。

    视觉锚点任务以含 shot_range / scene_name 字段为特征（分镜图任务无这些字段）。
    同场阶段链：首阶段（按 shot_range 起始排序第一个）不得有 depends_on；
    depends_on 同场与存在性由主循环逐任务校验。
    """
    errors = []
    va_tasks = [t for t in tasks if "shot_range" in t or "scene_name" in t]
    if not va_tasks:
        return errors

    # 按场分组
    by_scene: dict[str, list] = {}
    for t in va_tasks:
        scene = str(t.get("scene", "") or "")
        by_scene.setdefault(scene, []).append(t)

    for scene, scene_tasks in by_scene.items():
        ranges = []
        for t in scene_tasks:
            tid = t.get("id", "?")
            parsed = _parse_shot_range(t.get("shot_range"))
            if parsed is None:
                errors.append(
                    f"任务{tid}: visual_anchor 任务 shot_range [{t.get('shot_range') or '(未设置)'}] 无效，"
                    f"须为 '起始-结束' 数字区间（如 '1-7'）"
                )
                continue
            ranges.append((tid, parsed))

        # 同场多阶段 shot_range 不得重叠
        for i in range(len(ranges)):
            for j in range(i + 1, len(ranges)):
                id_a, (sa, ea) = ranges[i]
                id_b, (sb, eb) = ranges[j]
                if sa <= eb and sb <= ea:
                    errors.append(
                        f"场{scene}: 任务 [{id_a}] 与 [{id_b}] 的 shot_range 重叠"
                        f"（{id_a} 覆盖 {sa}-{ea}，{id_b} 覆盖 {sb}-{eb}），同场多阶段不得重叠"
                    )

        # 首阶段无 depends_on：同场按 (shot_range 起始, group, id) 排序后第一个任务
        if scene_tasks:
            ordered = sorted(
                scene_tasks,
                key=lambda t: (
                    _parse_shot_range(t.get("shot_range")) or (0, 0),
                    str(t.get("group", "")),
                    str(t.get("id", "")),
                ),
            )
            first = ordered[0]
            if first.get("depends_on"):
                errors.append(
                    f"场{scene}: 首阶段锚点 [{first.get('id', '?')}] 不应有 depends_on"
                    f"（首阶段是阶段链起点，depends_on 仅用于同场非首阶段）"
                )

    return errors


def format_report(errors, verbose=True):
    """格式化校验报告（ASCII，避免 Windows GBK 控制台炸）"""
    if not errors:
        return "[PASS] 分镜图任务表校验通过"
    lines = [f"[FAIL] 发现 {len(errors)} 个问题："]
    for e in errors:
        lines.append(f"  - {e}")
    return "\n".join(lines)


# ─── CLI 入口 ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="分镜图任务表校验器")
    parser.add_argument("--check", metavar="task_table.json", required=True,
                        help="校验分镜图任务表 JSON")
    parser.add_argument("--mode", choices=["anchor", "storyboard", "auto"], default="auto",
                        help="任务表类型：anchor=视觉锚点_任务表，storyboard=分镜图_任务表，"
                             "auto=按任务特征自动识别（默认）。显式指定可防止两套模式规则互窜")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    check_path = Path(args.check)
    if not check_path.exists():
        print(f"[ERROR] 文件不存在: {check_path}", file=sys.stderr)
        sys.exit(1)

    with open(check_path, "r", encoding="utf-8-sig") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        # 友好报错：指名位置 + 上下文片段，不再倾倒 Traceback
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(f"[ERROR] 任务表 JSON 损坏: {check_path} — 第 {e.lineno} 行第 {e.colno} 列: {e.msg}")
        lines = raw.splitlines()
        if 0 < e.lineno <= len(lines):
            line = lines[e.lineno - 1]
            c = max(0, e.colno - 1)
            print(f"  上下文: ...{line[max(0, c - 100):c + 100]}...")
        # 常见事故：TEXT POLICY 精确文字用 ASCII 双引号包裹（未转义 \"）
        if re.search(r'(?:Exact|readable) text:\s*"(?![^"]*\\)', raw):
            print(
                "  [HINT] 检测到 Exact text / readable text 后的裸 ASCII 双引号："
                "prompt 内包裹精确文字请改用全角引号「」（无需 JSON 转义），"
                "或将其转义为 \\\"（见 phase-2-common.md「引号铁律」）"
            )
        sys.exit(1)

    errors = validate_task_table(data, verbose=args.verbose, table_type=args.mode)
    warnings = check_meta_residuals(data)

    # 解析最终类型（供摘要展示；类型不符时以检测值为准）
    resolved_type = detect_table_type(data)

    if args.verbose:
        tasks = data.get("tasks", [])
        mode = data.get("mode", "(未设置)")
        model = data.get("model", "(未设置)")
        print(f"\n执行模式: {mode}")
        print(f"全局模型: {model}")
        print(f"任务总数: {len(tasks)}")
        for i, task in enumerate(tasks):
            task_id = task.get("id", "?")
            filename = task.get("filename", "?")
            depends_on = task.get("depends_on", "")
            group = task.get("group", "")
            scene = task.get("scene", "")
            cast = task.get("cast", "(缺省)")
            model = task.get("model", "")
            image_size = task.get("imageSize", "")
            images = task.get("images", [])
            prompt = task.get("prompt", "")
            ref_count = _extract_image_refs(prompt)
            print(f"\n--- {task_id} ({filename}) ---")
            print(f"  场: {scene}")
            print(f"  组: {group}")
            print(f"  cast: {cast}")
            print(f"  依赖: {depends_on or '(场首帧)'}")
            print(f"  模型: {model or '(继承全局)'}")
            print(f"  分辨率: {image_size or '(继承全局)'}")
            print(f"  images 数量: {len(images)}")
            print(f"  Image N: 映射块: {ref_count}")
            print(f"  Character Anchors: {_count_char_anchors(prompt)}")
            for j, img in enumerate(images):
                ref_type = _classify_ref(img)
                display = img if img == PREV_OUTPUT_PLACEHOLDER else os.path.basename(img)
                print(f"    [{j+1}] ({ref_type}) {display}")
        print()

    # 强制 UTF-8 输出，避免 GBK 下中文路径报错
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(format_report(errors, args.verbose))
    if warnings:
        print(f"\n[WARN] 元约束残留告警 {len(warnings)} 条（提示词净化规范，不阻塞通过）：")
        for w in warnings:
            print(f"  - {w}")

    # 一行式摘要：会话无需回读全量报告即可获知结果
    tasks_list = data.get("tasks", []) if isinstance(data, dict) else []
    scene_count = len({
        str(t.get("scene")) for t in tasks_list
        if isinstance(t, dict) and t.get("scene")
    })
    print(
        f"[SUMMARY] type={resolved_type} | tasks={len(tasks_list)} | "
        f"scenes={scene_count} | errors={len(errors)} | warnings={len(warnings)} | "
        f"result={'PASS' if not errors else 'FAIL'}"
    )
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
