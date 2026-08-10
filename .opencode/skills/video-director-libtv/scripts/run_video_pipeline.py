#!/usr/bin/env python3
"""视频生成管线编排器 — 一站式完整流程

依赖: libtv >= 1.1.1（group --run 现为阻塞等待命令，CLI 内部完成轮询）

画布模型:
  - 每个项目对应一个 libtv 工作区（workspace）
  - 每个剧集对应一个 libtv 画布（canvas）
  - 画布 UUID 存储在 project_config.json 的 episodes.{剧集号}.canvas_uuid

用法:
  # 完整流程（上传素材 → 创建节点（一次性含引用行） → 建组）
  # 注意: --model 传 modelName（中文名），如 "Seedance 2.0 VIP"；不要传 modelKey
  # --canvas-uuid 可选：不传时自动从 project_config.json 的 episodes 映射查找
  python run_video_pipeline.py --build ^
    --project "项目名" --episode EP01 ^
    --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 --resolution 480p ^
    --refs "组7:场景_现代南京长江边,角色_一岛,角色_郑和,道具_平板" ^
    --refs "组8:场景_现代南京长江边,角色_一岛,角色_郑和"

  # 完整流程 + 音色参考
  python run_video_pipeline.py --build ^
    --project "项目名" --episode EP01 ^
    --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 ^
    --refs "组7:场景_现代南京,角色_一岛" ^
    --voice-refs 吉小泰 妈妈 女儿

  # 完整流程 + 运行（group --run 阻塞等待）
  python run_video_pipeline.py --build ... --run

  # 完整流程 + 运行 + 自动下载视频到 project/<项目>/<剧集>/视频/
  python run_video_pipeline.py --build ... --run --download

  # 精简模式分镜（自动读取 project_config.json 的 storyboard_mode，
  # 也可用 --storyboard-mode 显式指定）
  python run_video_pipeline.py --build ^
    --project "项目名" --episode EP01 ^
    --groups 1 2 3 --model "Seedance 2.0 VIP" --ratio 16:9 ^
    --storyboard-mode simplified

  # 仅创建节点，不建组（--no-group）
  python run_video_pipeline.py --build ^
    --project "项目名" --episode EP01 ^
    --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 --resolution 480p ^
    --refs "组7:场景_现代南京长江边,角色_一岛,角色_郑和,道具_平板" ^
    --no-group

分镜模式优先级: --storyboard-mode > project_config.json > 默认 detailed
  detailed   → 加载 组{N}.json（结构化 JSON）
  simplified → 加载 组{N}.md（讲戏式 Markdown，全文作为 prompt）

设计原则:
  - 参考图和音色的选取由 Agent 判断，脚本不做自动匹配
  - --refs 由 Agent 根据分组内容显式指定每个分组的参考图（仅上传指定的参考图，非全量上传）
  - --voice-refs 由 Agent 根据分组台词显式指定需要的音色参考（仅上传指定的音色参考）
  - ⛔ 选角参考图（{角色名}_选角.png）自动过滤，禁止用于视频生成
  - --no-group 跳过建组步骤，仅创建独立节点（适用于需要手动编排节点的场景）
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

CONSTRAINT = "画面严禁出现任何字幕，无配乐"
SEPARATOR = "---"

CONFIG_DEFAULTS = {
    # model 字段必须是 modelName（中文名），不是 modelKey
    # libtv 1.1.1+ 直接使用该值作为 modelName，不做 modelKey → modelName 转换
    "model": "Seedance 2.0 VIP",
    "modeType": "mixed2video",
    "count": 1,
    "ratio": "16:9",
    "resolution": "480p",
    "enableSound": "on",
}

POLL_INTERVAL = 30
POLL_TIMEOUT = 600

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


def run_libtv(args_list):
    result = subprocess.run(
        ["libtv"] + args_list, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"  libtv 失败: {' '.join(args_list[:4])}...")
        print(f"  stderr: {result.stderr[:400]}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout


def poll_node(node_name, interval=POLL_INTERVAL, timeout=POLL_TIMEOUT):
    # libtv >= 1.1.1: group --run 已阻塞等待完成，此处轮询通常立即返回
    start = time.time()
    while time.time() - start < timeout:
        result = run_libtv(["node", node_name])
        if result is None:
            print(f"  ⚠ {node_name} 查询失败，重试中...")
            time.sleep(interval)
            continue
        urls = result.get("data", {}).get("url", [])
        if urls and any(urls):
            return urls
        elapsed = int(time.time() - start)
        print(f"  ⏳ {node_name} 生成中... ({elapsed}s)")
        time.sleep(interval)
    print(f"  ❌ {node_name} 超时（{timeout}s）")
    return []


def download_video(url, output_path):
    try:
        print(f"  ⬇️  下载: {url[:80]}...")
        urllib.request.urlretrieve(url, output_path)
        return True
    except Exception as e:
        print(f"  ❌ 下载失败: {e}")
        return False


def parse_refs(refs_args):
    result = {}
    for ref_str in refs_args:
        parts = ref_str.split(":", 1)
        if len(parts) != 2:
            print(f"  ⚠ --refs 格式错误: {ref_str}，跳过")
            continue
        group_key = parts[0].strip()
        refs = [r.strip() for r in parts[1].split(",") if r.strip()]
        result[group_key] = refs
    return result


def scan_project_refs(project_root, episode=None):
    found = {}
    for ref_type, rel_path in REFERENCE_TYPE_PATHS.items():
        dir_path = os.path.join(project_root, rel_path)
        if not os.path.isdir(dir_path):
            continue
        for f in sorted(os.listdir(dir_path)):
            if not f.lower().endswith(".png"):
                continue
            name_without_ext = os.path.splitext(f)[0]
            # ⛔ 选角参考图（{角色名}_选角.png）禁止用于视频生成
            # 选角资产为白T恤+灰背景，仅用于角色面部特征确立，不适合作为视频画面参考
            if "_选角" in name_without_ext:
                print(f"  ⛔ 跳过选角参考图: {f}（禁止用于视频生成）", file=sys.stderr)
                continue
            # 新格式: {道具名}_{出现场合}_基准.png → 需剥离 _{出现场合}_基准
            # 出现场合: 全剧 / EP01 / EP01,EP13(文件名取首集)
            clean_name = re.sub(r"_(全剧|EP\d+)_基准$", "", name_without_ext, flags=re.IGNORECASE)
            # 剧集级格式: {道具名}_{剧集号}集.png → 需剥离 _{剧集号}集
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
                node_name = f"分镜_{name_without_ext}"
                found[node_name] = os.path.join(sb_dir, f)

        # 扫描视觉锚点图（剧集级目录）
        va_dir = os.path.join(project_root, episode, VISUAL_ANCHOR_PATH)
        if os.path.isdir(va_dir):
            for f in sorted(os.listdir(va_dir)):
                if not f.lower().endswith(".png"):
                    continue
                name_without_ext = os.path.splitext(f)[0]
                # 视觉锚点文件名格式：锚点_场{N}_{场景名}
                # 节点名格式：视觉锚点_场{N}
                match = re.match(r"锚点_场(\d+)", name_without_ext)
                if match:
                    scene_num = match.group(1)
                    node_name = f"视觉锚点_场{scene_num}"
                    found[node_name] = os.path.join(va_dir, f)

    return found


def match_ref_name(ref_name, available_nodes):
    if ref_name in available_nodes:
        return [ref_name]
    keywords = ref_name.split("_", 1)
    matches = []
    for node_name in available_nodes:
        if all(kw in node_name for kw in keywords if kw):
            matches.append(node_name)
    return matches


def build_canvas_cache(canvas_uuid):
    cache = {}
    data = run_libtv(["project", canvas_uuid])
    if data:
        for n in data.get("nodes", []):
            name = n.get("name", "")
            nid = n.get("id", "")
            if name and nid:
                cache[name] = nid
    return cache


def upload_references(project_root, canvas_cache, needed_refs=None, episode=None):
    """上传参考图到画布。

    Args:
        project_root: 项目根路径
        canvas_cache: 画布已有节点缓存，用于复用检测
        needed_refs: 需要上传的参考图节点名集合（如 {"角色_掌柜", "场景_茶馆"}）。
                     为 None 时上传全部（向后兼容，但不推荐）。
                     提供时仅上传该集合中的参考图，避免全量上传无关素材。
        episode: 剧集号（如 EP04），用于扫描剧集级分镜图目录
    """
    ref_nodes = {}
    all_files = scan_project_refs(project_root, episode=episode)

    # 过滤：仅上传 needed_refs 中指定的参考图
    if needed_refs is not None:
        # 先尝试精确匹配，再用 match_ref_name 做模糊匹配收集候选
        needed_set = set(needed_refs)
        # 收集所有被需要的节点名（含模糊匹配）
        matched_names = set()
        for node_name in all_files:
            if node_name in needed_set:
                matched_names.add(node_name)
                continue
            # 模糊匹配：检查 needed_refs 中是否有匹配该节点名的
            for needed in needed_set:
                keywords = needed.split("_", 1)
                if all(kw in node_name for kw in keywords if kw):
                    matched_names.add(node_name)
                    break
        files_to_upload = {k: v for k, v in all_files.items() if k in matched_names}
        skipped_count = len(all_files) - len(files_to_upload)
    else:
        files_to_upload = all_files
        skipped_count = 0

    print("\n" + "=" * 60)
    if needed_refs is not None:
        print(f"上传参考图到画布（按需上传，跳过 {skipped_count} 个无关素材）")
    else:
        print("上传参考图到画布（全量上传）")
    print("=" * 60)

    for node_name, file_path in files_to_upload.items():
        if node_name in canvas_cache:
            existing_id = canvas_cache[node_name]
            ref_nodes[node_name] = existing_id
            print(f"  {node_name} → 已存在，复用 (ID={existing_id[:16]}...)")
            continue

        rel = os.path.relpath(file_path, project_root)
        print(f"  {rel} → {node_name}...", end=" ")
        result = run_libtv(["upload", node_name, "-t", "image", "-f", file_path])
        if result:
            node_id = result.get("data", {}).get("id", result.get("nodeId", "?"))
            ref_nodes[node_name] = node_id
            print(f"✅ (ID={node_id[:12] if node_id != '?' else '?'}...)")
        else:
            print("❌")

    print(f"  参考图就绪: {len(ref_nodes)} 个")
    return ref_nodes


def upload_voice_refs(project_root, role_names=None, canvas_cache=None):
    """上传音色参考到画布，返回上传成功的节点名列表。

    Args:
        project_root: 项目根路径
        role_names: 指定上传的角色名列表；为 None 时自动扫描音色参考目录
        canvas_cache: 画布已有节点缓存，用于复用检测

    支持两种文件命名模式（自动识别）：
      - {角色名}音色.{ext}     (如 掌柜音色.wav, 皇帝音色.mp3)
      - {角色名}-音色参考.{ext} (如 吉小泰-音色参考.wav)

    支持多种音频格式：.wav, .mp3, .m4a, .ogg, .flac
    """
    voice_ref_dir = os.path.join(project_root, "全局依赖", "音色参考")
    voice_nodes = []

    print("\n" + "=" * 60)
    print("上传音色参考到画布")
    print("=" * 60)

    if not os.path.isdir(voice_ref_dir):
        print(f"  ⚠ 音色参考目录不存在: {voice_ref_dir}")
        return voice_nodes

    # 确定要上传的角色及其文件路径
    to_upload = {}  # {角色名: 文件路径}

    if role_names is not None:
        # 显式指定：查找对应文件
        for role_name in role_names:
            role_name = role_name.strip()
            if not role_name:
                continue
            found = False
            # 尝试两种文件命名模式
            for pattern in [f"{role_name}-音色参考", f"{role_name}音色"]:
                for ext in (".wav", ".mp3", ".m4a", ".ogg", ".flac"):
                    candidate = os.path.join(voice_ref_dir, f"{pattern}{ext}")
                    if os.path.exists(candidate):
                        to_upload[role_name] = candidate
                        found = True
                        break
                if found:
                    break
            if not found:
                print(f"  ⚠ 未找到 {role_name} 的音色参考文件（目录: {voice_ref_dir}）")
    else:
        # 自动扫描：查找目录下所有音频文件
        scanned = auto_scan_voice_dir(voice_ref_dir)
        if not scanned:
            print(f"  ⚠ 音色参考目录下未找到音频文件")
        to_upload = scanned

    # 逐文件上传
    for role_name, file_path in to_upload.items():
        node_name = f"音色_{role_name}"

        # 复用检测
        if canvas_cache and node_name in canvas_cache:
            voice_nodes.append(node_name)
            print(f"  {node_name} → 已存在，复用")
            continue

        rel = os.path.relpath(file_path, project_root)
        print(f"  {rel} → {node_name}...", end=" ")
        result = run_libtv(["upload", node_name, "-t", "audio", "-f", file_path])
        if result:
            voice_nodes.append(node_name)
            print("✅")
        else:
            print("❌")

    print(f"  音色参考就绪: {len(voice_nodes)} 个")
    return voice_nodes


def auto_scan_voice_dir(voice_ref_dir):
    """扫描音色参考目录，返回 {角色名: 文件路径} 字典。

    支持两种文件命名模式：
      - {角色名}音色.{ext}     (如 掌柜音色.wav, 皇帝音色.mp3)
      - {角色名}-音色参考.{ext} (如 吉小泰-音色参考.wav)

    支持的音频格式：.wav, .mp3, .m4a, .ogg, .flac
    """
    voice_files = {}
    if not os.path.isdir(voice_ref_dir):
        return voice_files

    for fname in sorted(os.listdir(voice_ref_dir)):
        base, ext = os.path.splitext(fname)
        ext_lower = ext.lower()
        if ext_lower not in (".wav", ".mp3", ".m4a", ".ogg", ".flac"):
            continue

        role_name = None
        # 模式 1: {角色名}-音色参考.ext
        m = re.match(r"(.+?)-音色参考$", base)
        if m:
            role_name = m.group(1).strip()
        else:
            # 模式 2: {角色名}音色.ext
            m = re.match(r"(.+?)音色$", base)
            if m:
                role_name = m.group(1).strip()

        if role_name:
            voice_files[role_name] = os.path.join(voice_ref_dir, fname)

    return voice_files


def build_ref_description(ref_name, idx):
    """根据参考图名称生成 Image N 引用描述。
    --left 顺序决定 {{Image N}} 编号，第一个 --left 为 {{Image 1}}

    格式统一为 "{名称}{类型}参考{{Image N}}"，简洁明确。
    分镜图按镜头编号引用：镜头1参考{{Image N}}、镜头2参考{{Image N}}...
    """
    if "场景" in ref_name:
        scene_name = ref_name.replace("场景_", "")
        return f"{scene_name}场景参考{{{{Image {idx}}}}}"
    elif "角色" in ref_name:
        char_name = ref_name.replace("角色_", "").replace("_基准", "")
        return f"{char_name}角色参考{{{{Image {idx}}}}}"
    elif "道具" in ref_name:
        prop_name = ref_name.replace("道具_", "").replace("_基准", "")
        # 剥离出现场合标记（全剧 / EP01 等）和剧集号后缀
        prop_name = re.sub(r"_(全剧|EP\d+)$", "", prop_name)
        prop_name = re.sub(r"_EP\d+集$", "", prop_name)
        return f"{prop_name}道具参考{{{{Image {idx}}}}}"
    elif "视觉锚点" in ref_name:
        # 视觉锚点节点名格式：视觉锚点_场{N} → 提取场号
        match = re.search(r"场(\d+)", ref_name)
        scene_num = match.group(1) if match else str(idx)
        return f"场{scene_num}视觉锚点参考{{{{Image {idx}}}}}"
    elif "分镜" in ref_name:
        # 分镜图节点名格式：分镜_组{N}_镜{M} → 提取镜号
        match = re.search(r"镜(\d+)", ref_name)
        shot_num = match.group(1) if match else str(idx)
        return f"镜头{shot_num}参考{{{{Image {idx}}}}}"
    elif "风格" in ref_name:
        style_name = ref_name.replace("风格_", "")
        return f"{style_name}风格参考{{{{Image {idx}}}}}"
    else:
        return f"参考素材{{{{Image {idx}}}}}"


def sort_ref_names(ref_names):
    """按类型排序参考图：分镜图 → 视觉锚点 → 角色 → 道具 → 其他（场景/风格等）。
    分镜图内部按镜号排序，视觉锚点按场号排序。
    """
    def sort_key(name):
        if "分镜" in name:
            match = re.search(r"镜(\d+)", name)
            shot = int(match.group(1)) if match else 0
            return (0, shot)
        elif "视觉锚点" in name:
            match = re.search(r"场(\d+)", name)
            scene = int(match.group(1)) if match else 0
            return (1, scene)
        elif "角色" in name:
            return (2, 0)
        elif "道具" in name:
            return (3, 0)
        else:
            return (4, 0)
    return sorted(ref_names, key=sort_key)


def build_prompt(group_json, ref_names, voice_ref_names=None, audio_connector="，"):
    """构建完整 prompt：引用行 + 约束行 + 分隔线 + 组内容。
    引用行中的 {{Image N}} 编号与 --left 顺序一致。
    参考图排序：分镜图（按镜号）→ 视觉锚点（按场号）→ 角色 → 道具 → 其他。
    含音色参考时在引用行末尾追加 {{Audio N}} 引用。
    支持 JSON 格式（dict）和 MD 格式（含 _raw_content 键的 dict）。"""
    # 精简模式：使用原始 MD 文本作为 prompt 内容
    if isinstance(group_json, dict) and group_json.get("_format") == "md":
        raw_content = group_json.get("_raw_content", "")
    else:
        raw_content = json.dumps(group_json, ensure_ascii=False)

    # 按类型排序：分镜图 → 角色 → 道具 → 其他
    ordered_refs = sort_ref_names(ref_names) if ref_names else []

    if ordered_refs:
        ref_parts = [build_ref_description(n, i+1) for i, n in enumerate(ordered_refs)]
        ref_line = "、".join(ref_parts)
        if voice_ref_names:
            audio_parts = []
            for i, vn in enumerate(voice_ref_names):
                role = vn.replace("音色_", "", 1) if vn.startswith("音色_") else vn
                audio_parts.append(f"{role}音色参考{{{{Audio {i+1}}}}}")
            ref_line += audio_connector + "、".join(audio_parts)
        return f"{ref_line}\n\n{CONSTRAINT}\n{SEPARATOR}\n{raw_content}"
    if voice_ref_names:
        audio_parts = []
        for i, vn in enumerate(voice_ref_names):
            role = vn.replace("音色_", "", 1) if vn.startswith("音色_") else vn
            audio_parts.append(f"{role}音色参考{{{{Audio {i+1}}}}}")
        ref_line = "、".join(audio_parts)
        return f"{ref_line}\n\n{CONSTRAINT}\n{SEPARATOR}\n{raw_content}"
    return f"{CONSTRAINT}\n{SEPARATOR}\n{raw_content}"


def calc_duration(group_json):
    raw = group_json.get("组时长", "5")
    try:
        duration = int(raw)
    except (ValueError, TypeError):
        shots = group_json.get("镜头列表", [])
        if shots:
            duration = sum(int(s.get("时长", 5)) for s in shots)
        else:
            duration = 5
    return max(4, min(15, duration))


def _load_project_config(project_root):
    """从 .meta/projects/{uuid}/project_config.json 读取项目配置。

    通过项目名反查 UUID 来定位配置文件。返回配置 dict，找不到时返回 None。
    """
    project_name = os.path.basename(os.path.normpath(project_root))
    meta_projects_dir = os.path.join(os.getcwd(), ".meta", "projects")

    if not os.path.isdir(meta_projects_dir):
        return None

    for uuid_dir in os.listdir(meta_projects_dir):
        project_json_path = os.path.join(meta_projects_dir, uuid_dir, "project.json")
        if not os.path.isfile(project_json_path):
            continue
        try:
            with open(project_json_path, "r", encoding="utf-8") as f:
                pj = json.load(f)
            if pj.get("name") == project_name:
                config_path = os.path.join(meta_projects_dir, uuid_dir, "project_config.json")
                if os.path.isfile(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                break
        except (json.JSONDecodeError, OSError):
            continue
    return None


def lookup_episode_canvas_uuid(project_root, episode):
    """从 project_config.json 的 episodes 映射查找指定剧集的画布 UUID。

    画布模型：每个项目对应一个工作区，每个剧集对应一个画布。
    画布 UUID 存储在 episodes.{剧集号}.canvas_uuid 中。

    返回 (canvas_uuid, config) 元组。canvas_uuid 为 None 表示该集尚无画布。
    同时兼容旧的顶层 canvas_uuid 字段（向后兼容）。
    """
    config = _load_project_config(project_root)
    if config is None:
        return None, None

    # 优先从 episodes 映射查找
    episodes = config.get("episodes", {})
    if episode in episodes:
        canvas_uuid = episodes[episode].get("canvas_uuid", "")
        if canvas_uuid:
            return canvas_uuid, config

    # 向后兼容：旧的顶层 canvas_uuid 字段
    legacy_uuid = config.get("canvas_uuid", "")
    if legacy_uuid:
        return legacy_uuid, config

    return None, config


def load_storyboard_mode(project_root, cli_override=None):
    """从 project_config.json 读取 storyboard_mode 字段。

    优先级：CLI 参数 > project_config.json > 默认值 "detailed"
    返回 ("detailed" | "simplified")
    """
    if cli_override:
        return cli_override

    cfg = _load_project_config(project_root)
    if cfg:
        mode = cfg.get("storyboard_mode", "detailed")
        if mode in ("detailed", "simplified"):
            return mode

    return "detailed"


def load_group_file(groups_dir, group_name, storyboard_mode):
    """按 storyboard_mode 加载对应格式的组文件。
    
    detailed  → 组{N}.json
    simplified → 组{N}.md
    
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
        # detailed 模式（默认）
        group_path = os.path.join(groups_dir, f"{group_name}.json")
        if not os.path.exists(group_path):
            return None, None
        with open(group_path, "r", encoding="utf-8") as f:
            group = json.load(f)
        return group, "json"


