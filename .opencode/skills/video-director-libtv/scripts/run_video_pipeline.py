#!/usr/bin/env python3
"""视频生成管线编排器 — 计划 / 构建 / 运行 三阶段分离

依赖: libtv >= 1.1.1（group --run 为阻塞等待命令，CLI 内部完成轮询）

画布模型:
  - 每个项目对应一个 libtv 工作区（workspace）
  - 每个剧集对应一个 libtv 画布（canvas）
  - 画布 UUID 来源：调用方（video-director agent）先经 meta_query(scope=config)
    查 episodes.{剧集号}.canvas_uuid；无则创建画布后经 meta_update_config 写回，
    再以 --canvas-uuid 显式传入本脚本（--build/--run 必填，脚本不读任何持久化配置）

三阶段模式（互斥，必选其一）:
  --plan   生成本次执行计划：各组参考图/音色的自动匹配结果 + 可直接复制的
           --refs/--voice-refs 建议参数。纯本地解析，不调用 libtv，无需画布/模型。
  --build  并发上传参考素材 → 并发创建 video 节点（upsert）→ 幂等建组。不运行生成。
  --run    运行已有分组（阻塞等待终态 JSON）→ 解析终态提取 URL → 并发下载。
           与 --build 分开调用，避免单次工具调用被长时间生成阻塞。

用法示例:
  # 1) 计划（可选但推荐：agent 审核参考图自动匹配结果，无需通读组文件）
  python run_video_pipeline.py --plan \
    --project "项目名" --episode EP01 --groups 7 8 9 \
    --storyboard-mode detailed --reference-image-mode visual_anchor

  # 2) 构建（未显式 --refs 的组按组内容自动匹配参考图；--no-auto-refs 关闭）
  python run_video_pipeline.py --build \
    --project "项目名" --episode EP01 \
    --canvas-uuid <画布UUID> --model "Seedance 2.0 VIP" \
    --storyboard-mode detailed --reference-image-mode visual_anchor \
    --groups 7 8 9 --ratio 16:9 --resolution 480p --sound on \
    --refs "组7:场景_现代南京,角色_一岛"

  # 3) 运行 + 下载（单独调用；须先 --build）
  python run_video_pipeline.py --run \
    --project "项目名" --episode EP01 --canvas-uuid <画布UUID> \
    --groups 7 8 9 --download

设计原则:
  - 计划/执行分离: 确定性匹配（素材名出现在组内容中 + 最长子串去重）在
    --plan 预演、--build 默认自动生效；agent 经 --refs 显式覆盖，经 --plan 审核
  - 并发: 上传 / 建节点 / 下载经线程池并发（--max-workers，默认 4，上限 8）
  - 幂等: 节点 create 失败自动回退默认子命令 update（upsert，重跑改参安全）；
    建组用 libtv group "<名>"（有则绑定、无则新建），重跑不产生 _v2
    注意: update 走 --left ensure 语义，不删除未列出的旧边；需清理旧连线时
    手动 libtv node <名> --left-rm <旧上游> 或删除节点重建
  - 状态缓存: 画布节点缓存落盘 .opencode/cache/video-director/<canvas_uuid>.json，
    重跑跳过已上传素材；--refresh-cache 强制重建缓存
  - ! 选角参考图（{角色名}_选角.png）自动过滤，禁止用于视频生成
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

CONSTRAINT = "画面严禁出现任何字幕，无配乐"
SEPARATOR = "---"

# 本地默认值：仅限可选参数回退；model 等关键参数由模式校验强制要求
CONFIG_DEFAULTS = {
    "count": 1,
    "ratio": "16:9",
    "resolution": "480p",
    "enableSound": "on",
}

REFERENCE_TYPE_PATHS = {
    "角色": "全局依赖/角色设定/角色参考图",
    "场景": "全局依赖/场景设定/场景参考图",
    "道具": "全局依赖/道具设定/道具参考图",
    "风格": "前期采样/风格",
}

# 分镜图目录（剧集级，需要 episode 参数拼接）
STORYBOARD_IMAGE_PATH = "分镜/分镜图"

# 视觉锚点图目录（剧集级，需要 episode 参数拼接）
VISUAL_ANCHOR_PATH = "分镜/视觉锚点"

# 画布节点缓存目录（工作区根下）
CACHE_SUBDIR = os.path.join(".opencode", "cache", "video-director")

MAX_WORKERS_DEFAULT = 4
MAX_WORKERS_LIMIT = 8


# ============================================================
# 基础执行层
# ============================================================

def run_libtv(args_list):
    """执行 libtv 子命令。

    返回 (result, stderr)：成功时 result 为解析后的 JSON（或原始 stdout 字符串），
    stderr 为空串；失败时 result 为 None，stderr 为截断后的错误信息。
    """
    try:
        result = subprocess.run(
            ["libtv"] + args_list, capture_output=True, text=True, encoding="utf-8"
        )
    except FileNotFoundError:
        return None, "libtv 命令不存在（未安装或不在 PATH）"
    if result.returncode != 0:
        return None, (result.stderr or result.stdout or "未知错误")[:400]
    out = (result.stdout or "").strip()
    if not out:
        return "", ""
    try:
        return json.loads(out), ""
    except json.JSONDecodeError:
        return out, ""


def run_concurrent(tasks, max_workers, on_done=None):
    """并发执行任务。tasks: [(key, fn), ...]，返回 {key: fn返回值}。

    on_done(key, result) 在主线程随完成随回调（用于打印进度）。
    任务内抛异常会被捕获为 {"error": ...}，不中断其他任务。
    """
    results = {}
    if not tasks:
        return results
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fn): key for key, fn in tasks}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                res = fut.result()
            except Exception as e:  # 单任务失败不影响其他任务
                res = {"error": str(e)}
            results[key] = res
            if on_done:
                on_done(key, res)
    return results


# ============================================================
# 画布节点缓存（落盘，重跑跳过已上传素材）
# ============================================================

def cache_file_for(canvas_uuid):
    return os.path.join(os.getcwd(), CACHE_SUBDIR, f"{canvas_uuid}.json")


def load_canvas_cache(canvas_uuid, refresh=False):
    """加载画布节点缓存 {节点名: 节点id}；缓存缺失或 --refresh-cache 时全量拉取并落盘。"""
    path = cache_file_for(canvas_uuid)
    if not refresh and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", {})
            if isinstance(nodes, dict):
                return nodes
        except (json.JSONDecodeError, OSError):
            pass  # 缓存损坏则重建

    data, _ = run_libtv(["project", canvas_uuid])
    nodes = {}
    if isinstance(data, dict):
        for n in data.get("nodes", []):
            name = n.get("name", "")
            nid = n.get("id", "")
            if name and nid:
                nodes[name] = nid
    save_canvas_cache(canvas_uuid, nodes)
    return nodes


def save_canvas_cache(canvas_uuid, nodes):
    path = cache_file_for(canvas_uuid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "canvas": canvas_uuid,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "nodes": nodes,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"  ! 缓存写入失败: {e}", file=sys.stderr)


# ============================================================
# 素材扫描与匹配
# ============================================================

def scan_project_refs(project_root, episode=None):
    """扫描本地素材文件，返回 {节点名: 文件路径}。不调用 libtv。"""
    found = {}
    for ref_type, rel_path in REFERENCE_TYPE_PATHS.items():
        dir_path = os.path.join(project_root, rel_path)
        if not os.path.isdir(dir_path):
            continue
        for f in sorted(os.listdir(dir_path)):
            if not f.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            name_without_ext = os.path.splitext(f)[0]
            # ! 选角参考图（{角色名}_选角.png）禁止用于视频生成
            # 选角资产为白T恤+灰背景，仅用于角色面部特征确立，不适合作为视频画面参考
            if "_选角" in name_without_ext:
                print(f"  ! 跳过选角参考图: {f}（禁止用于视频生成）", file=sys.stderr)
                continue
            # 新格式: {道具名}_{出现场合}_基准.png → 剥离 _{出现场合}_基准
            clean_name = re.sub(r"_(全剧|EP\d+)_基准$", "", name_without_ext, flags=re.IGNORECASE)
            # 剧集级格式: {道具名}_{剧集号}集.png → 剥离 _{剧集号}集
            clean_name = re.sub(r"_EP\d+集$", "", clean_name, flags=re.IGNORECASE)
            # 旧格式兼容: _基准 / _参考 / _ref / -reference 后缀
            clean_name = re.sub(r"(_基准|_参考|_ref|-reference)$", "", clean_name, flags=re.IGNORECASE)
            if ref_type == "风格":
                clean_name = re.sub(r"^风格参考-", "", clean_name)
            node_name = f"{ref_type}_{clean_name}"
            found[node_name] = os.path.join(dir_path, f)

    # 扫描分镜图（剧集级目录）
    if episode:
        sb_dir = os.path.join(project_root, episode, STORYBOARD_IMAGE_PATH)
        if os.path.isdir(sb_dir):
            for f in sorted(os.listdir(sb_dir)):
                if not f.lower().endswith(".png"):
                    continue
                name_without_ext = os.path.splitext(f)[0]
                found[f"分镜_{name_without_ext}"] = os.path.join(sb_dir, f)

        # 扫描视觉锚点图（剧集级目录）
        # 文件名格式：锚点_场{N}{阶段?}_{场景名}，如 锚点_场1A_断供报信.png
        va_dir = os.path.join(project_root, episode, VISUAL_ANCHOR_PATH)
        if os.path.isdir(va_dir):
            for f in sorted(os.listdir(va_dir)):
                if not f.lower().endswith(".png"):
                    continue
                name_without_ext = os.path.splitext(f)[0]
                match = re.match(r"锚点_场(\d+[A-Z]?)", name_without_ext)
                if match:
                    found[f"视觉锚点_场{match.group(1)}"] = os.path.join(va_dir, f)

    return found


def scan_storyboard_refs(project_root, episode):
    """扫描分镜图目录，返回 {组N: [分镜_组N_镜M, ...]}（按文件名排序）。"""
    by_group = {}
    sb_dir = os.path.join(project_root, episode, STORYBOARD_IMAGE_PATH)
    if os.path.isdir(sb_dir):
        for f in sorted(os.listdir(sb_dir)):
            if not f.lower().endswith(".png"):
                continue
            name = os.path.splitext(f)[0]
            match = re.match(r"组(\d+)_镜(\d+)", name)
            if match:
                by_group.setdefault(f"组{match.group(1)}", []).append(f"分镜_{name}")
    return by_group


def scan_visual_anchors(project_root, episode):
    """扫描视觉锚点目录，返回 {纯场号: [视觉锚点_场N{阶段?}, ...]}。

    同场多阶段锚点（场1A/场1B）聚合为列表，由 Agent 经 --refs 显式指定阶段。
    """
    by_scene = {}
    va_dir = os.path.join(project_root, episode, VISUAL_ANCHOR_PATH)
    if os.path.isdir(va_dir):
        for f in sorted(os.listdir(va_dir)):
            if not f.lower().endswith(".png"):
                continue
            name = os.path.splitext(f)[0]
            match = re.match(r"锚点_场(\d+[A-Z]?)", name)
            if match:
                phase = match.group(1)  # 如 "1" 或 "1A"
                scene_num = re.match(r"(\d+)", phase).group(1)
                by_scene.setdefault(scene_num, []).append(f"视觉锚点_场{phase}")
    return by_scene


def match_ref_name(ref_name, available_nodes):
    """精确名匹配；失败则按 '_' 拆关键词做包含匹配，返回匹配到的节点名列表。"""
    if ref_name in available_nodes:
        return [ref_name]
    keywords = ref_name.split("_", 1)
    return [n for n in available_nodes if all(kw in n for kw in keywords if kw)]


def dedupe_contained_names(names):
    """同类型下，若名称 A 是另一匹配名 B 的子串则丢弃 A（如 掌柜 ⊂ 大掌柜），保留更长名。"""
    def name_part(n):
        t, _, nm = n.partition("_")
        return t, nm

    kept = []
    for n in names:
        t, nm = name_part(n)
        contained = any(
            m != n and name_part(m)[0] == t and nm != name_part(m)[1] and nm in name_part(m)[1]
            for m in names
        )
        if not contained:
            kept.append(n)
    return kept


def group_text_corpus(group):
    """组的全文语料（用于素材名匹配）。MD 用原文，JSON 用完整序列化。"""
    if isinstance(group, dict) and group.get("_format") == "md":
        return group.get("_raw_content", "")
    try:
        return json.dumps(group, ensure_ascii=False)
    except (TypeError, ValueError):
        return ""


def group_dialogue_text(group):
    """组的台词语料（用于音色参考建议）。JSON 取台词字段；MD 含引号对白时用全文。"""
    if isinstance(group, dict) and group.get("_format") == "md":
        raw = group.get("_raw_content", "")
        return raw if re.search(r"[「」『』“”\"']", raw) else ""
    if not isinstance(group, dict):
        return ""
    parts = []
    for shot in group.get("镜头列表", []) or []:
        line = str(shot.get("台词", "") or "")
        if line.strip():
            parts.append(line)
    return "\n".join(parts)


def find_voice_file(voice_dir, role_name):
    """在音色参考目录查找角色音频，支持 {角色名}-音色参考.ext / {角色名}音色.ext 两种命名。"""
    for pattern in (f"{role_name}-音色参考", f"{role_name}音色"):
        for ext in (".wav", ".mp3", ".m4a", ".ogg", ".flac"):
            candidate = os.path.join(voice_dir, f"{pattern}{ext}")
            if os.path.exists(candidate):
                return candidate
    return None


def resolve_group_refs(gid, group, custom_refs, no_auto, candidates,
                       storyboard_by_group, anchor_by_scene, ref_mode):
    """解析单组的最终参考图列表。

    优先级：显式 --refs > 自动匹配（名称出现在组内容中）> 无；
    叠加 reference_image_mode 的自动分镜图/视觉锚点。
    返回 (refs, source, warnings)。
    """
    group_name = f"组{gid}"
    warnings = []
    refs = []

    explicit = custom_refs.get(group_name) or custom_refs.get(str(gid))
    if explicit:
        for r in explicit:
            refs.extend(match_ref_name(r.strip(), candidates))
        source = "explicit"
    elif not no_auto:
        corpus = group_text_corpus(group)
        matched = []
        for cand in sorted(candidates):  # 排序保证计划输出确定性
            type_, _, nm = cand.partition("_")
            if type_ not in ("角色", "场景", "道具") or not nm:
                continue
            # 场景通常不引用（分镜图/视觉锚点已含场景信息），仅 none 模式纳入场景
            if type_ == "场景" and ref_mode != "none":
                continue
            if nm in corpus:
                matched.append(cand)
        refs.extend(dedupe_contained_names(matched))
        source = "auto"
    else:
        source = "none"

    # 模式自动素材叠加
    if ref_mode == "storyboard_images":
        for sb in storyboard_by_group.get(group_name, []):
            if sb in candidates and sb not in refs:
                refs.append(sb)
    elif ref_mode == "visual_anchor":
        scene_num = extract_scene_number(group)
        if scene_num and scene_num in anchor_by_scene:
            anchors = anchor_by_scene[scene_num]
            if len(anchors) == 1:
                if anchors[0] in candidates and anchors[0] not in refs:
                    refs.append(anchors[0])
            elif not any(x.startswith("视觉锚点_") for x in refs):
                warnings.append(
                    f"场{scene_num} 有 {len(anchors)} 张阶段锚点（{', '.join(anchors)}），"
                    f"脚本不做自动匹配，需经 --refs 显式指定该组对应阶段的锚点节点名"
                )
        elif scene_num:
            warnings.append(f"场号{scene_num} 未找到对应视觉锚点图")

    refs = list(dict.fromkeys(refs))
    if not refs:
        warnings.append("无参考图，将以纯文生视频（text2video）模式生成")

    return refs, source, warnings


# ============================================================
# 组文件加载
# ============================================================

def parse_refs(refs_args):
    result = {}
    for ref_str in refs_args:
        parts = ref_str.split(":", 1)
        if len(parts) != 2:
            print(f"  ! --refs 格式错误: {ref_str}（应为 \"组N:类型_名,类型_名\"），跳过", file=sys.stderr)
            continue
        group_key = parts[0].strip()
        refs = [r.strip() for r in parts[1].split(",") if r.strip()]
        result[group_key] = refs
    return result


def load_group_file(groups_dir, group_name, storyboard_mode):
    """按 storyboard_mode 加载组文件。

    detailed   → 组{N}.json（结构化 JSON）
    simplified → 组{N}.md（讲戏式 Markdown，全文作为 prompt）

    返回 (group_dict, format_str) 或 (None, None) 表示文件不存在。
    """
    if storyboard_mode == "simplified":
        group_path = os.path.join(groups_dir, f"{group_name}.md")
        if not os.path.exists(group_path):
            return None, None
        with open(group_path, "r", encoding="utf-8") as f:
            raw_md = f.read()
        # 从首行提取组时长（格式：组时长：7s 或 组时长：7）
        duration_match = re.search(r"组时长[：:]\s*(\d+)", raw_md)
        group = {
            "_format": "md",
            "_raw_content": raw_md,
            "组时长": duration_match.group(1) if duration_match else "5",
        }
        return group, "md"
    else:
        group_path = os.path.join(groups_dir, f"{group_name}.json")
        if not os.path.exists(group_path):
            return None, None
        with open(group_path, "r", encoding="utf-8") as f:
            group = json.load(f)
        return group, "json"


def preload_groups(groups_dir, groups, storyboard_mode):
    """预加载全部分组文件。返回 (loaded, missing)：loaded={组N: dict}，missing=[组N]。"""
    loaded, missing = {}, []
    for gid in groups:
        name = f"组{gid}"
        group, _fmt = load_group_file(groups_dir, name, storyboard_mode)
        if group is None:
            missing.append(name)
        else:
            loaded[name] = group
    return loaded, missing


def extract_scene_number(group_dict):
    """从组文件内容提取场号。JSON 取「场号」字段；MD 正则匹配「场号：N」或「场N」。"""
    if not isinstance(group_dict, dict):
        return None
    if group_dict.get("_format") == "md":
        raw_md = group_dict.get("_raw_content", "")
        match = re.search(r"场号[：:]\s*(\d+)", raw_md)
        if match:
            return match.group(1)
        match = re.search(r"场(\d+)", raw_md)
        if match:
            return match.group(1)
        return None
    scene = group_dict.get("场号")
    return str(scene) if scene is not None else None


# ============================================================
# Prompt 构建（契约不变）
# ============================================================

def build_ref_description(ref_name, idx):
    """根据参考图名称生成 Image N 引用描述。

    --left 顺序决定 {{Image N}} 编号，第一个 --left 为 {{Image 1}}。
    格式统一为 "{名称}{类型}参考{{Image N}}"；分镜图按镜头编号、视觉锚点按场号引用。
    """
    if "场景" in ref_name:
        scene_name = ref_name.replace("场景_", "")
        return f"{scene_name}场景参考{{{{Image {idx}}}}}"
    elif "角色" in ref_name:
        char_name = ref_name.replace("角色_", "").replace("_基准", "")
        return f"{char_name}角色参考{{{{Image {idx}}}}}"
    elif "道具" in ref_name:
        prop_name = ref_name.replace("道具_", "").replace("_基准", "")
        prop_name = re.sub(r"_(全剧|EP\d+)$", "", prop_name)
        prop_name = re.sub(r"_EP\d+集$", "", prop_name)
        return f"{prop_name}道具参考{{{{Image {idx}}}}}"
    elif "视觉锚点" in ref_name:
        # 视觉锚点节点名格式：视觉锚点_场{N}{阶段?}，如 视觉锚点_场1A
        match = re.search(r"场(\d+[A-Z]?)", ref_name)
        scene_num = match.group(1) if match else str(idx)
        return f"场{scene_num}视觉锚点参考{{{{Image {idx}}}}}"
    elif "分镜" in ref_name:
        # 分镜图节点名格式：分镜_组{N}_镜{M}
        match = re.search(r"镜(\d+)", ref_name)
        shot_num = match.group(1) if match else str(idx)
        return f"镜头{shot_num}参考{{{{Image {idx}}}}}"
    elif "风格" in ref_name:
        style_name = ref_name.replace("风格_", "")
        return f"{style_name}风格参考{{{{Image {idx}}}}}"
    else:
        return f"参考素材{{{{Image {idx}}}}}"


def sort_ref_names(ref_names):
    """按类型排序参考图：分镜图 → 视觉锚点 → 角色 → 道具 → 其他（场景/风格等）。"""
    def sort_key(name):
        if "分镜" in name:
            match = re.search(r"镜(\d+)", name)
            shot = int(match.group(1)) if match else 0
            return (0, shot)
        elif "视觉锚点" in name:
            # 按 (场号, 阶段) 排序：场1A 排在场1 之后、场2 之前
            match = re.search(r"场(\d+)([A-Z]?)", name)
            scene = int(match.group(1)) if match else 0
            phase = match.group(2) if match else ""
            return (1, scene, phase)
        elif "角色" in name:
            return (2, 0)
        elif "道具" in name:
            return (3, 0)
        else:
            return (4, 0)
    return sorted(ref_names, key=sort_key)


def build_prompt(group_json, ref_names, voice_ref_names=None, audio_connector="，"):
    """构建完整 prompt：引用行 + 约束行 + 分隔线 + 组内容。

    引用行中的 {{Image N}} 编号与 --left 顺序一致（sort_ref_names 排序）。
    含音色参考时在引用行末尾追加 {{Audio N}} 引用。
    支持 JSON 格式（dict）和 MD 格式（含 _raw_content 键的 dict）。
    """
    if isinstance(group_json, dict) and group_json.get("_format") == "md":
        raw_content = group_json.get("_raw_content", "")
    else:
        raw_content = json.dumps(group_json, ensure_ascii=False)

    ordered_refs = sort_ref_names(ref_names) if ref_names else []
    audio_parts = []
    if voice_ref_names:
        for i, vn in enumerate(voice_ref_names):
            role = vn.replace("音色_", "", 1) if vn.startswith("音色_") else vn
            audio_parts.append(f"{role}音色参考{{{{Audio {i+1}}}}}")

    if ordered_refs:
        ref_parts = [build_ref_description(n, i + 1) for i, n in enumerate(ordered_refs)]
        ref_line = "、".join(ref_parts)
        if audio_parts:
            ref_line += audio_connector + "、".join(audio_parts)
        return f"{ref_line}\n\n{CONSTRAINT}\n{SEPARATOR}\n{raw_content}"
    if audio_parts:
        return f"{'、'.join(audio_parts)}\n\n{CONSTRAINT}\n{SEPARATOR}\n{raw_content}"
    return f"{CONSTRAINT}\n{SEPARATOR}\n{raw_content}"


def calc_duration(group_json):
    raw = group_json.get("组时长", "5")
    try:
        duration = int(float(str(raw)))
    except (ValueError, TypeError):
        shots = group_json.get("镜头列表", [])
        if shots:
            duration = sum(int(float(str(s.get("时长", 5)))) for s in shots)
        else:
            duration = 5
    return max(4, min(15, duration))


def map_resolution(resolution, model):
    """分辨率映射（与 references/storyboard-to-libtv.md §4 一致）。

    - Minimax H3 系（仅支持 768P/2K）：480p/720p → 768P
    - 其他模型：1080p/2K/4K → 720p；480p/720p 原样
    """
    raw = resolution or CONFIG_DEFAULTS["resolution"]
    r = raw.lower()
    if "minimax" in (model or "").lower():
        return "768P" if r in ("480p", "720p") else raw
    if r in ("1080p", "2k", "4k"):
        return "720p"
    return raw


# ============================================================
# 上传层（并发）
# ============================================================

def make_upload_task(node_name, node_type, file_path):
    def task():
        r, err = run_libtv(["upload", node_name, "-t", node_type, "-f", file_path])
        if r is None:
            return {"ok": False, "error": err}
        node_id = "?"
        if isinstance(r, dict):
            node_id = r.get("data", {}).get("id") or r.get("nodeId") or r.get("nodeKey") or "?"
        return {"ok": True, "id": str(node_id)}
    return task


def upload_references(project_root, canvas_cache, needed_names, episode, max_workers):
    """按需并发上传参考图。返回 {节点名: 节点id}（含缓存复用与本次上传）。"""
    local_assets = scan_project_refs(project_root, episode=episode)

    to_upload = {}   # 节点名 → 文件路径
    ref_nodes = {}   # 节点名 → 节点id（复用 + 上传）
    missing = []

    for need in sorted(needed_names):
        if need in canvas_cache:
            ref_nodes[need] = canvas_cache[need]
            continue
        file_path = local_assets.get(need)
        if file_path is None:
            fuzzy = match_ref_name(need, local_assets)
            if fuzzy:
                file_path = local_assets[fuzzy[0]]
        if file_path is None:
            missing.append(need)
            continue
        to_upload[need] = file_path

    print("\n" + "=" * 60)
    reused = len(ref_nodes)
    print(f"上传参考图（需 {len(needed_names)} | 复用 {reused} | 上传 {len(to_upload)}"
          f" | 缺失 {len(missing)}）")
    print("=" * 60)
    for name in missing:
        print(f"  ! {name}: 未找到本地素材文件，跳过", file=sys.stderr)

    project_root_abs = os.path.abspath(project_root)

    def on_done(name, res):
        rel = os.path.relpath(to_upload.get(name, ""), project_root_abs)
        if res.get("ok"):
            print(f"  {rel} → {name} ✅ (ID={str(res.get('id', '?'))[:12]}...)")
        else:
            print(f"  {rel} → {name} ❌ {res.get('error', '')[:120]}", file=sys.stderr)

    tasks = [(name, make_upload_task(name, "image", path)) for name, path in to_upload.items()]
    results = run_concurrent(tasks, max_workers, on_done=on_done)
    for name, res in results.items():
        if res.get("ok"):
            ref_nodes[name] = res["id"]
    print(f"  参考图就绪: {len(ref_nodes)} 个")
    return ref_nodes


def upload_voice_refs(project_root, role_names, canvas_cache, max_workers):
    """按需并发上传音色参考。返回上传/复用成功的节点名列表。"""
    voice_dir = os.path.join(project_root, "全局依赖", "音色参考")
    voice_nodes = []

    to_upload = {}
    print("\n" + "=" * 60)
    print("上传音色参考到画布")
    print("=" * 60)

    if not os.path.isdir(voice_dir):
        print(f"  ! 音色参考目录不存在: {voice_dir}", file=sys.stderr)
        return voice_nodes

    for role_name in role_names:
        role_name = role_name.strip()
        if not role_name:
            continue
        node_name = f"音色_{role_name}"
        if node_name in canvas_cache:
            voice_nodes.append(node_name)
            print(f"  {node_name} → 已存在，复用")
            continue
        file_path = find_voice_file(voice_dir, role_name)
        if file_path is None:
            print(f"  ! 未找到 {role_name} 的音色参考文件（目录: {voice_dir}）", file=sys.stderr)
            continue
        to_upload[node_name] = file_path

    def on_done(name, res):
        if res.get("ok"):
            print(f"  {name} ✅")
        else:
            print(f"  {name} ❌ {res.get('error', '')[:120]}", file=sys.stderr)

    tasks = [(name, make_upload_task(name, "audio", path)) for name, path in to_upload.items()]
    results = run_concurrent(tasks, max_workers, on_done=on_done)
    for name, res in results.items():
        if res.get("ok"):
            voice_nodes.append(name)
    print(f"  音色参考就绪: {len(voice_nodes)} 个")
    return voice_nodes


# ============================================================
# 节点创建（并发 + upsert）
# ============================================================

def build_node_cmds(group_name, prompt, model, mode_type, count, ratio, duration,
                    resolution, sound, left_names):
    """组装 create 与 update 两组命令参数（同一套 prompt/set/left）。"""
    sets = [
        f"model={model}",
        f"modeType={mode_type}",
        f"count={count}",
        f"ratio={ratio}",
        f"duration={duration}",
    ]
    # Minimax H3 不支持 enableSound
    if "minimax" not in model.lower():
        sets.append(f"enableSound={sound}")
    sets.append(f"resolution={map_resolution(resolution, model)}")

    common = ["--prompt", prompt]
    for s in sets:
        common += ["--set", s]
    for n in left_names:
        common += ["--left", n]

    create_args = ["node", "create", group_name, "-t", "video"] + common
    # update 走默认子命令（不接受 -t）；--left 为 ensure 语义，不删旧边
    update_args = ["node", group_name] + common
    return create_args, update_args


def make_upsert_node_task(create_args, update_args):
    def task():
        r, err = run_libtv(create_args)
        if r is not None:
            return {"action": "created"}
        # create 失败（通常为同名已存在）→ 回退 update，保证重跑幂等
        r2, err2 = run_libtv(update_args)
        if r2 is not None:
            return {"action": "updated"}
        return {"action": "failed", "error": (err or err2 or "未知错误")[:300]}
    return task


# ============================================================
# 运行结果解析与下载
# ============================================================

def _collect_node_urls(node, mapping):
    """递归收集 {节点名: [url, ...]}。"""
    if isinstance(node, dict):
        name = node.get("displayName") or node.get("name") or node.get("nodeName")
        if name:
            urls = []
            u = node.get("url") or node.get("videoUrl")
            if isinstance(u, str):
                urls.append(u)
            elif isinstance(u, list):
                urls.extend(x for x in u if isinstance(x, str) and x)
            for r_ in node.get("results") or []:
                if isinstance(r_, dict) and isinstance(r_.get("url"), str):
                    urls.append(r_["url"])
            d = node.get("data")
            if isinstance(d, dict):
                u = d.get("url")
                if isinstance(u, str):
                    urls.append(u)
                elif isinstance(u, list):
                    urls.extend(x for x in u if isinstance(x, str) and x)
            if urls:
                mapping.setdefault(str(name), urls)
        for v in node.values():
            _collect_node_urls(v, mapping)
    elif isinstance(node, list):
        for v in node:
            _collect_node_urls(v, mapping)


def extract_urls_from_run_result(result):
    """从 group --run 终态输出提取 {节点名: [视频URL]}。

    兼容 JSON 对象 / NDJSON 多行 / 原始字符串；结构不认识时返回空 dict，
    由调用方回退到逐节点查询。
    """
    mapping = {}
    if isinstance(result, str):
        for line in result.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                _collect_node_urls(json.loads(line), mapping)
            except json.JSONDecodeError:
                continue
    else:
        _collect_node_urls(result, mapping)
    return mapping


def extract_node_urls_from_query(result):
    """从 `libtv node <名>` 查询输出提取 URL 列表。"""
    if not isinstance(result, dict):
        return []
    data = result.get("data", {}) or {}
    urls = data.get("url") or []
    if isinstance(urls, str):
        urls = [urls]
    urls = [u for u in urls if isinstance(u, str) and u]
    if urls:
        return urls
    for r_ in data.get("results", []) or []:
        if isinstance(r_, dict) and isinstance(r_.get("url"), str):
            urls.append(r_["url"])
    return urls


def query_node_urls(node_name, retry_delay=5, timeout=600):
    """单节点结果查询（仅查询失败时有限重试）。

    group --run 已阻塞完成后正常一次即返回；查询成功但无 URL 视为该节点未产出。
    """
    start = time.time()
    while True:
        r, _ = run_libtv(["node", node_name])
        if r is not None:
            return extract_node_urls_from_query(r)
        if time.time() - start >= timeout:
            return []
        time.sleep(max(1, retry_delay))


def extract_group_names(result):
    """从 `group list` 输出提取分组名集合；结构不认识时返回 None（跳过预检）。"""
    if isinstance(result, str):
        parsed = []
        for line in result.splitlines():
            line = line.strip()
            if line:
                try:
                    parsed.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        result = parsed if parsed else None
    groups = None
    if isinstance(result, dict):
        groups = result.get("groups") or (result.get("data", {}) or {}).get("groups")
    elif isinstance(result, list):
        groups = result
    if not isinstance(groups, list):
        return None
    names = set()
    for g in groups:
        if isinstance(g, dict):
            n = g.get("name") or g.get("displayName") or g.get("groupName")
            if n:
                names.add(str(n))
    return names or None


def download_video(url, output_path):
    try:
        urllib.request.urlretrieve(url, output_path)
        return True, None
    except Exception as e:
        return False, str(e)


def make_download_task(node_name, url, output_path):
    def task():
        ok, error = download_video(url, output_path)
        return {"ok": ok, "error": error, "url": url, "path": output_path,
                "displayName": node_name}
    return task


# ============================================================
# 阶段一：--plan（纯本地，无副作用）
# ============================================================

def plan_pipeline(args):
    project_root = os.path.join(os.getcwd(), "project", args.project)
    groups_dir = os.path.join(project_root, args.episode, "分镜", "分组")
    if not os.path.isdir(groups_dir):
        print(f"❌ 分组目录不存在: {groups_dir}")
        return 1

    loaded, missing = preload_groups(groups_dir, args.groups, args.storyboard_mode)
    for name in missing:
        ext = ".md" if args.storyboard_mode == "simplified" else ".json"
        print(f"  ! {name}{ext} 不存在（模式: {args.storyboard_mode}）", file=sys.stderr)

    local_assets = scan_project_refs(project_root, episode=args.episode)
    candidates = set(local_assets)
    voice_dir = os.path.join(project_root, "全局依赖", "音色参考")
    storyboard_by_group = (
        scan_storyboard_refs(project_root, args.episode)
        if args.reference_image_mode == "storyboard_images" else {}
    )
    anchor_by_scene = (
        scan_visual_anchors(project_root, args.episode)
        if args.reference_image_mode == "visual_anchor" else {}
    )
    custom_refs = parse_refs(args.refs) if args.refs else {}
    char_assets = sorted(c for c in candidates if c.startswith("角色_"))

    plan_rows = []
    voice_union = set()
    for gid in args.groups:
        name = f"组{gid}"
        group = loaded.get(name)
        if group is None:
            plan_rows.append({"group": name, "error": "分组文件不存在"})
            continue

        refs, source, warnings = resolve_group_refs(
            gid, group, custom_refs, args.no_auto_refs, candidates,
            storyboard_by_group, anchor_by_scene, args.reference_image_mode,
        )

        # 音色建议：角色名出现在台词语料中，且本地存在对应音色文件
        suggested_voices = []
        dialogue = group_dialogue_text(group)
        if dialogue:
            matched_chars = [c for c in char_assets if c.partition("_")[2] in dialogue]
            for c in dedupe_contained_names(matched_chars):
                role = c.partition("_")[2]
                if find_voice_file(voice_dir, role):
                    suggested_voices.append(role)
        voice_union.update(suggested_voices)

        plan_rows.append({
            "group": name,
            "duration": calc_duration(group),
            "scene": extract_scene_number(group),
            "refSource": source,
            "refs": refs,
            "voiceRefs": suggested_voices,
            "warnings": warnings,
        })

    # ===== 人类可读摘要 =====
    print("=" * 60)
    print(f"执行计划（--plan，无副作用）")
    print(f"项目: {args.project} | 剧集: {args.episode} | "
          f"分镜模式: {args.storyboard_mode} | 参考图模式: {args.reference_image_mode}")
    print("=" * 60)
    for row in plan_rows:
        if "error" in row:
            print(f"\n{row['group']}: ❌ {row['error']}")
            continue
        scene = f"，场{row['scene']}" if row["scene"] else ""
        print(f"\n{row['group']}（{row['duration']}s{scene}）")
        print(f"  参考图[{row['refSource']}]: {', '.join(row['refs']) if row['refs'] else '（无）'}")
        if row["voiceRefs"]:
            print(f"  音色建议: {', '.join(row['voiceRefs'])}")
        for w in row["warnings"]:
            print(f"  ! {w}")

    # ===== 可直接复制的构建参数建议 =====
    refs_args = [f"{r['group']}:{','.join(r['refs'])}" for r in plan_rows if r.get("refs")]
    print("\n" + "-" * 60)
    print("建议构建流程（补入画布 UUID 与模型名后执行）:")
    script = os.path.basename(sys.argv[0])
    cmd = (f"  python {script} --build --project \"{args.project}\" --episode {args.episode} \\\n"
           f"    --canvas-uuid <画布UUID> --model \"<modelName>\" \\\n"
           f"    --storyboard-mode {args.storyboard_mode} "
           f"--reference-image-mode {args.reference_image_mode} \\\n"
           f"    --groups {' '.join(str(g) for g in args.groups)}")
    if refs_args:
        cmd += " \\\n    " + " \\\n    ".join(f"--refs \"{ra}\"" for ra in refs_args)
    if voice_union:
        cmd += f" \\\n    --voice-refs {' '.join(sorted(voice_union))}"
    print(cmd)
    print("-" * 60)
    print("说明: --build 未显式 --refs 的组将按本计划自动匹配；显式 --refs 的组以其为准。")
    print("      运行与下载须在 --build 之后单独调用（--run ... --download）。")

    # ===== 机器可读 JSON =====
    print("\nPLAN_JSON:")
    print(json.dumps({
        "project": args.project,
        "episode": args.episode,
        "storyboardMode": args.storyboard_mode,
        "referenceImageMode": args.reference_image_mode,
        "groups": plan_rows,
        "suggestedVoiceRefs": sorted(voice_union),
    }, ensure_ascii=False, indent=2))
    return 0


# ============================================================
# 阶段二：--build（上传 → 建节点 → 幂等建组，不运行）
# ============================================================

def build_pipeline(args):
    project_root = os.path.join(os.getcwd(), "project", args.project)
    groups_dir = os.path.join(project_root, args.episode, "分镜", "分组")
    if not os.path.isdir(groups_dir):
        print(f"❌ 分组目录不存在: {groups_dir}")
        return 1

    # 步骤0: 预加载全部分组文件（缺失提前暴露，不浪费上传）
    loaded, missing = preload_groups(groups_dir, args.groups, args.storyboard_mode)
    for name in missing:
        ext = ".md" if args.storyboard_mode == "simplified" else ".json"
        print(f"  ! {name}{ext} 不存在（模式: {args.storyboard_mode}），跳过", file=sys.stderr)
    if not loaded:
        print("❌ 未找到任何分组文件")
        return 1

    print(f"分镜模式: {args.storyboard_mode}（{'组{N}.json' if args.storyboard_mode == 'detailed' else '组{N}.md'}）")

    # 步骤1: 绑定画布
    canvas_uuid = args.canvas_uuid
    print("\n" + "=" * 60)
    print(f"步骤1: 绑定画布 {canvas_uuid}")
    print("=" * 60)
    r, err = run_libtv(["project", "use", canvas_uuid])
    if r is None:
        print(f"❌ 绑定失败: {err}")
        return 1
    print("  ✅ 已绑定")

    # 步骤2: 画布节点缓存（落盘复用）
    canvas_cache = load_canvas_cache(canvas_uuid, refresh=args.refresh_cache)
    print(f"  画布缓存: {len(canvas_cache)} 个已有节点"
          f"{'（强制刷新）' if args.refresh_cache else ''} ← {cache_file_for(canvas_uuid)}")

    # 步骤3: 解析各组参考（显式 --refs > 自动匹配；叠加模式自动素材）
    storyboard_by_group = (
        scan_storyboard_refs(project_root, args.episode)
        if args.reference_image_mode == "storyboard_images" else {}
    )
    anchor_by_scene = (
        scan_visual_anchors(project_root, args.episode)
        if args.reference_image_mode == "visual_anchor" else {}
    )
    if storyboard_by_group:
        total_sb = sum(len(v) for v in storyboard_by_group.values())
        print(f"  📋 分镜图: {total_sb} 张（自动扫描，按组号聚合）")
    if anchor_by_scene:
        total_va = sum(len(v) for v in anchor_by_scene.values())
        print(f"  📋 视觉锚点: {total_va} 张（自动扫描，按场号聚合）")

    local_assets = scan_project_refs(project_root, episode=args.episode)
    candidates = set(local_assets) | set(canvas_cache)
    custom_refs = parse_refs(args.refs) if args.refs else {}

    resolved = {}
    all_needed = set()
    for gid in args.groups:
        name = f"组{gid}"
        group = loaded.get(name)
        if group is None:
            continue
        refs, source, warnings = resolve_group_refs(
            gid, group, custom_refs, args.no_auto_refs, candidates,
            storyboard_by_group, anchor_by_scene, args.reference_image_mode,
        )
        resolved[name] = (refs, source, warnings)
        all_needed.update(refs)

    # 步骤4: 并发上传参考图（按需，跳过缓存命中）
    ref_nodes = upload_references(
        project_root, canvas_cache,
        needed_names=all_needed if all_needed else set(),
        episode=args.episode, max_workers=args.max_workers,
    )
    for n, nid in ref_nodes.items():
        canvas_cache[n] = nid

    # 步骤5: 并发上传音色参考（仅 --voice-refs 显式指定的角色）
    voice_nodes = []
    if args.voice_refs:
        voice_nodes = upload_voice_refs(project_root, args.voice_refs, canvas_cache, args.max_workers)
        for vn in voice_nodes:
            if vn not in canvas_cache:
                canvas_cache[vn] = "?"  # id 未知也标记存在，避免重复上传
    else:
        print("\n  ℹ️ 未指定 --voice-refs，跳过音色参考上传")

    save_canvas_cache(canvas_uuid, canvas_cache)

    # 步骤6: 并发创建 video 节点（upsert：create 失败回退 update）
    print("\n" + "=" * 60)
    print(f"步骤6: 创建 video 节点（并发 ×{args.max_workers}，upsert 幂等）")
    print("=" * 60)

    model = args.model
    ratio = args.ratio or CONFIG_DEFAULTS["ratio"]
    resolution = args.resolution or CONFIG_DEFAULTS["resolution"]
    sound = args.sound or CONFIG_DEFAULTS["enableSound"]
    count = CONFIG_DEFAULTS["count"]

    tasks = []
    task_meta = {}
    for gid in args.groups:
        name = f"组{gid}"
        group = loaded.get(name)
        if group is None:
            continue
        refs, source, warnings = resolved[name]

        # 仅连线实际就绪（已上传/已缓存）的参考
        available = [x for x in refs if x in ref_nodes]
        dropped = set(refs) - set(available)
        if dropped:
            warnings.append(f"参考素材未就绪，已从连线中移除: {', '.join(sorted(dropped))}")

        duration = calc_duration(group)
        ordered_refs = sort_ref_names(available) if available else []
        prompt = build_prompt(group, available, voice_nodes)
        mode_type = "mixed2video" if (available or voice_nodes) else "text2video"

        create_args, update_args = build_node_cmds(
            name, prompt, model, mode_type, count, ratio, duration,
            resolution, sound, ordered_refs + voice_nodes,
        )
        tasks.append((name, make_upsert_node_task(create_args, update_args)))
        task_meta[name] = {
            "duration": duration, "mode": mode_type, "refs": ordered_refs,
            "source": source, "warnings": warnings,
        }

    def on_node_done(name, res):
        meta = task_meta[name]
        action = res.get("action")
        refs_desc = ", ".join(meta["refs"] + voice_nodes) or "(无参考素材，text2video)"
        if action == "created":
            print(f"  ✅ {name} 新建（{meta['duration']}s，{meta['mode']}，[{meta['source']}] {refs_desc}）")
        elif action == "updated":
            print(f"  ♻️  {name} 已存在 → 更新（{meta['duration']}s，{meta['mode']}，[{meta['source']}] {refs_desc}）")
        else:
            print(f"  ❌ {name} 创建失败: {res.get('error', '')}", file=sys.stderr)
        for w in meta["warnings"]:
            print(f"    ! {w}", file=sys.stderr)

    node_results = run_concurrent(tasks, args.max_workers, on_done=on_node_done)
    succeeded = [f"组{g}" for g in args.groups
                 if node_results.get(f"组{g}", {}).get("action") in ("created", "updated")]
    failed_nodes = [n for n in node_results if node_results[n].get("action") == "failed"]
    if not succeeded:
        print("❌ 未创建任何节点")
        return 1
    if failed_nodes:
        print(f"  ! {len(failed_nodes)} 个节点失败，已从分组中排除: {', '.join(failed_nodes)}", file=sys.stderr)

    # 步骤7: 幂等建组（默认子命令：有则绑定、无则新建）
    if args.no_group:
        print("\n" + "=" * 60)
        print("步骤7: 建组（已跳过 --no-group）")
        print("=" * 60)
        print(f"  ⏭️ 跳过建组，共创建 {len(succeeded)} 个独立节点: {', '.join(succeeded)}")
        print("  如需运行，请去掉 --no-group 重新 --build，或在画布手动编排")
        return 0

    group_name = args.group_name or f"{args.episode}_组{'_'.join(str(g) for g in args.groups)}"
    print("\n" + "=" * 60)
    print(f"步骤7: 建组 {group_name}（幂等）")
    print("=" * 60)
    node_args = []
    for n in succeeded:
        node_args += ["--node", n]
    r, err = run_libtv(["group", group_name] + node_args)
    if r is None:
        print(f"❌ 建组失败: {err}")
        return 1
    action = r.get("action", "?") if isinstance(r, dict) else "?"
    print(f"  ✅ 分组就绪: {group_name}（action={action}，{len(succeeded)} 个节点）")

    # 摘要 + 下一步
    print("\n" + "=" * 60)
    print(f"🎉 构建完成: {len(succeeded)}/{len(node_results)} 个节点，分组 {group_name}")
    if failed_nodes:
        print(f"!️  {len(failed_nodes)} 个节点失败")
    script = os.path.abspath(sys.argv[0])
    print(f"下一步（运行 + 下载，单独调用）:")
    print(f'  python "{script}" --run --project "{args.project}" --episode {args.episode} '
          f'--canvas-uuid {canvas_uuid} '
          f'--groups {" ".join(str(g) for g in args.groups)} --download')
    print("=" * 60)
    return 0


# ============================================================
# 阶段三：--run（阻塞运行 → 解析终态 → 并发下载）
# ============================================================

def run_pipeline(args):
    project_root = os.path.join(os.getcwd(), "project", args.project)
    canvas_uuid = args.canvas_uuid

    # --run 模式忽略构建期参数（模型/模式在建节点时已固化到节点）
    if args.model or args.storyboard_mode or args.reference_image_mode:
        print("  ℹ️ --run 模式忽略 --model/--storyboard-mode/--reference-image-mode（构建期参数）")

    # 步骤1: 绑定画布
    print("=" * 60)
    print(f"步骤1: 绑定画布 {canvas_uuid}")
    print("=" * 60)
    r, err = run_libtv(["project", "use", canvas_uuid])
    if r is None:
        print(f"❌ 绑定失败: {err}")
        return 1
    print("  ✅ 已绑定")

    group_name = args.group_name or f"{args.episode}_组{'_'.join(str(g) for g in args.groups)}"
    node_names = [f"组{g}" for g in args.groups]

    # 步骤2: 分组存在性预检（group list 无副作用，避免对不存在分组触发建空组）
    r, _ = run_libtv(["group", "list"])
    known = extract_group_names(r)
    if known is not None and group_name not in known:
        print(f"❌ 分组不存在: {group_name}（画布上分组: {', '.join(sorted(known)) or '无'}）")
        print("   请先执行 --build 创建节点与分组")
        return 1

    # 步骤3: 运行分组（libtv >= 1.1.1 阻塞等待终态，stdout 输出终态 JSON）
    print("\n" + "=" * 60)
    print(f"步骤3: 运行分组 {group_name}（阻塞等待完成，stderr 每 ~3 分钟输出进度）")
    print("=" * 60)
    r, err = run_libtv(["group", group_name, "--run"])
    if r is None:
        print(f"❌ 运行失败: {err}")
        return 1
    print("  ✅ 分组运行结束")

    # 步骤4: 解析终态提取 URL；缺失节点回退单次查询（并发）
    urls_by_node = extract_urls_from_run_result(r)
    missing = [n for n in node_names if not urls_by_node.get(n)]
    if missing:
        print(f"\n  终态未覆盖 {len(missing)} 个节点，逐节点查询: {', '.join(missing)}")
        tasks = [
            (n, lambda n=n: {"urls": query_node_urls(n, args.poll_interval, args.poll_timeout)})
            for n in missing
        ]

        def on_query(name, res):
            urls = res.get("urls") or []
            if urls:
                urls_by_node[name] = urls
                print(f"  ✅ {name}: 已获取 URL")
            else:
                print(f"  ❌ {name}: 无生成结果", file=sys.stderr)

        run_concurrent(tasks, args.max_workers, on_done=on_query)

    failed = [n for n in node_names if not urls_by_node.get(n)]
    print("\n" + "=" * 60)
    print(f"生成结果: {len(node_names) - len(failed)}/{len(node_names)} 个节点有产物")
    print("=" * 60)
    for n in node_names:
        urls = urls_by_node.get(n)
        print(f"  {'✅' if urls else '❌'} {n}: {urls[0][:80] + '...' if urls and len(urls[0]) > 80 else (urls[0] if urls else '无结果')}")

    if not args.download:
        if failed:
            print(f"\n!️  {len(failed)} 个节点无产物: {', '.join(failed)}")
            return 1
        print("\n🎉 运行完成（未指定 --download，跳过下载）")
        return 0

    # 步骤5: 并发下载 + 写 manifest
    print("\n" + "=" * 60)
    print(f"步骤5: 并发下载视频（×{args.max_workers}）")
    print("=" * 60)
    output_dir = args.output_dir or os.path.join(project_root, args.episode, "视频")
    os.makedirs(output_dir, exist_ok=True)

    download_tasks = []
    for n in node_names:
        urls = urls_by_node.get(n)
        if not urls:
            continue
        output_path = os.path.join(output_dir, f"{n}.mp4")
        download_tasks.append((n, make_download_task(n, urls[0], output_path)))

    def on_download(name, res):
        if res.get("ok"):
            print(f"  ✅ {name} → {res['path']}")
        else:
            print(f"  ❌ {name} 下载失败: {res.get('error', '')[:120]}", file=sys.stderr)

    dl_results = run_concurrent(download_tasks, args.max_workers, on_done=on_download)
    downloaded = [
        {"displayName": name, "videoUrl": res["url"], "localPath": res["path"]}
        for name, res in dl_results.items() if res.get("ok")
    ]
    dl_failed = len(node_names) - len(downloaded)

    manifest = {
        "status": "success" if dl_failed == 0 else "partial",
        "episode": args.episode,
        "groupName": group_name,
        "output_dir": output_dir,
        "nodes": downloaded,
        "totalGroups": len(node_names),
        "downloaded": len(downloaded),
        "failed": dl_failed,
    }
    manifest_path = os.path.join(output_dir, "_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"📋 Manifest: {manifest_path}")
    if dl_failed == 0:
        print(f"🎉 全部完成: {len(downloaded)}/{len(node_names)}")
    else:
        print(f"!️  完成（{dl_failed} 个组失败）")
    print("=" * 60)
    return 1 if dl_failed else 0


# ============================================================
# CLI
# ============================================================

def validate_args(parser, args):
    modes = [bool(args.plan), bool(args.build), bool(args.run)]
    if sum(modes) != 1:
        if args.build and args.run:
            parser.error(
                "--build 与 --run 同时指定：--run 现为独立模式，"
                "请先 --build 构建完成，再单独调用 --run"
            )
        parser.error("必须且只能指定一种模式: --plan / --build / --run（互斥）")

    if args.build:
        for name, val in (("--canvas-uuid", args.canvas_uuid),
                          ("--model", args.model),
                          ("--storyboard-mode", args.storyboard_mode),
                          ("--reference-image-mode", args.reference_image_mode)):
            if not val:
                parser.error(f"--build 模式必填 {name}")
        if args.download:
            parser.error("--download 属于 --run 模式（构建与运行分离）")

    if args.plan:
        for name, val in (("--storyboard-mode", args.storyboard_mode),
                          ("--reference-image-mode", args.reference_image_mode)):
            if not val:
                parser.error(f"--plan 模式必填 {name}")
        if args.canvas_uuid or args.model:
            print("  ℹ️ --plan 模式忽略 --canvas-uuid/--model（纯本地解析，不调用 libtv）")
        if args.download:
            parser.error("--download 属于 --run 模式")

    if args.run:
        if not args.canvas_uuid:
            parser.error("--run 模式必填 --canvas-uuid")
        if args.no_group:
            parser.error("--no-group 仅适用于 --build（--run 依赖已建分组）")
        if args.refs or args.voice_refs:
            parser.error("--refs/--voice-refs 属于 --build/--plan 模式")


def main():
    parser = argparse.ArgumentParser(
        description="视频生成管线编排器 — 计划/构建/运行 三阶段分离",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  %(prog)s --plan --project 项目名 --episode EP01 --groups 7 8 9 \\\n"
            "      --storyboard-mode detailed --reference-image-mode visual_anchor\n"
            "  %(prog)s --build --project 项目名 --episode EP01 \\\n"
            "      --canvas-uuid <UUID> --model \"Seedance 2.0 VIP\" \\\n"
            "      --storyboard-mode detailed --reference-image-mode visual_anchor \\\n"
            "      --groups 7 8 9 --refs \"组7:场景_现代南京,角色_一岛\"\n"
            "  %(prog)s --run --project 项目名 --episode EP01 --canvas-uuid <UUID> \\\n"
            "      --groups 7 8 9 --download"
        ),
    )

    mode = parser.add_argument_group("模式（三选一，互斥）")
    mode.add_argument("--plan", action="store_true",
                      help="生成执行计划（各组参考图/音色自动匹配结果 + 建议 --refs/--voice-refs）。纯本地，不调用 libtv")
    mode.add_argument("--build", action="store_true",
                      help="并发上传参考 → 并发创建节点（upsert）→ 幂等建组。不运行生成")
    mode.add_argument("--run", action="store_true",
                      help="运行已有分组（阻塞等待终态）+ 可选 --download。须在 --build 之后单独调用")

    parser.add_argument("--project", required=True, help="项目名，对应 project/<名>/")
    parser.add_argument("--episode", default="EP01", help="剧集号（默认 EP01）")
    parser.add_argument("--canvas-uuid", default=None,
                        help="画布 UUID（--build/--run 必填）。调用方先经 meta_query(scope=config) 查 "
                             "episodes.{剧集}.canvas_uuid，无则创建画布后经 meta_update_config 写回")
    parser.add_argument("--groups", nargs="+", type=int, required=True,
                        help="组号列表，如 7 8 9（顺序即分组的整组执行顺序）")
    parser.add_argument("--model", default=None,
                        help='视频模型 modelName（中文名，--build 必填，如 "Seedance 2.0 VIP"）；禁止传 modelKey')
    parser.add_argument("--storyboard-mode", choices=["detailed", "simplified"], default=None,
                        help="分镜脚本模式（--build/--plan 必填）。detailed=组{N}.json，simplified=组{N}.md")
    parser.add_argument("--reference-image-mode", choices=["visual_anchor", "storyboard_images", "none"], default=None,
                        help="参考图模式（--build/--plan 必填）。visual_anchor=视觉锚点自动扫描，"
                             "storyboard_images=分镜图自动扫描，none=不做自动扫描")
    parser.add_argument("--refs", action="append", default=None,
                        help='参考图映射，可重复，格式 "组N:类型_名,类型_名"（如 "组1:角色_掌柜,场景_茶馆"）；'
                             "显式指定的组不做自动匹配；选角参考图自动过滤")
    parser.add_argument("--voice-refs", nargs="*", default=None,
                        help="音色参考角色列表（如 吉小泰 妈妈）；仅上传指定角色音色，未指定时跳过")
    parser.add_argument("--no-auto-refs", action="store_true",
                        help="关闭参考图自动匹配：未显式 --refs 的组以纯文生视频生成（旧行为）")
    parser.add_argument("--ratio", default=None, help="画面比例（默认 16:9）")
    parser.add_argument("--resolution", default=None, help="分辨率（默认 480p；Minimax 系自动映射 768P）")
    parser.add_argument("--sound", default=None, help="音频开关 on/off（默认 on）")
    parser.add_argument("--no-group", action="store_true",
                        help="（--build）跳过建组，仅创建独立节点")
    parser.add_argument("--group-name", default=None,
                        help="自定义分组名（默认 {剧集}_组N_N_N）")
    parser.add_argument("--download", action="store_true",
                        help="（--run）运行完成后并发下载视频到 project/<项目>/<剧集>/视频/ 并写 _manifest.json")
    parser.add_argument("--output-dir", default=None,
                        help="（--run）自定义下载目录（默认: project/<项目>/<剧集>/视频/）")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS_DEFAULT,
                        help=f"并发线程数（默认 {MAX_WORKERS_DEFAULT}，上限 {MAX_WORKERS_LIMIT}）")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="（--build）忽略画布节点缓存，强制全量拉取重建")
    parser.add_argument("--poll-interval", type=int, default=5,
                        help="（--run）节点结果查询重试间隔秒（默认 5）")
    parser.add_argument("--poll-timeout", type=int, default=600,
                        help="（--run）节点结果查询总超时秒（默认 600）")

    args = parser.parse_args()
    validate_args(parser, args)
    args.max_workers = max(1, min(args.max_workers, MAX_WORKERS_LIMIT))

    if args.plan:
        sys.exit(plan_pipeline(args))
    if args.build:
        sys.exit(build_pipeline(args))
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
