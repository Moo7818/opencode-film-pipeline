#!/usr/bin/env python3
"""GRSAI API 客户端

封装 GRSAI 图像生成和 LLM 调用的统一客户端。
Phase 2：LLM 调用
Phase 3：图像生成（后续扩展）
"""

import json
import os
import sys
import urllib.parse
import asyncio
import httpx

from .config import _cfg, get_api_key, get_host

# ─── 图像生成 ─────────────────────────────────────────────

ASPECT_RATIO_PIXEL_MAP = {
    ("1:1", "1K"): "1024x1024", ("1:1", "2K"): "2048x2048", ("1:1", "4K"): "2880x2880",
    ("16:9", "1K"): "1774x887", ("16:9", "2K"): "2048x1152", ("16:9", "4K"): "3840x2160",
    ("9:16", "1K"): "887x1774", ("9:16", "2K"): "1152x2048", ("9:16", "4K"): "2160x3840",
    ("3:2", "1K"): "1536x1024", ("3:2", "2K"): "2048x1360", ("3:2", "4K"): "3504x2336",
    ("2:3", "1K"): "1024x1536", ("2:3", "2K"): "1360x2048", ("2:3", "4K"): "2336x3504",
    ("21:9", "2K"): "2048x880", ("21:9", "4K"): "3840x1648",
    ("9:21", "2K"): "880x2048", ("9:21", "4K"): "1648x3840",
    ("1:3", "1K"): "688x2048", ("1:3", "4K"): "1280x3840",
    ("3:1", "1K"): "2048x688", ("3:1", "4K"): "3840x1280",
    ("2:1", "1K"): "2048x1024", ("2:1", "4K"): "3840x1920",
    ("1:2", "1K"): "1024x2048", ("1:2", "4K"): "1920x3840",
    ("4:3", "1K"): "1365x1024", ("4:3", "2K"): "2048x1536", ("4:3", "4K"): "2880x2160",
    ("3:4", "1K"): "1024x1365", ("3:4", "2K"): "1536x2048", ("3:4", "4K"): "2160x2880",
}


def resolve_aspect_ratio(ratio, image_size="4K"):
    if not ratio:
        ratio = "1:1"
    ratio = ratio.strip()
    if "x" in ratio.lower():
        return ratio
    image_size = image_size or "4K"
    image_size = image_size.upper()
    if image_size not in ("1K", "2K", "4K"):
        image_size = "4K"
    key = (ratio, image_size)
    if key in ASPECT_RATIO_PIXEL_MAP:
        return ASPECT_RATIO_PIXEL_MAP[key]
    fallback_order = ["4K", "2K", "1K"] if image_size == "4K" else ["2K", "1K", "4K"] if image_size == "2K" else ["1K", "2K", "4K"]
    for fallback_size in fallback_order:
        fallback_key = (ratio, fallback_size)
        if fallback_key in ASPECT_RATIO_PIXEL_MAP:
            return ASPECT_RATIO_PIXEL_MAP[fallback_key]
    return "1024x1024"


def _is_nano_banana_model(model):
    return bool(model and model.lower().startswith("nano-banana"))


def _parse_response(text):
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
    return {}


def _extract_task_id(result):
    return result.get("id")


def _extract_image_url(result):
    results = result.get("results")
    if results and isinstance(results, list) and len(results) > 0:
        return results[0].get("url")
    return result.get("url")


def _extract_oss_url(result):
    results = result.get("results")
    if results and isinstance(results, list) and len(results) > 0:
        return results[0].get("oss_url")
    return result.get("oss_url")


def _extract_status(result):
    return result.get("status")


def _extract_failure_reason(result):
    error = result.get("error")
    if isinstance(error, dict):
        return error.get("message") or "Generation failed"
    return error or "Generation failed"


async def _process_urls(urls, cos_config, timestamp=None):
    """将本地文件路径替换为 COS URL，跳过远程 URL。

    使用全局 COS 缓存避免重复上传：
    - 路径 + mtime + size 快速匹配 → 跳过 hash 计算
    - hash 兜底 → 捕获移动/重命名的文件
    """
    if not urls:
        return urls, []
    from . import cos_cache
    result = []
    uploaded = []
    for url in urls:
        if os.path.exists(url) and os.path.isfile(url):
            if not cos_config:
                raise ValueError("Local file detected but COS credentials not configured")
            cached_url, file_hash = cos_cache.lookup(url)
            if cached_url:
                result.append(cached_url)
                uploaded.append({"local": url, "remote": cached_url, "cached": True})
            else:
                from .cos_client import upload_to_cos
                public_url = await upload_to_cos(
                    url,
                    secret_id=cos_config['secret_id'],
                    secret_key=cos_config['secret_key'],
                    bucket=cos_config['bucket'],
                    region=cos_config['region'],
                    timestamp=timestamp,
                )
                cos_cache.record(url, public_url, file_hash)
                result.append(public_url)
                uploaded.append({"local": url, "remote": public_url, "cached": False})
        else:
            result.append(url)
    cos_cache._save()
    return result, uploaded


_global_client: httpx.AsyncClient | None = None


async def _get_client(timeout=120):
    """获取全局复用的 httpx.AsyncClient，避免连接 churn"""
    global _global_client
    if _global_client is None or _global_client.is_closed:
        _global_client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _global_client


