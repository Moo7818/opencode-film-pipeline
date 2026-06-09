#!/usr/bin/env python3
"""GRSAI 图像生成 CLI — 主入口

通过 JSON 任务列表批量生成图像，具备并发提交、队列调度、自动轮询和本地下载能力。
支持云存储持久化与本地参考图自动上传 COS。

模块结构：
  - config.py       配置加载（环境变量 > 配置文件）
  - cos_uploader.py  腾讯云 COS 上传
  - file_cache.py    文件映射缓存（SHA256 去重）
  - log_manager.py   日志索引与全量文档管理
  - api_client.py    GRSAI API 调用封装

接口：
  - 图像生成 →  POST /v1/api/generate  (replyType=async)
    - gpt-image-*: aspectRatio 使用像素格式（如 "1024x1024"）
    - nano-banana-*: aspectRatio 使用比例格式（如 "1:1"），额外传 imageSize
  - 结果查询 →  GET  /v1/api/result?id=xxx

凭证加载优先级：环境变量 > ~/.trae-cn/media_gen_config.json
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    _cfg, get_api_key, get_host, get_model, load_cos_config,
    CFG_OSS_ID, CFG_OSS_PATH,
)
from api_client import (
    draw_gpt_image, draw_result,
    extract_task_id, extract_image_url, extract_oss_url,
    extract_status, extract_failure_reason,
)
from log_manager import resolve_logs_dir, update_index, rebuild_index, INDEX_FILE

DEFAULT_CONCURRENCY = 10
DEFAULT_START_POLL_DELAY = 14
DEFAULT_POLL_INTERVAL = 5
DEFAULT_MAX_POLL_ROUNDS = 60


def auto_detect_project_dir(cwd=None):
    """自动从工作空间结构检测项目根目录。

    检测逻辑（按优先级）：
      1. 如果 CWD 直接包含 project/ 子目录且其下恰有一个非隐藏子目录，返回该子目录绝对路径
      2. 如果 CWD 已经是某个项目的目录（包含 .logs 等特征），返回 CWD
      3. 否则返回 None（调用方必须提供 --project-dir）

    多项目时必须显式指定 --project-dir，禁止回退到工作空间根目录。
    """
    if cwd is None:
        cwd = os.getcwd()

    project_root = os.path.join(cwd, "project")
    if os.path.isdir(project_root):
        projects = [
            d for d in os.listdir(project_root)
            if os.path.isdir(os.path.join(project_root, d)) and not d.startswith(".")
        ]
        if len(projects) == 1:
            return os.path.join(project_root, projects[0])
        if len(projects) > 1:
            print(json.dumps({
                "error": "检测到多个项目目录，必须通过 --project-dir 显式指定",
                "projects": projects,
            }, ensure_ascii=False), file=sys.stderr)
            return None
    return None


def sanitize_filename(text, max_length=50):
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    if len(text) > max_length:
        text = text[:max_length]
    return text.strip()


def download_image(url, output_path, timeout=60):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception:
        return False


def submit_single_task(task_config, api_key, host, model, task_index,
                       oss_id=None, oss_path=None, cos_config=None,
                       timestamp=None, logs_dir=None):
    """提交单个生成任务（POST /v1/api/generate，replyType=async）"""
    try:
        prompt = task_config.get("prompt", "")
        image_size = task_config.get("imageSize") or task_config.get("image_size")
        aspect_ratio = task_config.get("aspectRatio") or task_config.get("aspect_ratio")
        urls = task_config.get("urls") or task_config.get("images")
        task_model = task_config.get("model") or model

        task_logs_dir = resolve_logs_dir(logs_dir)

        result, uploaded_refs = draw_gpt_image(
            prompt, api_key, host, task_model,
            image_size, aspect_ratio, urls,
            oss_id=oss_id, oss_path=oss_path,
            cos_config=cos_config,
            timestamp=timestamp,
            logs_dir=task_logs_dir,
        )

        task_id = extract_task_id(result)
        image_url = extract_image_url(result)

        status = extract_status(result)
        if status == "failed" or status == "violation":
            error_msg = extract_failure_reason(result)
            return {
                "index": task_index,
                "prompt": prompt,
                "status": "failed",
                "task_id": task_id,
                "result": result,
                "image_url": None,
                "uploaded_refs": uploaded_refs,
                "error": error_msg,
                "config": task_config,
            }

        if image_url:
            return {
                "index": task_index,
                "prompt": prompt,
                "status": "completed",
                "task_id": task_id,
                "result": result,
                "image_url": image_url,
                "uploaded_refs": uploaded_refs,
                "error": None,
                "config": task_config,
            }

        if task_id:
            return {
                "index": task_index,
                "prompt": prompt,
                "status": "submitted",
                "task_id": task_id,
                "result": result,
                "image_url": None,
                "uploaded_refs": uploaded_refs,
                "error": None,
                "config": task_config,
            }

        error_msg = "未知错误：未返回 task_id"
        if "error" in result:
            error_msg = result["error"]

        return {
            "index": task_index,
            "prompt": prompt,
            "status": "failed",
            "task_id": None,
            "result": result,
            "image_url": None,
            "uploaded_refs": uploaded_refs,
            "error": error_msg,
            "config": task_config,
        }
    except Exception as e:
        return {
            "index": task_index,
            "prompt": task_config.get("prompt", ""),
            "status": "failed",
            "task_id": None,
            "result": {},
            "image_url": None,
            "uploaded_refs": [],
            "error": str(e),
            "config": task_config,
        }


def poll_task(task_info, api_key, host, max_rounds=DEFAULT_MAX_POLL_ROUNDS, interval=DEFAULT_POLL_INTERVAL):
    """轮询任务结果（GET /v1/api/result）"""
    if task_info["status"] in ("completed", "failed"):
        return task_info

    task_id = task_info.get("task_id")
    if not task_id:
        task_info["status"] = "failed"
        task_info["error"] = "没有 task_id，无法轮询"
        return task_info

    for _ in range(max_rounds):
        time.sleep(interval)
        try:
            result = draw_result(task_id, api_key, host)

            status = extract_status(result)

            if status == "failed" or status == "violation":
                task_info["status"] = "failed"
                task_info["error"] = extract_failure_reason(result)
                task_info["result"] = result
                return task_info

            if status == "succeeded":
                image_url = extract_image_url(result)
                if image_url:
                    task_info["status"] = "completed"
                    task_info["result"] = result
                    task_info["image_url"] = image_url
                    return task_info
        except Exception:
            continue

    task_info["status"] = "timeout"
    task_info["error"] = f"轮询超时，已超过 {max_rounds * interval} 秒"
    return task_info


def run_batch_generation(
    task_configs,
    output_dir,
    api_key,
    host,
    model,
    oss_id=None,
    oss_path=None,
    cos_config=None,
    concurrency=DEFAULT_CONCURRENCY,
    start_poll_delay=DEFAULT_START_POLL_DELAY,
    poll_interval=DEFAULT_POLL_INTERVAL,
    max_poll_rounds=DEFAULT_MAX_POLL_ROUNDS,
    project_dir=None,
    batch_type=None,
    project_id=None,
):
    """执行批量生成"""
    total = len(task_configs)
    batch_id = f"batch_{time.strftime('%Y%m%d_%H%M%S')}"
    submitted_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    timestamp = time.strftime("%Y%m%d_%H%M%S")

    os.makedirs(output_dir, exist_ok=True)

    if project_dir:
        effective_project_dir = project_dir
    else:
        detected = auto_detect_project_dir()
        if detected is None:
            print(json.dumps({
                "error": "无法自动检测项目目录，请通过 --project-dir 显式指定",
                "hint": "例如: --project-dir \"project/江苏吉泰安防科技\"",
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        if detected != os.getcwd():
            print(json.dumps({
                "event": "project_dir_auto_detected",
                "detected": detected,
            }, ensure_ascii=False), file=sys.stderr)
        effective_project_dir = detected
    batch_logs_dir = os.path.join(effective_project_dir, ".logs")
    os.makedirs(batch_logs_dir, exist_ok=True)

    tasks = []
    print(json.dumps({"event": "batch_submit_start", "total": total, "concurrency": concurrency, "model": model}, ensure_ascii=False), file=sys.stderr)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_index = {
            executor.submit(
                submit_single_task, task_config, api_key, host, model, i,
                oss_id, oss_path, cos_config, timestamp, batch_logs_dir
            ): i
            for i, task_config in enumerate(task_configs)
        }

        for future in as_completed(future_to_index):
            task_info = future.result()
            tasks.append(task_info)
            print(json.dumps({
                "event": "task_submitted",
                "index": task_info["index"],
                "prompt": task_info["prompt"],
                "status": task_info["status"],
                "task_id": task_info.get("task_id"),
            }, ensure_ascii=False), file=sys.stderr)

    tasks.sort(key=lambda x: x["index"])

    submitted_count = sum(1 for t in tasks if t["status"] == "submitted")
    completed_count = sum(1 for t in tasks if t["status"] == "completed")
    failed_count = sum(1 for t in tasks if t["status"] == "failed")

    print(json.dumps({
        "event": "batch_submit_complete",
        "total": total,
        "submitted": submitted_count,
        "completed_immediately": completed_count,
        "failed": failed_count,
    }, ensure_ascii=False), file=sys.stderr)

    tasks_to_poll = [t for t in tasks if t["status"] == "submitted"]
    if tasks_to_poll:
        print(json.dumps({
            "event": "poll_start",
            "delay": start_poll_delay,
            "pending_count": len(tasks_to_poll),
        }, ensure_ascii=False), file=sys.stderr)
        time.sleep(start_poll_delay)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_task = {
                executor.submit(
                    poll_task, task, api_key, host, max_poll_rounds, poll_interval
                ): task
                for task in tasks_to_poll
            }

            for future in as_completed(future_to_task):
                task_info = future.result()
                print(json.dumps({
                    "event": "task_complete",
                    "index": task_info["index"],
                    "prompt": task_info["prompt"],
                    "status": task_info["status"],
                    "task_id": task_info.get("task_id"),
                }, ensure_ascii=False), file=sys.stderr)

    print(json.dumps({"event": "download_start"}, ensure_ascii=False), file=sys.stderr)

    for task in tasks:
        if task["status"] == "completed" and task.get("image_url"):
            config = task.get("config", {})
            task_filename = config.get("filename")

            if task_filename:
                output_path = os.path.join(output_dir, task_filename)
            else:
                safe_name = sanitize_filename(task["prompt"])
                filename = f"{task['index'] + 1:03d}_{safe_name}.png"
                output_path = os.path.join(output_dir, filename)

            if download_image(task["image_url"], output_path):
                task["local_path"] = output_path
                print(json.dumps({
                    "event": "image_downloaded",
                    "index": task["index"],
                    "path": output_path,
                }, ensure_ascii=False), file=sys.stderr)
            else:
                task["download_error"] = "下载失败"
                print(json.dumps({
                    "event": "image_download_failed",
                    "index": task["index"],
                    "url": task["image_url"],
                }, ensure_ascii=False), file=sys.stderr)

    completed = [t for t in tasks if t["status"] == "completed"]
    failed = [t for t in tasks if t["status"] in ("failed", "timeout")]

    result = {
        "batch_id": batch_id,
        "submitted_at": submitted_at,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": total,
        "succeeded": len(completed),
        "failed": len(failed),
        "output_dir": output_dir,
        "model": model,
        "results": [
            {
                "index": t["index"],
                "prompt": t["prompt"],
                "status": t["status"],
                "task_id": t.get("task_id"),
                "image_url": t.get("image_url"),
                "oss_url": extract_oss_url(t.get("result", {})),
                "local_path": t.get("local_path"),
                "uploaded_refs": t.get("uploaded_refs", []),
                "error": t.get("error") or t.get("download_error"),
                "config": t.get("config"),
            }
            for t in tasks
        ],
        "failed_tasks": [
            {
                "index": t["index"],
                "prompt": t["prompt"],
                "status": t["status"],
                "task_id": t.get("task_id"),
                "error": t.get("error") or t.get("download_error"),
                "config": t.get("config"),
            }
            for t in failed
        ],
    }

    if batch_type:
        result["type"] = batch_type

    if project_id:
        result["project_id"] = project_id

    if oss_id or any(t.get("config", {}).get("oss_id") for t in task_configs):
        result["oss_config"] = {
            "oss_id": oss_id,
            "oss_path": oss_path,
        }

    logs_dir = batch_logs_dir

    batch_log_filename = f"{batch_id}.json"
    batch_log_path = os.path.join(logs_dir, batch_log_filename)
    try:
        with open(batch_log_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["batch_log_path"] = batch_log_path
    except OSError:
        pass

    batch_summary = {
        "batch_id": batch_id,
        "submitted_at": submitted_at,
        "completed_at": result["completed_at"],
        "total": total,
        "succeeded": len(completed),
        "failed": len(failed),
        "model": model,
        "log_file": batch_log_filename
    }
    if batch_type:
        batch_summary["type"] = batch_type
    if project_id:
        batch_summary["project_id"] = project_id
    batch_summary["output_dir"] = output_dir
    update_index(logs_dir, batch_summary)

    if failed:
        failed_list_path = os.path.join(logs_dir, f"failed_{batch_id}.json")
        try:
            with open(failed_list_path, "w", encoding="utf-8") as f:
                json.dump({
                    "batch_id": batch_id,
                    "failed_tasks": result["failed_tasks"],
                }, f, ensure_ascii=False, indent=2)
            result["failed_list_path"] = failed_list_path
        except OSError:
            pass

    return result


def load_tasks_from_json(file_path):
    """从 JSON 文件加载任务列表"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data, None, None, None, None, None
    if isinstance(data, dict) and "tasks" in data:
        tasks = data["tasks"]
        output_path = data.get("output_path")
        oss_id = data.get("oss_id")
        oss_path = data.get("oss_path")
        model = data.get("model")
        project_id = data.get("project_id")
        return tasks, output_path, oss_id, oss_path, model, project_id

    raise ValueError("JSON 格式错误：必须是任务列表数组或包含 'tasks' 字段的对象")


