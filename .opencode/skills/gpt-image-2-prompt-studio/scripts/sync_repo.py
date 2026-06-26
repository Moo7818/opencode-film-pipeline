"""
sync_repo.py — 管理 awesome-gpt-image-2-API-and-Prompts 仓库

用法：
  python sync_repo.py                    # 克隆（首次）
  python sync_repo.py --update           # 更新到最新
  python sync_repo.py --status           # 查看仓库状态
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

# 确保 UTF-8 输出（Windows GBK 兼容）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

REPO_URL = "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts.git"
DEFAULT_TARGET = Path(__file__).resolve().parents[3] / "temp" / "awesome-gpt-image-2-API-and-Prompts"


def get_repo_path() -> Path:
    env_path = os.environ.get("REPO_PATH")
    return Path(env_path).resolve() if env_path else DEFAULT_TARGET


def run_git(cmd: list[str], cwd: Path = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def cmd_clone(target: Path):
    if target.exists():
        print(f"[ERR] 目标路径已存在: {target}")
        print("   使用 --update 更新，或删除后重新克隆")
        sys.exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[..] 克隆 {REPO_URL} -> {target} ...")
    result = run_git(["clone", REPO_URL, str(target)])
    if result.returncode != 0:
        print(f"[ERR] 克隆失败:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("[OK] 克隆完成")
    cmd_status(target)


def cmd_update(target: Path):
    if not target.exists():
        print(f"[ERR] 仓库不存在: {target}")
        print("   请先运行 sync_repo.py（不带 --update）")
        sys.exit(1)
    print(f"[..] 更新仓库 {target} ...")
    result = run_git(["pull", "--ff-only"], cwd=target)
    if result.returncode != 0:
        print(f"[ERR] 更新失败:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("[OK] 已更新到最新")
    cmd_status(target)


def cmd_status(target: Path):
    if not target.exists():
        print(f"[ERR] 仓库不存在: {target}")
        return
    result = run_git(["log", "--oneline", "-3"], cwd=target)
    print(f"[INFO] 仓库: {target}")
    print(f"最近提交:")
    print(result.stdout)
    result2 = run_git(["rev-parse", "--short", "HEAD"], cwd=target)
    sha = result2.stdout.strip()
    print(f"SHA: {sha}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="管理 GPT Image 2 提示词仓库")
    parser.add_argument("--update", action="store_true", help="更新到最新")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--target", type=str, default=None, help="仓库路径（覆盖默认）")
    args = parser.parse_args()

    target = Path(args.target).resolve() if args.target else get_repo_path()

    if args.status:
        cmd_status(target)
    elif args.update:
        cmd_update(target)
    elif not target.exists():
        cmd_clone(target)
    else:
        cmd_status(target)


if __name__ == "__main__":
    main()
