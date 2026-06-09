#!/usr/bin/env python3
"""
分片管理器 — 分镜脚本的分片拆分、请求生成与结果合并。

三种模式:
  --split              : 分析剧本，按叙事节拍拆分为多个分片，输出分片方案
  --generate-requests  : 根据分片方案 + shared system prompt，写出每个分片的 request.json
  --merge              : 合并多个分片 response.json 为统一分镜 JSON，重编号

每个分片放在 pipeline-dir/{序号_shard_{id}/ 子目录下，含 request.json + response.json。
"""

import json, os, re, sys
from pathlib import Path

SCENE_BREAK_PATTERNS = [
    r'^---+\s*$',
    r'^##\s+.+场景',
    r'^###?\s+.+',
    r'^【.+】\s*$',
    r'^第.+幕[：:]\s*$',
]
TARGET_GROUPS_PER_SHARD = 4
MAX_GROUPS_PER_SHARD = 6


def detect_scene_breaks(script_text: str) -> list[int]:
    breaks = [0]
    lines = script_text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        for pattern in SCENE_BREAK_PATTERNS:
            if re.match(pattern, stripped):
                if i > breaks[-1]:
                    breaks.append(i)
                break
    return breaks


def estimate_groups(text: str) -> int:
    char_count = len(text)
    return max(1, round(char_count / 400))


def split_script(script_text: str, target_groups: int = TARGET_GROUPS_PER_SHARD) -> list[dict]:
    scene_breaks = detect_scene_breaks(script_text)
    lines = script_text.split('\n')
    scenes = []
    for i, break_line in enumerate(scene_breaks):
        end_line = scene_breaks[i + 1] if i + 1 < len(scene_breaks) else len(lines)
        segment = '\n'.join(lines[break_line:end_line]).strip()
        if segment:
            scenes.append({
                "start_line": break_line,
                "end_line": end_line,
                "text": segment,
                "char_count": len(segment),
            })
    shards = []
    current = {"chunks": [], "text": "", "char_count": 0}
    for scene in scenes:
        scene_est = estimate_groups(scene["text"])
        current_est = estimate_groups(current["text"])
        if current["chunks"] and (current_est >= target_groups or current_est + scene_est > MAX_GROUPS_PER_SHARD):
            shards.append(current)
            current = {"chunks": [], "text": "", "char_count": 0}
        current["chunks"].append(scene)
        current["text"] += ("\n\n" + scene["text"]) if current["text"] else scene["text"]
        current["char_count"] += scene["char_count"]
    if current["text"]:
        shards.append(current)
    return shards


def extract_from_response(response_path: str) -> list:
    with open(response_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    content = raw.get("content", raw) if isinstance(raw, dict) else raw
    if isinstance(content, dict):
        content = content.get("content", json.dumps(content))
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    text = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n```\s*$', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    text = re.sub(r',\s*(\}|\])', r'\1', text)
    text = text.strip()
    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return []


def merge_shards(response_files: list[str], output_path: str) -> dict:
    all_groups = []
    group_offset = 0
    shot_offset = 0
    merge_log = []
    for response_file in response_files:
        groups = extract_from_response(response_file)
        original_count = len(groups)
        for group in groups:
            group_offset += 1
            group["组号"] = group_offset
            shots = group.get("镜头列表", [])
            for shot in shots:
                shot_offset += 1
                shot["镜号"] = shot_offset
            all_groups.append(group)
        merge_log.append(f"  {Path(response_file).name}: {original_count} 组 → 组{group_offset - original_count + 1}-{group_offset}")
    result = all_groups
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 合并完成 → {output_path}")
    print(f"   总 {len(all_groups)} 个镜头组，来自 {len(response_files)} 个分片")
    for line in merge_log:
        print(line)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="分片管理器 — 拆分、生成请求与合并")
    parser.add_argument("--split", metavar="script.md", help="分析剧本，输出分片方案")
    parser.add_argument("--generate-requests", action="store_true", help="根据分片方案生成各分片的 request.json")
    parser.add_argument("--system", help="--generate-requests 时使用的共享 System Prompt")
    parser.add_argument("--merge", metavar="pipeline_dir", help="合并分片响应文件目录")
    parser.add_argument("--output", "-o", metavar="output.json", help="输出路径")
    parser.add_argument("--target-groups", type=int, default=TARGET_GROUPS_PER_SHARD, help="每分片目标组数")
    parser.add_argument("--pipeline-dir", help="pipeline 基准目录")
    args = parser.parse_args()

    # pipeline-dir 拼接：output 相对于 pipeline-dir，而非绝对路径拼接
    if args.pipeline_dir:
        pd = Path(args.pipeline_dir)
        if args.split:
            if args.output:
                out_path = pd / args.output if not Path(args.output).is_absolute() else Path(args.output)
            else:
                out_path = pd / "02_shard_plan.json"
        else:
            out_path = None

    # ─── --split 模式 ──────────────────────────────────
    if args.split:
        with open(args.split, "r", encoding="utf-8") as f:
            text = f.read()
        shards = split_script(text, args.target_groups)
        plan = {
            "shard_count": len(shards),
            "target_groups_per_shard": args.target_groups,
            "shards": []
        }
        for i, shard in enumerate(shards):
            est = estimate_groups(shard["text"])
            plan["shards"].append({
                "shard_id": i + 1,
                "char_count": shard["char_count"],
                "estimated_groups": est,
                "chunk_count": len(shard["chunks"]),
            })
        out_path = out_path or Path(args.output or "shard_plan.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"✅ 分片方案 → {out_path}")
        for s in plan["shards"]:
            print(f"   分片{s['shard_id']}: ~{s['estimated_groups']}组, {s['char_count']}字符")

        # 如果同时有 --generate-requests，生成 request.json
        if args.generate_requests:
            if not args.system:
                parser.error("--generate-requests 需要 --system 参数 (共享 System Prompt)")
            for shard_info in plan["shards"]:
                sid = shard_info["shard_id"]
                shard_text = shards[sid - 1]["text"]
                shard_dir = Path(out_path).parent / f"{sid:02d}_shard_{sid}"
                shard_dir.mkdir(parents=True, exist_ok=True)
                req_path = shard_dir / "request.json"
                messages = []
                messages.append({"role": "system", "content": args.system})
                messages.append({
                    "role": "user",
                    "content": f"以下是你需要处理的剧本片段（共 {plan['shard_count']} 个分片中的第 {sid} 个）：\n\n{shard_text}"
                })
                with open(req_path, "w", encoding="utf-8") as f:
                    json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)
                print(f"  → {req_path}")
        return

    # ─── --merge 模式 ──────────────────────────────────
    if args.merge:
        merge_dir = Path(args.merge)
        if not merge_dir.is_dir():
            print(f"❌ 目录不存在: {args.merge}", file=sys.stderr)
            sys.exit(1)
        response_files = sorted(merge_dir.rglob("response.json"))
        if not response_files:
            print(f"❌ 未找到 response.json 文件", file=sys.stderr)
            sys.exit(1)
        out = args.output or str(merge_dir / "03_merged.json")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        merge_shards([str(p) for p in response_files], out)
        return

    parser.print_help()


if __name__ == "__main__":
    main()