def main():
    parser = argparse.ArgumentParser(
        description="GRSAI 图像生成 CLI - 从 JSON 任务列表批量生成图像",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 JSON 任务列表生成（每个任务可独立参数）
  python3 batch_generator.py --tasks ./storyboard.json -o ./output

  # 指定模型
  python3 batch_generator.py --tasks ./tasks.json --model gpt-image-2
        """,
    )

    parser.add_argument(
        "--tasks",
        required=True,
        help="JSON 任务列表文件路径",
    )

    parser.add_argument(
        "-o", "--output-dir",
        default="./generated",
        help="输出目录，默认 ./generated",
    )
    parser.add_argument(
        "-p", "--project-dir",
        default=None,
        help="项目根目录，日志将存储在 {project_dir}/.logs/ 下。未指定时将自动检测 CWD 下的 project/ 目录（若唯一则自动使用，否则回退到 CWD）",
    )
    parser.add_argument(
        "--batch-type",
        default=None,
        choices=["character_reference", "storyboard", "other"],
        help="批次类型，用于索引表分类（可选）",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="模型名称，覆盖配置文件 (e.g. gpt-image-2, gpt-image-2-vip)",
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"并发数，默认 {DEFAULT_CONCURRENCY}",
    )
    parser.add_argument(
        "--poll-delay",
        type=int,
        default=DEFAULT_START_POLL_DELAY,
        help=f"轮询开始延迟（秒），默认 {DEFAULT_START_POLL_DELAY}",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"轮询间隔（秒），默认 {DEFAULT_POLL_INTERVAL}",
    )
    parser.add_argument(
        "--max-poll-rounds",
        type=int,
        default=DEFAULT_MAX_POLL_ROUNDS,
        help=f"最大轮询次数，默认 {DEFAULT_MAX_POLL_ROUNDS}",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="重建索引表（从全量文档恢复索引）",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="项目 UUID，用于跨日志关联（与 .meta/projects/{id}/ 一致）",
    )

    args = parser.parse_args()

    try:
        api_key = get_api_key()
        host = get_host()
        model = get_model()

        if args.rebuild_index:
            project_dir = args.project_dir if args.project_dir else auto_detect_project_dir()
            if project_dir is None:
                print(json.dumps({
                    "error": "无法自动检测项目目录，请通过 --project-dir 显式指定",
                }, ensure_ascii=False), file=sys.stderr)
                sys.exit(1)
            logs_dir = os.path.join(project_dir, ".logs")
            if not os.path.exists(logs_dir):
                print(json.dumps({"error": f"日志目录不存在: {logs_dir}"}, ensure_ascii=False), file=sys.stderr)
                sys.exit(1)

            index = rebuild_index(logs_dir)
            if index:
                print(json.dumps({
                    "event": "index_rebuilt",
                    "total_batches": index["total_batches"],
                    "index_path": os.path.join(logs_dir, INDEX_FILE)
                }, ensure_ascii=False))
            else:
                print(json.dumps({"error": "索引重建失败"}, ensure_ascii=False), file=sys.stderr)
                sys.exit(1)
            return

        cos_config = load_cos_config()

        task_configs, json_output_path, json_oss_id, json_oss_path, json_model, json_project_id = load_tasks_from_json(args.tasks)
        output_dir = args.output_dir if args.output_dir != "./generated" else (json_output_path or args.output_dir)
        oss_id = json_oss_id or _cfg(CFG_OSS_ID)
        oss_path = json_oss_path or _cfg(CFG_OSS_PATH)
        model = args.model or json_model or model
        project_id = args.project_id or json_project_id

        if not oss_id:
            print(json.dumps({"warning": "oss_id 未配置，将不使用云存储持久化"}, ensure_ascii=False), file=sys.stderr)
        if not oss_path:
            print(json.dumps({"warning": "oss_path 未配置，将不使用云存储持久化"}, ensure_ascii=False), file=sys.stderr)

        result = run_batch_generation(
            task_configs=task_configs,
            output_dir=output_dir,
            api_key=api_key,
            host=host,
            model=model,
            oss_id=oss_id,
            oss_path=oss_path,
            cos_config=cos_config,
            concurrency=args.concurrency,
            start_poll_delay=args.poll_delay,
            poll_interval=args.poll_interval,
            max_poll_rounds=args.max_poll_rounds,
            project_dir=args.project_dir,
            batch_type=args.batch_type,
            project_id=project_id,
        )

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()