async def _api_request(url, headers, data=None, timeout=120):
    """异步 HTTP 请求（使用全局连接池）"""
    client = await _get_client(timeout)
    # 将 headers 值编码为 latin-1（httpx 要求 header 值为 latin-1 兼容）
    # 中文字符先 URL 编码为 percent-encoded 形式
    import urllib.parse
    encoded_headers = {}
    for k, v in headers.items():
        if isinstance(v, str):
            # 对非 ASCII 字符进行 percent-encoding
            try:
                v.encode('latin-1')
                encoded_headers[k] = v
            except UnicodeEncodeError:
                encoded_headers[k] = urllib.parse.quote(v, safe='')
        else:
            encoded_headers[k] = v
    encoded_headers["Content-Type"] = "application/json"
    body = json.dumps(data).encode("utf-8") if data else None
    response = await client.post(url, content=body, headers=encoded_headers)
    if response.status_code >= 400:
        raise Exception(f"API error {response.status_code}: {response.text}")
    return response.text


async def check_image_status(task_id, host=None, api_key=None):
    """单次非阻塞查询图像生成状态。立即返回，不轮询。

    返回值：
    - status="pending": 生成中，调用方应 sleep 后再次查询
    - status="completed": 生成完成，包含 image_url
    - status="failed": 生成失败，包含 error
    """
    host = host or get_host()
    api_key = api_key or get_api_key()
    client = await _get_client(timeout=30)
    poll_url = f"{host}/v1/api/result?id={urllib.parse.quote(task_id, safe='')}"
    response = await client.get(poll_url, headers={"Authorization": f"Bearer {api_key}"})
    result = _parse_response(response.text)
    status = _extract_status(result)

    if status in ("failed", "violation"):
        return {"status": "failed", "error": _extract_failure_reason(result), "task_id": task_id}
    if status == "succeeded":
        image_url = _extract_image_url(result)
        if image_url:
            return {"status": "completed", "image_url": image_url,
                    "oss_url": _extract_oss_url(result), "task_id": task_id}
    return {"status": "pending", "task_id": task_id}


async def submit_image(prompt, model, aspect_ratio=None, image_size=None,
                       reference_images=None, oss_id=None, oss_path=None,
                       cos_config=None, timestamp=None):
    """异步提交图像生成任务"""
    host = get_host()
    api_key = get_api_key()

    processed_urls, uploaded_refs = await _process_urls(reference_images, cos_config, timestamp)

    headers = {"Authorization": f"Bearer {api_key}"}
    if oss_id:
        headers["oss-id"] = oss_id
    if oss_path:
        headers["oss-path"] = oss_path

    data = {"model": model, "prompt": prompt, "replyType": "async"}

    if _is_nano_banana_model(model):
        ratio = aspect_ratio or "1:1"
        if "x" in ratio.lower():
            ratio = "1:1"
        data["aspectRatio"] = ratio
        if image_size:
            data["imageSize"] = image_size.upper()
    else:
        data["aspectRatio"] = resolve_aspect_ratio(aspect_ratio, image_size)

    if processed_urls:
        data["images"] = processed_urls if isinstance(processed_urls, list) else [processed_urls]

    resp_text = await _api_request(f"{host}/v1/api/generate", headers, data, timeout=120)
    result = _parse_response(resp_text)
    task_id = _extract_task_id(result)

    status = _extract_status(result)
    if status in ("failed", "violation"):
        return {"status": "failed", "error": _extract_failure_reason(result),
                "task_id": task_id, "uploaded_refs": uploaded_refs}

    image_url = _extract_image_url(result)
    if image_url:
        return {"status": "completed", "image_url": image_url,
                "oss_url": _extract_oss_url(result), "task_id": task_id,
                "uploaded_refs": uploaded_refs}

    if not task_id:
        return {"status": "failed", "error": "No task_id returned",
                "task_id": None, "uploaded_refs": uploaded_refs}

    return {"status": "submitted", "task_id": task_id, "uploaded_refs": uploaded_refs}


async def poll_image(task_id, host=None, api_key=None, poll_delay=5, poll_interval=3, max_poll_rounds=60):
    """异步轮询图像生成结果"""
    host = host or get_host()
    api_key = api_key or get_api_key()

    await asyncio.sleep(poll_delay)
    consecutive_failures = 0

    client = await _get_client(timeout=30)
    for _ in range(max_poll_rounds):
        await asyncio.sleep(poll_interval)
        try:
            poll_url = f"{host}/v1/api/result?id={urllib.parse.quote(task_id, safe='')}"
            response = await client.get(poll_url, headers={"Authorization": f"Bearer {api_key}"})

            result = _parse_response(response.text)
            status = _extract_status(result)
            consecutive_failures = 0

            if status in ("failed", "violation"):
                return {"status": "failed", "error": _extract_failure_reason(result),
                        "task_id": task_id}
            if status == "succeeded":
                image_url = _extract_image_url(result)
                if image_url:
                    return {"status": "completed", "image_url": image_url,
                            "oss_url": _extract_oss_url(result), "task_id": task_id}
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                return {"status": "failed", "error": "Polling failed 3 consecutive times",
                        "task_id": task_id}
            continue

    return {"status": "timeout", "error": f"Polling timeout after {max_poll_rounds * poll_interval}s",
            "task_id": task_id}


async def generate_image(prompt, model, aspect_ratio=None, image_size=None,
                         reference_images=None, oss_id=None, oss_path=None,
                         cos_config=None, timestamp=None,
                         poll_delay=5, poll_interval=3, max_poll_rounds=60):
    """异步单张图像生成（submit + poll 组合）"""
    submit_result = await submit_image(
        prompt=prompt, model=model, aspect_ratio=aspect_ratio, image_size=image_size,
        reference_images=reference_images, oss_id=oss_id, oss_path=oss_path,
        cos_config=cos_config, timestamp=timestamp,
    )
    if submit_result.get("status") != "submitted":
        return submit_result
    return await poll_image(
        task_id=submit_result["task_id"],
        poll_delay=poll_delay, poll_interval=poll_interval, max_poll_rounds=max_poll_rounds,
    )
