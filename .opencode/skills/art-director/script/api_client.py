#!/usr/bin/env python3
"""API 调用模块

封装 GRSAI 图像生成 API 的调用逻辑：
- POST /v1/api/generate（replyType=async）— 图像生成
- GET /v1/api/result?id=xxx — 结果查询

自动根据模型前缀选择参数格式：
- gpt-image-*: aspectRatio 使用像素格式
- nano-banana-*: aspectRatio 使用比例格式 + imageSize
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from config import _cfg, CFG_OSS_ID, CFG_OSS_PATH
from file_cache import process_urls
from log_manager import resolve_logs_dir

ASPECT_RATIO_PIXEL_MAP = {
    ("1:1", "1K"): "1024x1024",
    ("1:1", "2K"): "2048x2048",
    ("1:1", "4K"): "2880x2880",
    ("16:9", "1K"): "1774x887",
    ("16:9", "2K"): "2048x1152",
    ("16:9", "4K"): "3840x2160",
    ("9:16", "1K"): "887x1774",
    ("9:16", "2K"): "1152x2048",
    ("9:16", "4K"): "2160x3840",
    ("3:2", "1K"): "1536x1024",
    ("3:2", "2K"): "2048x1360",
    ("3:2", "4K"): "3504x2336",
    ("2:3", "1K"): "1024x1536",
    ("2:3", "2K"): "1360x2048",
    ("2:3", "4K"): "2336x3504",
    ("21:9", "2K"): "2048x880",
    ("21:9", "4K"): "3840x1648",
    ("9:21", "2K"): "880x2048",
    ("9:21", "4K"): "1648x3840",
    ("1:3", "1K"): "688x2048",
    ("1:3", "4K"): "1280x3840",
    ("3:1", "1K"): "2048x688",
    ("3:1", "4K"): "3840x1280",
    ("2:1", "1K"): "2048x1024",
    ("2:1", "4K"): "3840x1920",
    ("1:2", "1K"): "1024x2048",
    ("1:2", "4K"): "1920x3840",
    ("4:3", "1K"): "1365x1024",
    ("4:3", "2K"): "2048x1536",
    ("4:3", "4K"): "2880x2160",
    ("3:4", "1K"): "1024x1365",
    ("3:4", "2K"): "1536x2048",
    ("3:4", "4K"): "2160x2880",
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


def api_request(url, headers, data=None, timeout=120):
    """发送 JSON API 请求"""
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            **headers,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        raise Exception(f"API 错误 {e.code}: {err_body}")
    except urllib.error.URLError as e:
        raise Exception(f"网络错误: {e.reason}")


def parse_response(text):
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
    return {"raw": text}


def draw_gpt_image(prompt, api_key, host, model,
                   image_size=None, aspect_ratio=None,
                   urls=None, oss_id=None, oss_path=None,
                   cos_config=None, timestamp=None, logs_dir=None):
    """调用图像生成接口（POST /v1/api/generate）

    所有模型统一使用此接口，replyType=async 异步模式。
    - gpt-image-*: aspectRatio 使用像素格式，由 resolve_aspect_ratio 自动转换
    - nano-banana-*: aspectRatio 使用比例格式，额外传 imageSize 字段
    """
    logs_dir = resolve_logs_dir(logs_dir)

    url = f"{host.rstrip('/')}/v1/api/generate"
    headers = {"Authorization": f"Bearer {api_key}"}

    if oss_id:
        headers["oss-id"] = oss_id
    if oss_path:
        headers["oss-path"] = oss_path

    processed_urls, uploaded_refs = process_urls(urls, cos_config, timestamp=timestamp, logs_dir=logs_dir)

    data = {
        "model": model,
        "prompt": prompt,
        "replyType": "async",
    }

    if _is_nano_banana_model(model):
        ratio = aspect_ratio or "1:1"
        if "x" in ratio.lower():
            ratio = "1:1"
        data["aspectRatio"] = ratio
        if image_size:
            data["imageSize"] = image_size.upper()
    else:
        pixel_ratio = resolve_aspect_ratio(aspect_ratio, image_size)
        data["aspectRatio"] = pixel_ratio

    if processed_urls:
        data["images"] = processed_urls if isinstance(processed_urls, list) else [processed_urls]

    resp_text = api_request(url, headers, data, timeout=30)
    return parse_response(resp_text), uploaded_refs


def draw_result(task_id, api_key, host):
    """查询绘画结果（GET /v1/api/result?id=xxx）"""
    url = f"{host.rstrip('/')}/v1/api/result?id={urllib.parse.quote(task_id, safe='')}"
    headers = {"Authorization": f"Bearer {api_key}"}

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return parse_response(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        try:
            return json.loads(err_body)
        except json.JSONDecodeError:
            return {"status": "failed", "error": f"HTTP {e.code}: {err_body[:300]}"}
    except urllib.error.URLError as e:
        return {"status": "failed", "error": f"网络错误: {e.reason}"}


def extract_task_id(result):
    return result.get("id")


def extract_image_url(result):
    results = result.get("results")
    if results and isinstance(results, list) and len(results) > 0:
        return results[0].get("url")
    return result.get("url")


def extract_oss_url(result):
    results = result.get("results")
    if results and isinstance(results, list) and len(results) > 0:
        return results[0].get("oss_url")
    return result.get("oss_url")


def extract_status(result):
    return result.get("status")


def extract_failure_reason(result):
    error = result.get("error")
    if isinstance(error, dict):
        return error.get("message") or "生成失败"
    return error or "生成失败"