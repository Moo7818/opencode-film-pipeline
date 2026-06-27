#!/usr/bin/env python3
"""GRSAI MCP Server — 基于 FastMCP 标准范式

提供以下工具：
- grsai_health_check: 检查 API 连通性和凭证有效性
- grsai_submit_image: 提交图像生成任务，立即返回 task_id（不阻塞）
- grsai_poll_result: 根据 task_id 轮询结果
- grsai_batch_generate: 批量提交并轮询（注意：任务量大时可能超时，建议分批提交后逐个 poll）
- grsai_upload_cos: 腾讯云 COS 上传
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("grsai")


@mcp.tool()
def grsai_health_check() -> dict:
    """检查 GRSAI API 连通性和凭证有效性"""
    from config import _cfg, CFG_API_KEY, CFG_HOST, CFG_COS_ID, CFG_COS_KEY, CFG_COS_BUCKET, CFG_COS_REGION, DEFAULT_HOST

    api_key = _cfg(CFG_API_KEY)
    host = _cfg(CFG_HOST) or DEFAULT_HOST
    cos_configured = all([
        _cfg(CFG_COS_ID),
        _cfg(CFG_COS_KEY),
        _cfg(CFG_COS_BUCKET),
        _cfg(CFG_COS_REGION),
    ])

    return {
        "api_key_valid": bool(api_key),
        "host": host,
        "cos_configured": cos_configured,
    }


@mcp.tool()
def grsai_submit_image(
    prompt: str,
    model: str = "gpt-image-2",
    aspect_ratio: str | None = None,
    image_size: str = "1K",
    reference_images: list[str] | None = None,
    oss_id: str | None = None,
    oss_path: str | None = None,
) -> dict:
    """提交图像生成任务，立即返回 task_id。不阻塞等待生成完成。
    
    返回 status="submitted" 时，请使用 grsai_poll_result 传入 task_id 查询结果。
    poll 默认参数为 delay=5s, interval=3s, max_rounds=20（总最长 ~65s）。
    """
    from grsai_client import submit_image
    from config import load_cos_config, _cfg, CFG_OSS_ID, CFG_OSS_PATH
    try:
        return submit_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            reference_images=reference_images,
            oss_id=oss_id or _cfg(CFG_OSS_ID),
            oss_path=oss_path or _cfg(CFG_OSS_PATH),
            cos_config=load_cos_config(),
        )
    except ValueError as e:
        return {"error": str(e)}
    except Exception:
        return {"error": "提交图像时服务器内部错误"}


@mcp.tool()
def grsai_poll_result(
    task_id: str,
    poll_delay: int = 5,
    poll_interval: int = 3,
    max_poll_rounds: int = 20,
) -> dict:
    """根据 task_id 轮询图像生成结果。阻塞直到完成或超时。
    
    推荐策略：
    - 首次调用后等 5-10s 再 poll
    - 默认轮询：poll_delay=5, poll_interval=3, max_poll_rounds=20（~65s，适配 MCP 120s 超时）
    - 长任务：手动传 max_poll_rounds=60，如 poll_delay=5, poll_interval=3, max_poll_rounds=60（~185s）
    """
    from grsai_client import poll_image
    try:
        return poll_image(
            task_id=task_id,
            poll_delay=poll_delay,
            poll_interval=poll_interval,
            max_poll_rounds=max_poll_rounds,
        )
    except ValueError as e:
        return {"error": str(e)}
    except Exception:
        return {"error": "轮询时服务器内部错误"}


@mcp.tool()
def grsai_batch_generate(
    tasks: list[dict],
    output_dir: str = "./output",
    concurrency: int = 10,
    batch_type: str | None = None,
) -> dict:
    """批量提交图像生成任务。支持两种模式：
    - batch_type=None（默认）：提交 + 轮询 + 下载，一揽子完成
    - batch_type="submit_only"：仅提交不轮询，返回所有 task_id，适合大批量任务
    
    注意 MCP tool 默认 120s 超时，大批量任务建议：
    1. 先逐个 grsai_submit_image 拿到所有 task_id
    2. 再用 grsai_poll_result 分批轮询（默认 max_poll_rounds=20 适配 120s 超时）
    """
    from grsai_client import submit_image, poll_image
    from config import load_cos_config, get_model
    import os
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        cos_config = load_cos_config()
        default_model = get_model()
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        os.makedirs(output_dir, exist_ok=True)

        # 阶段 1：全部提交
        def submit_task(idx, task):
            task_model = task.get("model") or default_model
            return {
                "index": idx,
                "filename": task.get("filename") or f"{idx+1:03d}.png",
                "result": submit_image(
                    prompt=task["prompt"],
                    model=task_model,
                    aspect_ratio=task.get("aspect_ratio"),
                    image_size=task.get("image_size"),
                    reference_images=task.get("images"),
                    cos_config=cos_config,
                    timestamp=timestamp,
                    oss_id=task.get("oss_id"),
                    oss_path=task.get("oss_path"),
                ),
            }

        submitted = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(submit_task, i, t): i for i, t in enumerate(tasks)}
            for future in as_completed(futures):
                submitted.append(future.result())
        submitted.sort(key=lambda x: x["index"])

        submitted_ids = []
        for item in submitted:
            r = item["result"]
            if r.get("status") == "submitted" or r.get("status") == "completed":
                submitted_ids.append({"index": item["index"], "filename": item["filename"], **r})
            else:
                submitted_ids.append({"index": item["index"], "filename": item["filename"], "status": "failed", **r})

        # 阶段 2：根据 batch_type 决定是否轮询
        if batch_type == "submit_only":
            # 仅提交模式：返回所有 task_id，不轮询
            results = submitted_ids
        else:
            # 默认模式：轮询所有已提交的任务并下载
            def poll_task(item):
                if item.get("status") == "completed":
                    return item
                if item.get("status") != "submitted":
                    return item
                result = poll_image(
                    task_id=item["task_id"],
                    poll_delay=5,
                    poll_interval=3,
                    max_poll_rounds=20,
                )
                # 下载
                if result.get("status") == "completed" and result.get("image_url"):
                    local_path = os.path.join(output_dir, item["filename"])
                    try:
                        import urllib.request
                        response = urllib.request.urlopen(result["image_url"], timeout=60)
                        with open(local_path, 'wb') as f:
                            f.write(response.read())
                        result["local_path"] = local_path
                    except Exception:
                        result["download_error"] = "下载失败"
                result["index"] = item["index"]
                return result

            results = []
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {executor.submit(poll_task, item): item["index"] for item in submitted_ids}
                for future in as_completed(futures):
                    results.append(future.result())
            results.sort(key=lambda x: x["index"])

        succeeded = sum(1 for r in results if r["status"] == "completed")
        failed = len(results) - succeeded
        batch_id = f"batch_{time.strftime('%Y%m%d_%H%M%S')}"

        return {
            "batch_id": batch_id,
            "total": len(tasks),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }
    except ValueError as e:
        return {"error": str(e)}
    except Exception:
        return {"error": "批量生成时服务器内部错误"}


@mcp.tool()
def grsai_upload_cos(local_path: str) -> dict:
    """上传本地文件到腾讯云 COS，返回公开 URL"""
    from cos_client import upload_to_cos
    from config import load_cos_config
    try:
        cos_config = load_cos_config()
        if not cos_config:
            return {"error": "未配置 COS 凭证"}
        url = upload_to_cos(
            local_path=local_path,
            secret_id=cos_config["secret_id"],
            secret_key=cos_config["secret_key"],
            bucket=cos_config["bucket"],
            region=cos_config["region"],
        )
        return {"url": url}
    except ValueError as e:
        return {"error": str(e)}
    except Exception:
        return {"error": "上传时服务器内部错误"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
