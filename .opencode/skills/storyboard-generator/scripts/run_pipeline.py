#!/usr/bin/env python3
"""分镜管线编排器 — 一站式完整管线（LLM请求→校验→展开→输出独立组JSON）

Agent 的职责**只有**：
  1. 读剧本 + 读设定 → 构建 System Prompt
  2. 判断短/长剧本（>2000字为长剧本）
  3. 调用本脚本 `--build`，传入 Prompt 即可

本脚本自动处理：
  - 管线目录初始化
  - LLM 请求构建 + 调用（短剧本单次 / 长剧本自动分片并发+合并）
  - JSON 校验修复
  - 场→组展开 + 通用设定注入
  - 输出独立组 JSON 到最终目录

LLM 调用委托给 MCP server 的 grsai_client.call_llm（统一凭证源）。

用法:
  # 短剧本（≤2000字）
  python run_pipeline.py --build ^
    --system "(System Prompt 全文)" ^
    --user "(User Message 全文)" ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"

  # 长剧本（>2000字）
  python run_pipeline.py --build ^
    --system "(共享 System Prompt 全文)" ^
    --user "(User Message 全文)" ^
    --shard --script-path "project/X/EP01/剧本.md" ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"
"""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 引入 MCP server 的 grsai_client 模块（统一凭证源和 HTTP 调用逻辑）
MCP_SERVER_DIR = Path(__file__).resolve().parents[3] / "mcp-servers" / "grsai-server"
sys.path.insert(0, str(MCP_SERVER_DIR))
from grsai_client import call_llm as _mcp_call_llm


SKILL_DIR = Path(__file__).resolve().parent


# ============================================================
# 工具
# ============================================================

