#!/usr/bin/env python3
"""GRSAI API 客户端

封装 GRSAI 图像生成和 LLM 调用的统一客户端。
Phase 2：LLM 调用
Phase 3：图像生成（后续扩展）
"""

import hashlib
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
        return error.get("message") or "生成失败"
    return error or "生成失败"


def _compute_file_hash(local_path):
    sha256 = hashlib.sha256()
    with open(local_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


async def _process_urls(urls, cos_config, timestamp=None):
    """将本地文件路径替换为 COS URL，跳过远程 URL"""
    if not urls:
        return urls, []
    result = []
    uploaded = []
    for url in urls:
        if os.path.exists(url) and os.path.isfile(url):
            if not cos_config:
                raise ValueError("检测到本地文件但未配置 COS 凭证")
            from .cos_client import upload_to_cos
            public_url = await upload_to_cos(
                url,
                secret_id=cos_config['secret_id'],
                secret_key=cos_config['secret_key'],
                bucket=cos_config['bucket'],
                region=cos_config['region'],
                timestamp=timestamp,
            )
            result.append(public_url)
            uploaded.append({"local": url, "remote": public_url, "cached": False})
        else:
            result.append(url)
    return result, uploaded


async def _api_request(url, headers, data=None, timeout=120):
    """异步 HTTP 请求"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = {**headers, "Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        response = await client.post(url, content=body, headers=headers)
        if response.status_code >= 400:
            raise Exception(f"API 错误 {response.status_code}: {response.text}")
        return response.text


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
        return {"status": "failed", "error": "未返回 task_id",
                "task_id": None, "uploaded_refs": uploaded_refs}

    return {"status": "submitted", "task_id": task_id, "uploaded_refs": uploaded_refs,
            "message": f"任务已提交，task_id={task_id}，请使用 poll_image() 查询结果"}


async def poll_image(task_id, host=None, api_key=None, poll_delay=5, poll_interval=3, max_poll_rounds=60):
    """异步轮询图像生成结果"""
    host = host or get_host()
    api_key = api_key or get_api_key()

    await asyncio.sleep(poll_delay)
    consecutive_failures = 0

    async with httpx.AsyncClient(timeout=30) as client:
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
                    return {"status": "failed", "error": "连续轮询失败3次，请稍后重试",
                            "task_id": task_id}
                continue

    return {"status": "timeout", "error": f"轮询超时 {max_poll_rounds * poll_interval}s",
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
