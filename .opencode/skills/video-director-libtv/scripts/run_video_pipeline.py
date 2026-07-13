#!/usr/bin/env python3
"""视频生成管线编排器 — 一站式完整流程

依赖: libtv >= 1.1.1（group --run 现为阻塞等待命令，CLI 内部完成轮询）

用法:
  # 完整流程（上传素材 → 创建节点（一次性含引用行） → 建组）
  # 注意: --model 传 modelName（中文名），如 "Seedance 2.0 VIP"；不要传 modelKey
  python run_video_pipeline.py --build ^
    --project "项目名" --episode EP01 --canvas-uuid <UUID> ^
    --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 --resolution 480p ^
    --refs "组7:场景_现代南京长江边,角色_一岛,角色_郑和,道具_平板" ^
    --refs "组8:场景_现代南京长江边,角色_一岛,角色_郑和"

  # 完整流程 + 音色参考
  python run_video_pipeline.py --build ^
    --project "项目名" --episode EP01 --canvas-uuid <UUID> ^
    --groups 7 8 9 --model "Seedance 2.0 VIP" --ratio 16:9 ^
    --refs "组7:场景_现代南京,角色_一岛" ^
    --voice-refs 吉小泰 妈妈 女儿

  # 完整流程 + 运行（group --run 阻塞等待）
  python run_video_pipeline.py --build ... --run

  # 完整流程 + 运行 + 自动下载视频到 project/<项目>/<剧集>/视频/
  python run_video_pipeline.py --build ... --run --download
"""

import argparse
import json
import os
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


def scan_project_refs(project_root):
    import re
    found = {}
    for ref_type, rel_path in REFERENCE_TYPE_PATHS.items():
        dir_path = os.path.join(project_root, rel_path)
        if not os.path.isdir(dir_path):
            continue
        for f in sorted(os.listdir(dir_path)):
            if not f.lower().endswith(".png"):
                continue
            name_without_ext = os.path.splitext(f)[0]
            clean_name = re.sub(r"(_基准|_参考|_ref|-reference)$", "", name_without_ext, flags=re.IGNORECASE)
            if ref_type == "风格":
                clean_name = re.sub(r"^风格参考-", "", clean_name)
            node_name = f"{ref_type}_{clean_name}"
            found[node_name] = os.path.join(dir_path, f)
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


def upload_references(project_root, canvas_cache):
    ref_nodes = {}
    all_files = scan_project_refs(project_root)

    print("\n" + "=" * 60)
    print("上传参考图到画布（复用检测）")
    print("=" * 60)

    for node_name, file_path in all_files.items():
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


def upload_voice_refs(project_root, role_names):
    """上传音色参考（WAV）到画布，返回上传成功的节点名列表。"""
    voice_ref_dir = os.path.join(project_root, "全局依赖", "音色参考")
    voice_nodes = []

    print("\n" + "=" * 60)
    print("上传音色参考到画布")
    print("=" * 60)

    if not os.path.isdir(voice_ref_dir):
        print(f"  ⚠ 音色参考目录不存在: {voice_ref_dir}")
        return voice_nodes

    for role_name in role_names:
        role_name = role_name.strip()
        if not role_name:
            continue

        wav_path = os.path.join(voice_ref_dir, f"{role_name}-音色参考.wav")
        if not os.path.exists(wav_path):
            print(f"  ⚠ 未找到 {role_name} 的音色参考文件: {wav_path}")
            continue

        node_name = f"音色_{role_name}"
        rel = os.path.relpath(wav_path, project_root)
        print(f"  {rel} → {node_name}...", end=" ")
        result = run_libtv(["upload", node_name, "-t", "audio", "-f", wav_path])
        if result:
            voice_nodes.append(node_name)
            print("✅")
        else:
            print("❌")

    print(f"  音色参考就绪: {len(voice_nodes)} 个")
    return voice_nodes


def build_ref_description(ref_name, idx):
    """根据参考图名称生成 Image N 描述。
    --left 顺序决定 {{Image N}} 编号，第一个 --left 为 {{Image 1}}"""
    if "场景" in ref_name:
        return f"场景氛围参考{{{{Image {idx}}}}}"
    elif "角色" in ref_name:
        char_name = ref_name.replace("角色_", "").replace("_基准", "")
        return f"角色形象参考（{char_name}）{{{{Image {idx}}}}}"
    elif "道具" in ref_name:
        prop_name = ref_name.replace("道具_", "").replace("_基准", "")
        return f"道具样式参考（{prop_name}）{{{{Image {idx}}}}}"
    elif "分镜" in ref_name:
        return f"分镜构图参考{{{{Image {idx}}}}}"
    elif "风格" in ref_name:
        return f"视觉风格参考{{{{Image {idx}}}}}"
    else:
        return f"参考图{{{{Image {idx}}}}}"