def _run(step_name, args, capture=True):
    """执行单个子进程步骤，返回 (success, stdout)"""
    cmd = [sys.executable] + args
    print(f"\n{'='*60}")
    print(f"  [{step_name}] {' '.join(args)}")
    print(f"{'='*60}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, capture_output=capture, text=False, env=env)
    out = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    err = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    if result.returncode != 0:
        print(f"\n  ❌ {step_name} 失败 (exit code {result.returncode})", file=sys.stderr)
        return False, out or err
    print(f"  ✅ {step_name} 完成")
    return True, out or err


# ============================================================
# LLM 调用（进程内，直接委托给 MCP server 的 grsai_client）
# ============================================================

def _write_request(system_prompt, user_content, output_path):
    """构建并写出 request.json"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)
    print(f"  \u2714 {output_path}")


def _call_and_write(req_path, model=None, temperature=0.7):
    """读取 request.json → 调用 MCP server LLM → 写出同目录 response.json"""
    req_data = json.loads(Path(req_path).read_text(encoding="utf-8"))
    messages = req_data.get("messages", req_data)
    result = _mcp_call_llm(messages, model, temperature)
    resp_path = Path(req_path).parent / "response.json"
    resp_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


# ============================================================
# 步骤
# ============================================================

def setup_pipeline(pipeline_dir):
    """创建管线目录结构"""
    pd = Path(pipeline_dir).resolve()
    pd.mkdir(parents=True, exist_ok=True)
    print(f"  📁 管线目录就绪: {pd}")


def build_and_call_llm(pipeline_dir, system_prompt, user_message, model=None, temperature=0.7):
    """Step A：构建请求 → 调用 LLM（短剧本单次，进程内）"""
    pd = Path(pipeline_dir).resolve()
    req_path = pd / "01_request.json"

    _write_request(system_prompt, user_message, str(req_path))
    result = _call_and_write(req_path, model, temperature)
    print(f"  ✅ LLM 调用完成: {result.get('finish_reason', '?')} | tokens: {result.get('usage', {}).get('total_tokens', '?')}")
    return True


def shard_and_call_llm(pipeline_dir, system_prompt, script_path, model=None, temperature=0.7):
    """Step B：分片 → 并发调用 LLM（进程内） → 合并"""
    pd = Path(pipeline_dir).resolve()

    # 分片 + 生成请求文件（子进程调用 shard_manager.py）
    ok, _ = _run("分片分析", [
        str(SKILL_DIR / "shard_manager.py"),
        "--split", script_path,
        "--generate-requests",
        "--system", system_prompt,
        "--pipeline-dir", str(pd),
    ])
    if not ok:
        return False

    # 并发调用 LLM（进程内，无需子进程）
    request_files = sorted(pd.rglob("request.json"))
    if not request_files:
        print("  ❌ 未找到 request.json 分片文件", file=sys.stderr)
        return False

    print(f"  并发处理 {len(request_files)} 个分片...")
    with ThreadPoolExecutor(max_workers=min(len(request_files), 5)) as pool:
        futures = [pool.submit(_call_and_write, p, model, temperature) for p in request_files]
        for future in as_completed(futures):
            result = future.result()
            print(f"  ✅ 分片完成: {result.get('finish_reason', '?')} | {result.get('usage', {}).get('total_tokens', '?')} tokens")

    print(f"  ✅ 并发调用完成，响应文件已写入 {pd}")
    # 合并分片（子进程调用 shard_manager.py）
    ok, _ = _run("合并分片结果", [
        str(SKILL_DIR / "shard_manager.py"),
        "--merge", str(pd),
        "--pipeline-dir", str(pd),
    ])
    return ok


def validate_and_expand(pipeline_dir, output_dir, output_groups="分组",
                        with_task_table=False,
                        task_table_model="gpt-image-2",
                        task_table_resolution="1K",
                        task_table_aspect_ratio="16:9"):
    """校验 → 展开 → 输出独立组 JSON [→ 可选: 生成任务表]"""
    pd = Path(pipeline_dir).resolve()
    validated = pd / "04_validated.json"
    merged = pd / "03_merged.json"
    response = pd / "01_response.json"

    # 1. 确定输入文件
    if validated.exists():
        input_file = validated
        print(f"  ℹ️ 输入: {input_file} (已有校验文件，跳过校验)")
    elif merged.exists():
        input_file = merged
        print(f"  ℹ️ 输入: {input_file} (分片合并文件)")
    elif response.exists():
        input_file = response
        print(f"  ℹ️ 输入: {input_file} (单次响应文件)")
    elif (pd / "response.json").exists():
        input_file = pd / "response.json"
        print(f"  ℹ️ 输入: {input_file} (原始响应文件)")
    else:
        print("  ❌ 未找到 LLM 响应文件（03_merged.json / 01_response.json / response.json）", file=sys.stderr)
        return False

    # 2. 校验（仅在需要时执行）
    if input_file != validated:
        ok, _ = _run("校验修复", [
            str(SKILL_DIR / "validators.py"),
            "--repair", str(input_file),
            "--output", str(validated),
            "--check",
        ])
        if not ok:
            print("  ⚠️ 校验失败，请检查 LLM 输出后重试", file=sys.stderr)
            return False
    else:
        print("  [校验] 跳过（04_validated.json 已存在）")

    # 3. 展开场→独立组
    groups_dir = pd / "05_groups"
    ok, _ = _run("展开场→组", [
        str(SKILL_DIR / "expand_scenes_to_groups.py"),
        "--input", str(validated),
        "--output-dir", str(groups_dir),
    ])
    if not ok:
        return False

    # 4. [可选] 生成任务表（仅 --with-task-table 时执行）
    if with_task_table:
        ok, _ = _run("生成任务表", [
            str(SKILL_DIR / "generate_task_table.py"),
            "--groups-dir", str(groups_dir),
            "--output-dir", str(output_dir),
            "--model", task_table_model,
            "--image-size", task_table_resolution,
            "--aspect-ratio", task_table_aspect_ratio,
        ])
        if not ok:
            return False

    # 5. 输出独立组 JSON 到最终产物目录
    output_path = Path(output_dir).resolve()
    groups_output_dir = output_path / output_groups
    groups_output_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(groups_dir.glob("组*.json")):
        shutil.copy2(str(f), str(groups_output_dir / f.name))
        copied += 1

    print(f"\n{'='*60}")
    print(f"  🎉 管线完成！")
    print(f"    校验文件:       {validated}")
    print(f"    中间组目录:     {groups_dir}/ ({copied} 个组文件)")
    print(f"    最终分组文件:   {groups_output_dir}/ ({copied} 个组文件)")
    if with_task_table:
        print(f"    分镜图任务表:   {output_path}/分镜图_任务表.json")
    print(f"{'='*60}")
    return True


# ============================================================
# 一站式构建入口
# ============================================================

def build_pipeline(pipeline_dir, system_prompt, user_message,
                   output_dir, output_groups,
                   shard=False, script_path=None,
                   with_task_table=False,
                   task_table_model="gpt-image-2",
                   task_table_resolution="1K",
                   task_table_aspect_ratio="16:9",
                   llm_model=None, llm_temperature=0.7):
    """完整管线：初始化 → LLM 调用 → 校验 → 展开 → [可选]生成任务表 → 输出"""

    # 0. 初始化管线目录
    setup_pipeline(pipeline_dir)

    # 1. LLM 调用（进程内，直接委托给 MCP server 的 grsai_client）
    if shard:
        if not script_path:
            print("  ❌ 长剧本模式必须提供 --script-path", file=sys.stderr)
            return False
        print("\n>>> 📄 长剧本模式：分片 → 并发 → 合并")
        ok = shard_and_call_llm(pipeline_dir, system_prompt, script_path, llm_model, llm_temperature)
    else:
        print("\n>>> 📄 短剧本模式：单次请求")
        ok = build_and_call_llm(pipeline_dir, system_prompt, user_message, llm_model, llm_temperature)

    if not ok:
        print("  ❌ LLM 调用失败，管线终止", file=sys.stderr)
        return False

    # 2. 校验 → 展开 → [可选]生成任务表 → 输出
    mode_desc = "校验 → 展开 → 输出独立组 JSON"
    if with_task_table:
        mode_desc += " → 生成分镜图任务表"
    print(f"\n>>> 🔧 机械步骤：{mode_desc}")
    return validate_and_expand(
        pipeline_dir, output_dir, output_groups,
        with_task_table=with_task_table,
        task_table_model=task_table_model,
        task_table_resolution=task_table_resolution,
        task_table_aspect_ratio=task_table_aspect_ratio,
    )


# ============================================================
# CLI
# ============================================================

def load_config(config_path):
    """从 JSON 配置文件加载参数"""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="分镜管线编排器 — 一站式完整管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # [推荐] 配置文件模式（避免 PowerShell 引号问题）
  python run_pipeline.py --build --config pipeline_config.json

  # 短剧本：直接传参
  python run_pipeline.py --build ^
    --system "你是分镜导演..." --user "请为以下剧本生成..." ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"

  # 短剧本：文件传参（推荐，避免引号问题）
  python run_pipeline.py --build ^
    --system-file system_prompt.txt --user-file user_message.txt ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"

  # 长剧本：分片并发
  python run_pipeline.py --build ^
    --system "你是分镜导演..." --user "请为以下剧本生成..." ^
    --shard --script-path "project/X/EP01/剧本.md" ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"

  # 仅初始化管线目录
  python run_pipeline.py --setup --pipeline-dir "project/X/EP01/.pipeline"

  # 仅在 LLM 响应就位后执行机械步骤（校验->展开->输出）
  python run_pipeline.py --process --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"
"""
    )

    # --- 模式选择 ---
    parser.add_argument("--build", action="store_true",
                        help="一站式完整管线（LLM->校验->展开->输出）")
    parser.add_argument("--setup", action="store_true",
                        help="仅初始化管线目录")
    parser.add_argument("--process", action="store_true",
                        help="仅执行机械步骤（校验->展开->输出）")

    # --- 配置文件模式 ---
    parser.add_argument("--config", default=None,
                        help="JSON 配置文件路径（含所有参数，推荐模式）")

    # --- 管线目录 ---
    parser.add_argument("--pipeline-dir", default=".pipeline",
                        help="管线目录路径")
    parser.add_argument("--output-dir", default="分镜",
                        help="分组 JSON 输出目录")
    parser.add_argument("--output-groups", default="分组",
                        help="最终分组文件夹名称（在 output-dir 下）")

    # --- Prompt 输入 ---
    parser.add_argument("--system", default=None,
                        help="System Prompt 文本")
    parser.add_argument("--system-file", default=None,
                        help="System Prompt 文件路径")
    parser.add_argument("--user", default=None,
                        help="User Message 文本")
    parser.add_argument("--user-file", default=None,
                        help="User Message 文件路径")

    # --- 分片模式 ---
    parser.add_argument("--shard", action="store_true",
                        help="启用长剧本分片模式（配合 --build）")
    parser.add_argument("--script-path", default=None,
                        help="剧本文件路径（长剧本分片模式必填）")

    # --- 分镜图任务表 ---
    parser.add_argument("--with-task-table", action="store_true",
                        help="启用分镜图任务表生成")
    parser.add_argument("--task-table-model", default="gpt-image-2",
                        help="分镜图模型")
    parser.add_argument("--task-table-resolution", default="1K",
                        help="分镜图分辨率")
    parser.add_argument("--task-table-aspect-ratio", default="16:9",
                        help="分镜图画幅比例")

    # --- LLM 参数 ---
    parser.add_argument("--llm-model", default=None,
                        help="LLM 模型名（默认由 credentials.json 决定）")
    parser.add_argument("--llm-temperature", type=float, default=0.7,
                        help="LLM 温度（默认 0.7）")

    args = parser.parse_args()

    # -----------------------------------------------------------
    # 配置文件模式
    # -----------------------------------------------------------
    if args.config:
        cfg = load_config(args.config)
        pipeline_dir = cfg.get("pipeline_dir", args.pipeline_dir)
        output_dir = cfg.get("output_dir", args.output_dir)
        output_groups = cfg.get("output_groups", args.output_groups)
        system_prompt = cfg.get("system", "")
        user_message = cfg.get("user", "")
        shard = cfg.get("shard", False)
        script_path = cfg.get("script_path", None)

        if not system_prompt and cfg.get("system_file"):
            with open(cfg["system_file"], "r", encoding="utf-8") as f:
                system_prompt = f.read()
        if not user_message and cfg.get("user_file"):
            with open(cfg["user_file"], "r", encoding="utf-8") as f:
                user_message = f.read()

        if not system_prompt:
            print("❌ 配置文件中未提供 system 或 system_file", file=sys.stderr)
            sys.exit(1)

        print(f"\n📋 配置文件模式: {args.config}")
        print(f"   管线目录: {pipeline_dir}")
        print(f"   输出目录: {output_dir}")
        print(f"   分片模式: {'是' if shard else '否'}")
        if shard and script_path:
            print(f"   剧本文件: {script_path}")

        ok = build_pipeline(
            pipeline_dir=pipeline_dir,
            system_prompt=system_prompt,
            user_message=user_message,
            output_dir=output_dir,
            output_groups=output_groups,
            shard=shard,
            script_path=script_path,
            with_task_table=cfg.get("with_task_table", args.with_task_table),
            task_table_model=cfg.get("task_table_model", args.task_table_model),
            task_table_resolution=cfg.get("task_table_resolution", args.task_table_resolution),
            task_table_aspect_ratio=cfg.get("task_table_aspect_ratio", args.task_table_aspect_ratio),
            llm_model=cfg.get("llm_model", args.llm_model),
            llm_temperature=cfg.get("llm_temperature", args.llm_temperature),
        )
        sys.exit(0 if ok else 1)

    # -----------------------------------------------------------
    # 文件传参模式
    # -----------------------------------------------------------
    system_prompt = args.system
    user_message = args.user or ""

    if args.system_file:
        with open(args.system_file, "r", encoding="utf-8") as f:
            system_prompt = f.read()

    if args.user_file:
        with open(args.user_file, "r", encoding="utf-8") as f:
            user_message = f.read()

    # -----------------------------------------------------------
    # 一站式构建
    # -----------------------------------------------------------
    if args.build:
        if not system_prompt:
            print("❌ --build 模式必须提供 --system 或 --system-file", file=sys.stderr)
            sys.exit(1)
        if not args.shard and not user_message:
            print("❌ 短剧本 --build 模式必须提供 --user 或 --user-file", file=sys.stderr)
            sys.exit(1)
        ok = build_pipeline(
            pipeline_dir=args.pipeline_dir,
            system_prompt=system_prompt,
            user_message=user_message,
            output_dir=args.output_dir,
            output_groups=args.output_groups,
            shard=args.shard,
            script_path=args.script_path,
            with_task_table=args.with_task_table,
            task_table_model=args.task_table_model,
            task_table_resolution=args.task_table_resolution,
            task_table_aspect_ratio=args.task_table_aspect_ratio,
            llm_model=args.llm_model,
            llm_temperature=args.llm_temperature,
        )
        if not ok:
            sys.exit(1)
        return

    # -----------------------------------------------------------
    # 传统模式
    # -----------------------------------------------------------
    if args.setup:
        setup_pipeline(args.pipeline_dir)

    if args.process:
        ok = validate_and_expand(
            args.pipeline_dir, args.output_dir, args.output_groups,
            with_task_table=args.with_task_table,
            task_table_model=args.task_table_model,
            task_table_resolution=args.task_table_resolution,
            task_table_aspect_ratio=args.task_table_aspect_ratio,
        )
        if not ok:
            sys.exit(1)

    if not args.setup and not args.process and not args.build:
        parser.print_help()


if __name__ == "__main__":
    import argparse
    main()