def extract_scene_number(group_dict):
    """从组文件内容提取场号。
    
    detailed 模式：从 JSON 的 "场号" 字段提取
    simplified 模式：从 Markdown 文本中正则匹配 "场号：N" 或 "场N"
    
    返回场号字符串（如 "1"），找不到时返回 None。
    """
    if group_dict is None:
        return None
    
    # detailed 模式：JSON dict 直接取场号字段
    if isinstance(group_dict, dict):
        if group_dict.get("_format") == "md":
            # simplified 模式：从 raw_md 中正则匹配
            raw_md = group_dict.get("_raw_content", "")
            # 尝试匹配 "场号：1" 或 "场号: 1"
            match = re.search(r"场号[：:]\s*(\d+)", raw_md)
            if match:
                return match.group(1)
            # 尝试匹配 "场1" 或 "## 场1"
            match = re.search(r"场(\d+)", raw_md)
            if match:
                return match.group(1)
        else:
            # detailed 模式：JSON 字段
            scene = group_dict.get("场号")
            if scene is not None:
                return str(scene)
    
    return None


def load_reference_image_mode(project_root):
    """从 project_config.json 读取 reference_image_mode。
    
    优先级：reference_image_mode 字段 > use_storyboard_images（向后兼容）> 默认 "visual_anchor"
    
    返回 ("visual_anchor" | "storyboard_images" | "none")
    """
    config = _load_project_config(project_root)
    if config:
        mode = config.get("reference_image_mode")
        if mode in ("visual_anchor", "storyboard_images", "none"):
            return mode
        # 向后兼容：use_storyboard_images=true → storyboard_images
        if config.get("use_storyboard_images", False):
            return "storyboard_images"
    return "visual_anchor"