def build_prompt(group_json, ref_names, voice_ref_names=None, ref_prefix="请参考", ref_suffix="进行画面生成", audio_connector="，"):
    """构建完整 prompt：引用行 + 约束行 + 分隔线 + JSON。
    引用行中的 {{Image N}} 编号与 --left 顺序一致。
    含音色参考时在 prompt 末尾追加 {{Audio N}} 引用。
    可通过 ref_prefix/ref_suffix/audio_connector 自定义引用措辞。"""
    raw_json = json.dumps(group_json, ensure_ascii=False)
    if ref_names:
        ref_parts = [build_ref_description(n, i+1) for i, n in enumerate(ref_names)]
        ref_line = ref_prefix + "、".join(ref_parts) + ref_suffix
        if voice_ref_names:
            # voice_ref_names 是节点名列表，如 ["音色_吉小泰", "音色_妈妈"]
            # 从节点名中提取角色名（去掉 "音色_" 前缀）
            audio_parts = []
            for i, vn in enumerate(voice_ref_names):
                role = vn.replace("音色_", "", 1) if vn.startswith("音色_") else vn
                audio_parts.append(f"{role}角色音色请参考{{{{Audio {i+1}}}}}")
            ref_line += audio_connector + "、".join(audio_parts)
        return f"{ref_line}\n\n{CONSTRAINT}\n{SEPARATOR}\n{raw_json}"
    if voice_ref_names:
        # voice_ref_names 是节点名列表，如 ["音色_吉小泰", "音色_妈妈"]
        # 从节点名中提取角色名（去掉 "音色_" 前缀）
        audio_parts = []
        for i, vn in enumerate(voice_ref_names):
            role = vn.replace("音色_", "", 1) if vn.startswith("音色_") else vn
            audio_parts.append(f"{role}角色音色请参考{{{{Audio {i+1}}}}}")
        ref_line = ref_prefix + "、".join(audio_parts) + ref_suffix
        return f"{ref_line}\n\n{CONSTRAINT}\n{SEPARATOR}\n{raw_json}"
    return f"{CONSTRAINT}\n{SEPARATOR}\n{raw_json}"


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


def build_pipeline(args):
    project_root = os.path.join(os.getcwd(), "project", args.project)
    groups_dir = os.path.join(project_root, args.episode, "分镜", "分组")
    canvas_uuid = args.canvas_uuid

    if not os.path.isdir(groups_dir):
        print(f"❌ 分组目录不存在: {groups_dir}")
        sys.exit(1)

    if not args.canvas_uuid:
        print("❌ 必须提供 --canvas-uuid")
        sys.exit(1)

    custom_refs = parse_refs(args.refs) if args.refs else {}

    # ========== 步骤1: 绑定画布 ==========
    print("\n" + "=" * 60)
    print(f"步骤1: 绑定画布 {canvas_uuid}")
    print("=" * 60)
    r = run_libtv(["project", "use", canvas_uuid])
    if not r:
        print("❌ 绑定失败")
        sys.exit(1)
    print(f"  ✅ 已绑定 {canvas_uuid}")

    # ========== 步骤2: 建立画布缓存 + 上传参考图 ==========
    canvas_cache = build_canvas_cache(canvas_uuid)
    ref_nodes = upload_references(project_root, canvas_cache)

    # ========== 步骤2.5: [可选] 上传音色参考 ==========
    voice_ref_nodes = []
    if args.voice_refs:
        voice_ref_nodes = upload_voice_refs(project_root, args.voice_refs)

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
        group_path = os.path.join(groups_dir, f"{group_name}.json")

        if not os.path.exists(group_path):
            print(f"  ⚠ {group_name}.json 不存在，跳过")
            continue

        with open(group_path, "r", encoding="utf-8") as f:
            group = json.load(f)

        duration = calc_duration(group)

        # 确定该组要连线的参考图
        refs_for_group = custom_refs.get(group_name, custom_refs.get(str(gid), []))
        available_refs = []
        for r in refs_for_group:
            available_refs.extend(match_ref_name(r, ref_nodes))
        available_refs = list(dict.fromkeys(available_refs))

        # --left 顺序决定 {{Image N}} 和 {{Audio N}} 编号
        prompt = build_prompt(group, available_refs, voice_ref_nodes)

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
        for ref_name in available_refs:
            cmd += ["--left", ref_name]
        for vn in voice_ref_nodes:
            cmd += ["--left", vn]

        all_left = list(available_refs) + list(voice_ref_nodes)
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

    # ========== 步骤4: 建组 ==========
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
        else:
            print(f"  ❌ 建组失败")

    # ========== 步骤5: [可选] 运行 ==========
    if args.run:
        print("\n" + "=" * 60)
        print("步骤5: 运行分组（libtv >= 1.1.1 阻塞等待完成）")
        print("=" * 60)
        # v1.1.1+: group --run 阻塞等待，stderr 每 ~3min 输出进度，stdout 输终态 JSON
        run_libtv(["group", group_name, "--run"])

        # ========== 步骤6: [可选] 下载视频 ==========
        if args.download:
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
    print("🎉 全部完成！")
    if not args.run:
        print(f"运行命令: libtv group \"{group_name}\" --run")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="视频生成管线编排器 — 一站式完成上传->建节点->建组"
    )

    parser.add_argument("--build", action="store_true", help="完整流程")
    parser.add_argument("--process", action="store_true", help="仅处理已有节点")
    parser.add_argument("--project", default=None, help="项目名")
    parser.add_argument("--episode", default="EP01", help="剧集号")
    parser.add_argument("--canvas-uuid", default=None, help="画布项目 UUID")
    parser.add_argument("--groups", nargs="+", type=int, default=None, help="组号列表")
    parser.add_argument("--refs", action="append", default=None,
                        help='参考图映射 格式: "组N:类型_名,类型_名"')
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

    build_pipeline(args)


if __name__ == "__main__":
    main()
