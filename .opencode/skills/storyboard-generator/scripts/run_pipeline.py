#!/usr/bin/env python3
"""分镜管线编排器 — 校验 → 展开 → 输出独立组JSON

Agent 职责：
  1. 读剧本 + 读设定
  2. 用自身 LLM 生成分镜 JSON，写入 .pipeline/01_response.json
  3. 调用本脚本 `--build` 执行校验→展开→输出

本脚本自动处理：
  - 管线目录初始化
  - JSON 校验修复
  - 场→组展开 + 通用设定注入
  - 输出独立组 JSON 到最终目录

用法:
  python run_pipeline.py --build ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
# 步骤
# ============================================================

def setup_pipeline(pipeline_dir):
    """创建管线目录结构"""
    pd = Path(pipeline_dir).resolve()
    pd.mkdir(parents=True, exist_ok=True)
    print(f"  📁 管线目录就绪: {pd}")


def validate_and_expand(pipeline_dir, output_dir, output_groups="分组",
                        with_task_table=False,
                        task_table_model="gpt-image-2",
                        task_table_resolution="1K",
                        task_table_aspect_ratio="16:9"):
    """校验 → 展开 → 输出独立组 JSON [→ 可选: 生成任务表]"""
    pd = Path(pipeline_dir).resolve()
    validated = pd / "04_validated.json"
    response = pd / "01_response.json"

    # 1. 确定输入文件
    if validated.exists():
        input_file = validated
        print(f"  ℹ️ 输入: {input_file} (已有校验文件，跳过校验)")
    elif response.exists():
        input_file = response
        print(f"  ℹ️ 输入: {input_file} (单次响应文件)")
    elif (pd / "response.json").exists():
        input_file = pd / "response.json"
        print(f"  ℹ️ 输入: {input_file} (原始响应文件)")
    else:
        print("  ❌ 未找到分镜响应文件（01_response.json）", file=sys.stderr)
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

def build_pipeline(pipeline_dir, output_dir, output_groups,
                   with_task_table=False,
                   task_table_model="gpt-image-2",
                   task_table_resolution="1K",
                   task_table_aspect_ratio="16:9"):
    """完整管线：初始化 → 校验 → 展开 → [可选]生成任务表 → 输出

    Agent 需先自行生成分镜 JSON 并写入 .pipeline/01_response.json，
    本函数负责后续机械步骤。
    """

    # 0. 初始化管线目录
    setup_pipeline(pipeline_dir)

    # 1. 校验 → 展开 → [可选]生成任务表 → 输出
    mode_desc = "校验 → 展开 → 输出独立组 JSON"
    if with_task_table:
        mode_desc += " → 生成分镜图任务表"
    print(f"\n>>> 🔧 {mode_desc}")
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
  # [推荐] 配置文件模式
  python run_pipeline.py --build --config pipeline_config.json

  # 完整管线（Agent 需先写入 .pipeline/01_response.json）
  python run_pipeline.py --build ^
    --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"

  # 仅初始化管线目录
  python run_pipeline.py --setup --pipeline-dir "project/X/EP01/.pipeline"

  # 仅在 01_response.json 就位后执行校验→展开→输出
  python run_pipeline.py --process --pipeline-dir "project/X/EP01/.pipeline" ^
    --output-dir "project/X/EP01/分镜"
"""
    )

    # --- 模式选择 ---
    parser.add_argument("--build", action="store_true",
                        help="完整管线（初始化→校验→展开→输出）")
    parser.add_argument("--setup", action="store_true",
                        help="仅初始化管线目录")
    parser.add_argument("--process", action="store_true",
                        help="仅执行机械步骤（校验→展开→输出）")

    # --- 配置文件模式 ---
    parser.add_argument("--config", default=None,
                        help="JSON 配置文件路径")

    # --- 管线目录 ---
    parser.add_argument("--pipeline-dir", default=".pipeline",
                        help="管线目录路径")
    parser.add_argument("--output-dir", default="分镜",
                        help="分组 JSON 输出目录")
    parser.add_argument("--output-groups", default="分组",
                        help="最终分组文件夹名称（在 output-dir 下）")

    # --- 分镜图任务表 ---
    parser.add_argument("--with-task-table", action="store_true",
                        help="启用分镜图任务表生成")
    parser.add_argument("--task-table-model", default="gpt-image-2",
                        help="分镜图模型")
    parser.add_argument("--task-table-resolution", default="1K",
                        help="分镜图分辨率")
    parser.add_argument("--task-table-aspect-ratio", default="16:9",
                        help="分镜图画幅比例")

    args = parser.parse_args()

    # -----------------------------------------------------------
    # 配置文件模式
    # -----------------------------------------------------------
    if args.config:
        cfg = load_config(args.config)
        pipeline_dir = cfg.get("pipeline_dir", args.pipeline_dir)
        output_dir = cfg.get("output_dir", args.output_dir)
        output_groups = cfg.get("output_groups", args.output_groups)

        print(f"\n📋 配置文件模式: {args.config}")
        print(f"   管线目录: {pipeline_dir}")
        print(f"   输出目录: {output_dir}")

        ok = build_pipeline(
            pipeline_dir=pipeline_dir,
            output_dir=output_dir,
            output_groups=output_groups,
            with_task_table=cfg.get("with_task_table", args.with_task_table),
            task_table_model=cfg.get("task_table_model", args.task_table_model),
            task_table_resolution=cfg.get("task_table_resolution", args.task_table_resolution),
            task_table_aspect_ratio=cfg.get("task_table_aspect_ratio", args.task_table_aspect_ratio),
        )
        sys.exit(0 if ok else 1)

    # -----------------------------------------------------------
    # 一站式构建
    # -----------------------------------------------------------
    if args.build:
        ok = build_pipeline(
            pipeline_dir=args.pipeline_dir,
            output_dir=args.output_dir,
            output_groups=args.output_groups,
            with_task_table=args.with_task_table,
            task_table_model=args.task_table_model,
            task_table_resolution=args.task_table_resolution,
            task_table_aspect_ratio=args.task_table_aspect_ratio,
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