def build_pipeline(args):
    project_root = os.path.join(os.getcwd(), "project", args.project)
    groups_dir = os.path.join(project_root, args.episode, "分镜", "分组")
    failed = 0  # 下载阶段失败计数，0 表示无失败或未执行下载

    if not os.path.isdir(groups_dir):
        print(f"❌ 分组目录不存在: {groups_dir}")
        sys.exit(1)

    # 画布 UUID 查找：优先 CLI 参数，其次从 episodes 映射自动查找
    canvas_uuid = args.canvas_uuid
    if not canvas_uuid:
        canvas_uuid, _ = lookup_episode_canvas_uuid(project_root, args.episode)
        if canvas_uuid:
            print(f"  自动查找画布 UUID: {canvas_uuid}（来自 episodes.{args.episode}.canvas_uuid）")
        else:
            print("❌ 未提供 --canvas-uuid，且 project_config.json 中未找到该集的画布映射")
            print(f"   请先创建画布，或在 project_config.json 的 episodes.{args.episode} 中配置 canvas_uuid")
            sys.exit(1)

    custom_refs = parse_refs(args.refs) if args.refs else {}

    # ========== 步骤0: 确定分镜模式 ==========
    storyboard_mode = load_storyboard_mode(project_root, args.storyboard_mode)
    print(f"分镜模式: {storyboard_mode}（{'组{N}.json' if storyboard_mode == 'detailed' else '组{N}.md'}）")

    # ========== 步骤1: 绑定画布 ==========
    print("\n" + "=" * 60)
    print(f"步骤1: 绑定画布 {canvas_uuid}")
    print("=" * 60)
    r = run_libtv(["project", "use", canvas_uuid])
    if not r:
        print("❌ 绑定失败")
        sys.exit(1)
    print(f"  ✅ 已绑定 {canvas_uuid}")

    # ========== 步骤2: 建立画布缓存 + 上传参考图（按需）==========
    canvas_cache = build_canvas_cache(canvas_uuid)

    # 读取 reference_image_mode 配置
    reference_image_mode = load_reference_image_mode(project_root)
    print(f"参考图模式: {reference_image_mode}")

    # 收集所有分组实际需要的参考图名，实现按需上传（避免全量上传无关素材）
    all_needed_refs = set()
    for ref_list in custom_refs.values():
        all_needed_refs.update(ref_list)

    # storyboard_images 模式：自动收集各组对应分镜图作为需要上传的参考
    storyboard_refs_by_group = {}
    if reference_image_mode == "storyboard_images":
        sb_dir = os.path.join(project_root, args.episode, STORYBOARD_IMAGE_PATH)
        if os.path.isdir(sb_dir):
            for f in sorted(os.listdir(sb_dir)):
                if not f.lower().endswith(".png"):
                    continue
                name = os.path.splitext(f)[0]
                # 分镜图文件名格式：组{N}_镜{M} → 提取组号
                match = re.match(r"组(\d+)_镜(\d+)", name)
                if match:
                    group_num = match.group(1)
                    node_name = f"分镜_{name}"
                    storyboard_refs_by_group.setdefault(f"组{group_num}", []).append(node_name)
                    all_needed_refs.add(node_name)
            for g, refs in storyboard_refs_by_group.items():
                print(f"  📋 {g} 分镜图: {len(refs)} 张（自动扫描）")

    # visual_anchor 模式：扫描视觉锚点图，按场号建立映射
    visual_anchor_by_scene = {}
    if reference_image_mode == "visual_anchor":
        va_dir = os.path.join(project_root, args.episode, VISUAL_ANCHOR_PATH)
        if os.path.isdir(va_dir):
            for f in sorted(os.listdir(va_dir)):
                if not f.lower().endswith(".png"):
                    continue
                name = os.path.splitext(f)[0]
                match = re.match(r"锚点_场(\d+)", name)
                if match:
                    scene_num = match.group(1)
                    node_name = f"视觉锚点_场{scene_num}"
                    visual_anchor_by_scene[scene_num] = node_name
                    all_needed_refs.add(node_name)
            print(f"  📋 视觉锚点: {len(visual_anchor_by_scene)} 张（自动扫描，按场号映射）")

    ref_nodes = upload_references(
        project_root, canvas_cache,
        needed_refs=all_needed_refs if all_needed_refs else None,
        episode=args.episode,
    )

    # ========== 步骤2.5: 上传音色参考（按需）==========
    # 音色参考仅上传 --voice-refs 显式指定的角色，不做自动全量扫描
    voice_ref_nodes = []
    if args.voice_refs:
        voice_ref_nodes = upload_voice_refs(project_root, args.voice_refs, canvas_cache)
    else:
        print("\n  ℹ️ 未指定 --voice-refs，跳过音色参考上传")
        print("  如需音色参考，请通过 --voice-refs 显式指定角色名")

    # ========== 步骤3: 创建 video 节点（一次性完成 + 连线 + 引用行） ==========
    print("\n" + "=" * 60)
    print("步骤3: 创建 video 节点（一次性完成 + 连线 + 引用行）")
    print("=" * 60)

    created_nodes = []
    # model 字段已经是 modelName（中文名），libtv 1.1.1+ 直接使用，无需任何转换
    # project_config.json 的 model 字段或 --model 命令行参数都应传 modelName
    model = args.model or CONFIG_DEFAULTS["model"]
    ratio = args.ratio or CONFIG_DEFAULTS["ratio"]
    resolution = args.resolution or CONFIG_DEFAULTS["resolution"]
    sound = args.sound or CONFIG_DEFAULTS["enableSound"]
    count = CONFIG_DEFAULTS["count"]

    for gid in args.groups:
        group_name = f"组{gid}"

        group, fmt = load_group_file(groups_dir, group_name, storyboard_mode)
        if group is None:
            expected_ext = ".json" if storyboard_mode == "detailed" else ".md"
            print(f"  ⚠ {group_name}{expected_ext} 不存在（模式: {storyboard_mode}），跳过")
            continue
        if fmt == "md":
            print(f"  📄 {group_name}.md（精简模式）")

        duration = calc_duration(group)

        # 确定该组要连线的参考图（由 agent 通过 --refs 显式指定）
        refs_for_group = custom_refs.get(group_name, custom_refs.get(str(gid), []))
        available_refs = []
        for r in refs_for_group:
            available_refs.extend(match_ref_name(r, ref_nodes))
        available_refs = list(dict.fromkeys(available_refs))

        # storyboard_images 模式：自动将该组的分镜图加入参考
        if reference_image_mode == "storyboard_images":
            sb_refs = storyboard_refs_by_group.get(group_name, [])
            for sb_name in sb_refs:
                if sb_name in ref_nodes and sb_name not in available_refs:
                    available_refs.append(sb_name)
            if sb_refs:
                print(f"    📋 {group_name} 分镜图连线: {len(sb_refs)} 张")

        # visual_anchor 模式：按场号自动将该组的视觉锚点加入参考
        if reference_image_mode == "visual_anchor":
            scene_num = extract_scene_number(group)
            if scene_num and scene_num in visual_anchor_by_scene:
                va_node = visual_anchor_by_scene[scene_num]
                if va_node in ref_nodes and va_node not in available_refs:
                    available_refs.append(va_node)
                    print(f"    📋 {group_name} 视觉锚点连线: 场{scene_num}")
            elif scene_num:
                print(f"    ⚠ {group_name} 场号{scene_num} 未找到对应视觉锚点图", file=sys.stderr)

        if not available_refs:
            print(f"  ⚠ {group_name} 未指定参考图（--refs），将以纯文生视频模式生成", file=sys.stderr)

        # 音色参考连线：由 agent 通过 --voice-refs 统一指定，脚本不做逐组匹配
        # 所有已上传的音色参考统一连入每个组，agent 负责判断哪些角色实际有台词
        group_voice_refs = voice_ref_nodes[:]
        if group_voice_refs:
            print(f"    🎤 音色参考: {', '.join(group_voice_refs)}（统一连线，由 agent 判断适用性）")

        # --left 顺序决定 {{Image N}} 和 {{Audio N}} 编号
        # build_prompt 内部按 分镜图→角色→道具→其他 排序，--left 连线顺序必须与之一致
        ordered_refs = sort_ref_names(available_refs) if available_refs else []
        prompt = build_prompt(group, available_refs, group_voice_refs)

        mode_type = "mixed2video" if available_refs else "text2video"

        cmd = [
            "libtv", "node", "create", group_name, "-t", "video",
            "--prompt", prompt,
            "--set", f"model={model}",
            "--set", f"modeType={mode_type}",
            "--set", f"count={count}",
            "--set", f"ratio={ratio}",
            "--set", f"resolution={resolution}",
            "--set", f"duration={duration}",
            "--set", f"enableSound={sound}",
        ]
        for ref_name in ordered_refs:
            cmd += ["--left", ref_name]
        for vn in group_voice_refs:
            cmd += ["--left", vn]

        all_left = list(ordered_refs) + list(group_voice_refs)
        refs_desc = ", ".join(all_left) if all_left else "(无参考素材)"
        print(f"\n  创建 {group_name}（{duration}s）")
        print(f"    模式: {mode_type} | 连线: {refs_desc}")

        result = run_libtv(cmd[1:])
        if result:
            print(f"    ✅ {group_name} 创建成功")
            created_nodes.append((group_name, available_refs))
        else:
            print(f"    ❌ {group_name} 创建失败")

    if not created_nodes:
        print("❌ 未创建任何节点")
        sys.exit(1)

    # ========== 步骤4: 建组（可选，--no-group 跳过）==========
    group_name = None
    if args.no_group:
        print("\n" + "=" * 60)
        print("步骤4: 建组（已跳过 --no-group）")
        print("=" * 60)
        print(f"  ⏭️ 跳过建组，共创建 {len(created_nodes)} 个独立节点")
        print(f"  节点列表: {', '.join(n for n, _ in created_nodes)}")
    else:
        print("\n" + "=" * 60)
        print("步骤4: 建组")
        print("=" * 60)

        node_names = [n for n, _ in created_nodes]
        group_name = f"{args.episode}_组{'_'.join(str(g) for g in args.groups)}"

        node_args = []
        for n in node_names:
            node_args += ["--node", n]

        r = run_libtv(["group", "create", group_name] + node_args)
        if r:
            gk = r.get("groupNodeKey", "?")
            print(f"  ✅ 分组创建成功: {group_name}")
        else:
            print(f"  ⚠ 分组可能已存在，尝试创建不同名称")
            r2 = run_libtv(["group", "create", f"{group_name}_v2"] + node_args)
            if r2:
                print(f"  ✅ 以 {group_name}_v2 创建成功")
                group_name = f"{group_name}_v2"
            else:
                print(f"  ❌ 建组失败")

    # ========== 步骤5: [可选] 运行 ==========
    if args.run:
        if args.no_group:
            print("\n" + "=" * 60)
            print("⛔ 步骤5: 运行被跳过")
            print("=" * 60)
            print(f"  --no-group 模式未创建编组，无法通过 group --run 运行。")
            print(f"  如需运行，请去掉 --no-group 参数重新执行，或手动在画布中运行节点。")
            print("=" * 60)
        else:
            # 检查项目配置是否禁止运行
            project_config = _load_project_config(project_root)
            if project_config and project_config.get("suppress_run", False):
                print("\n" + "=" * 60)
                print("⛔ 步骤5: 运行被禁止")
                print("=" * 60)
                print(f"  项目配置 suppress_run=true，跳过视频生成运行。")
                print(f"  如需运行，请先修改 project_config.json 中 suppress_run 为 false。")
                print("=" * 60)
            else:
                print("\n" + "=" * 60)
                print("步骤5: 运行分组（libtv >= 1.1.1 阻塞等待完成）")
                print("=" * 60)
                # v1.1.1+: group --run 阻塞等待，stderr 每 ~3min 输出进度，stdout 输终态 JSON
                run_libtv(["group", group_name, "--run"])

        # ========== 步骤6: [可选] 下载视频 ==========
        if args.download and not args.no_group:
            print("\n" + "=" * 60)
            print("步骤6: 下载视频（group --run 已等待完成，直接查询结果）")
            print("=" * 60)

            output_dir = args.output_dir or os.path.join(project_root, args.episode, "视频")
            os.makedirs(output_dir, exist_ok=True)

            downloaded = []
            failed = 0

            for node_name, _ in created_nodes:
                print(f"\n  ── {node_name} ──")
                urls = poll_node(node_name, interval=args.poll_interval, timeout=args.poll_timeout)
                if not urls:
                    failed += 1
                    continue

                video_url = urls[0]
                ext = ".mp4"
                output_path = os.path.join(output_dir, f"{node_name}{ext}")

                ok = download_video(video_url, output_path)
                if ok:
                    downloaded.append({
                        "displayName": node_name,
                        "videoUrl": video_url,
                        "localPath": output_path,
                        "duration": None,
                    })
                    print(f"  ✅ {node_name} → {output_path}")
                else:
                    failed += 1

            manifest = {
                "status": "success" if failed == 0 else "partial",
                "episode": args.episode,
                "output_dir": output_dir,
                "nodes": downloaded,
                "totalGroups": len(created_nodes),
                "downloaded": len(downloaded),
                "failed": failed,
            }
            manifest_path = os.path.join(output_dir, "_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            print(f"\n  📋 Manifest: {manifest_path}")
            print(f"  ✅ 下载完成: {len(downloaded)}/{len(created_nodes)}")

    print("\n" + "=" * 60)
    if failed > 0:
        print(f"⚠️  完成（{failed} 个组失败）")
    else:
        print("🎉 全部完成！")
    if not args.run and group_name:
        print(f"运行命令: libtv group \"{group_name}\" --run")
    elif not args.run and args.no_group:
        print(f"节点已创建（未建组），如需运行请去掉 --no-group 重新执行")
    print("=" * 60)

    return failed


def main():
    parser = argparse.ArgumentParser(
        description="视频生成管线编排器 — 一站式完成上传->建节点->建组"
    )

    parser.add_argument("--build", action="store_true", help="完整流程")
    parser.add_argument("--process", action="store_true", help="仅处理已有节点")
    parser.add_argument("--project", default=None, help="项目名")
    parser.add_argument("--episode", default="EP01", help="剧集号")
    parser.add_argument("--canvas-uuid", default=None, help="画布 UUID（可选，不传时自动从 project_config.json 的 episodes 映射查找）")
    parser.add_argument("--groups", nargs="+", type=int, default=None, help="组号列表")
    parser.add_argument("--refs", action="append", default=None,
                        help='参考图映射（必填，由 agent 根据分组内容判断）格式: "组N:类型_名,类型_名"（如 "组1:角色_掌柜,场景_茶馆"）；选角参考图自动过滤')
    parser.add_argument("--voice-refs", nargs="*", default=None,
                        help='音色参考角色列表，如 吉小泰 妈妈 女儿；自动在 project/<项目>/全局依赖/音色参考/ 下查找对应WAV文件并上传连线')
    parser.add_argument("--run", action="store_true", help="执行后运行分组")
    parser.add_argument("--download", action="store_true", help="运行后轮询并下载视频到本地")
    parser.add_argument("--output-dir", default=None, help="视频下载目录（默认: project/<项目>/<剧集>/视频/）")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL, help="轮询间隔秒数（默认: 30）")
    parser.add_argument("--poll-timeout", type=int, default=POLL_TIMEOUT, help="轮询超时秒数（默认: 600）")
    parser.add_argument("--model", default=None, help='视频模型 modelName（中文名，如 "Seedance 2.0 VIP"）；libtv 1.1.1+ 直接使用该值，禁止传 modelKey')
    parser.add_argument("--ratio", default=None, help="画面比例")
    parser.add_argument("--resolution", default=None, help="分辨率")
    parser.add_argument("--sound", default=None, help="音频开关")
    parser.add_argument("--storyboard-mode", choices=["detailed", "simplified"], default=None,
                        help="分镜脚本模式，覆盖 project_config.json 中的 storyboard_mode。detailed=组{N}.json，simplified=组{N}.md")
    parser.add_argument("--no-group", action="store_true",
                        help="跳过建组步骤，仅创建独立节点不创建编组")

    args = parser.parse_args()

    if not args.build and not args.process:
        parser.print_help()
        sys.exit(1)

    if not args.groups:
        print("❌ 必须指定 --groups")
        sys.exit(1)

    if args.download and not args.run:
        print("❌ --download 必须搭配 --run 使用")
        sys.exit(1)

    failed = build_pipeline(args)
    if failed and failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
