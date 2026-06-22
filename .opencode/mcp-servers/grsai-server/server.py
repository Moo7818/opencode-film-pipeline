#!/usr/bin/env python3
"""GRSAI MCP Server — 基于 FastMCP 标准范式

提供以下工具：
- grsai_health_check: 检查 API 连通性和凭证有效性
- grsai_call_llm: 调用 GRSAI LLM API
- grsai_generate_image: 调用 GRSAI 图像生成 API
- grsai_batch_generate: 批量图像生成
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
def grsai_call_llm(
    messages: list[dict],
    model: str = "gemini-3.1-pro",
    temperature: float = 0.7,
    max_tokens: int | None = None,
    timeout: int = 300,
) -> dict:
    """调用 GRSAI LLM API，支持 3 次指数退避重试"""
    from grsai_client import call_llm
    try:
        return call_llm(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except RuntimeError as e:
        return {"error": str(e)}


@mcp.tool()
def grsai_generate_image(
    prompt: str,
    model: str = "gpt-image-2",
    aspect_ratio: str | None = None,
    image_size: str = "1K",
    reference_images: list[str] | None = None,
    negative_prompt: str | None = None,
    oss_id: str | None = None,
    oss_path: str | None = None,
    poll_delay: int = 14,
    poll_interval: int = 5,
    max_poll_rounds: int = 60,
) -> dict:
    """调用 GRSAI 图像生成 API，阻塞直到图片生成完成或超时"""
    from grsai_client import generate_image
    from config import load_cos_config, _cfg, CFG_OSS_ID, CFG_OSS_PATH
    try:
        return generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            reference_images=reference_images,
            oss_id=oss_id or _cfg(CFG_OSS_ID),
            oss_path=oss_path or _cfg(CFG_OSS_PATH),
            cos_config=load_cos_config(),
            poll_delay=poll_delay,
            poll_interval=poll_interval,
            max_poll_rounds=max_poll_rounds,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def grsai_batch_generate(
    tasks: list[dict],
    output_dir: str = "./output",
    concurrency: int = 10,
    batch_type: str | None = None,
) -> dict:
    """批量提交图像生成任务，并发轮询，下载结果到本地"""
    from grsai_client import generate_image
    from config import load_cos_config, get_model
    import os
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        cos_config = load_cos_config()
        default_model = get_model()
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        os.makedirs(output_dir, exist_ok=True)

        def run_task(idx, task):
            task_model = task.get("model") or default_model
            result = generate_image(
                prompt=task["prompt"],
                model=task_model,
                aspect_ratio=task.get("aspect_ratio"),
                image_size=task.get("image_size"),
                reference_images=task.get("images"),
                cos_config=cos_config,
                timestamp=timestamp,
            )
            if result["status"] == "completed" and result.get("image_url"):
                filename = task.get("filename") or f"{idx+1:03d}.png"
                local_path = os.path.join(output_dir, filename)
                try:
                    import urllib.request
                    urllib.request.urlretrieve(result["image_url"], local_path)
                    result["local_path"] = local_path
                except Exception:
                    result["download_error"] = "下载失败"
            result["index"] = idx
            return result

        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(run_task, i, t): i for i, t in enumerate(tasks)}
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda x: x["index"])

        succeeded = sum(1 for r in results if r["status"] == "completed")
        failed = len(results) - succeeded
        batch_id = f"batch_{timestamp}"

        return {
            "batch_id": batch_id,
            "total": len(tasks),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }
    except Exception as e:
        return {"error": str(e)}


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
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
