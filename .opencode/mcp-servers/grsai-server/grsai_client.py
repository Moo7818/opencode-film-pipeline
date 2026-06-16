#!/usr/bin/env python3
"""GRSAI API 客户端

封装 GRSAI 图像生成和 LLM 调用的统一客户端。
Phase 2：LLM 调用
Phase 3：图像生成（后续扩展）
"""

import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from config import _cfg, get_api_key, get_host

MAX_RETRIES = 3


def call_llm(messages, model=None, temperature=0.7, max_tokens=None, timeout=300):
    """调用 GRSAI LLM API，支持 3 次指数退避重试

    从 call_llm.py call() 函数提取，保持完全一致的行为。

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        model: 模型名，默认从配置读取，fallback "gemini-3.1-pro"
        temperature: 温度，默认 0.7
        max_tokens: 最大 token 数（可选）
        timeout: 请求超时秒数，默认 300

    Returns:
        {"content": str, "finish_reason": str, "usage": dict}

    Raises:
        RuntimeError: 认证失败、上下文超长、请求错误、网络错误
    """
    api_key = get_api_key()
    host = get_host()
    model = model or _cfg("GRSAI_LLM_MODEL") or "gemini-3.1-pro"

    body = {
        "model": model,
        "stream": False,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            return {
                "content": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"),
                "usage": data.get("usage", {}),
            }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise RuntimeError(f"认证失败 (HTTP {e.code}): {err_body[:300]}")
            if e.code == 400 and ("context_length" in err_body.lower() or "token" in err_body.lower()):
                raise RuntimeError(f"上下文超长 (HTTP 400): {err_body[:300]}")
            if e.code == 400:
                raise RuntimeError(f"请求参数错误 (HTTP 400): {err_body[:300]}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"API 失败 (HTTP {e.code}, 已重试{MAX_RETRIES}次): {err_body[:300]}")
        except urllib.error.URLError as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"网络错误 (已重试{MAX_RETRIES}次): {e.reason}")
        wait = min(2 ** attempt, 60) * (0.5 + random.random())
        print(f"  ⚠ 第{attempt}次失败，{wait:.1f}s 后重试...", file=sys.stderr)
        time.sleep(wait)

    raise RuntimeError("不可达状态")


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


def _api_request(url, headers, data=None, timeout=120):
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
    return {"raw": text}


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


def _process_urls(urls, cos_config, timestamp=None):
    """将本地文件路径替换为 COS URL，跳过远程 URL"""
    if not urls:
        return urls, []
    result = []
    uploaded = []
    for url in urls:
        if os.path.exists(url) and os.path.isfile(url):
            if not cos_config:
                raise ValueError("检测到本地文件但未配置 COS 凭证")
            from cos_client import upload_to_cos
            public_url = upload_to_cos(
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


def generate_image(prompt, model, aspect_ratio=None, image_size=None,
                   reference_images=None, oss_id=None, oss_path=None,
                   cos_config=None, timestamp=None,
                   poll_delay=14, poll_interval=5, max_poll_rounds=60):
    """单张图像生成，阻塞直到完成或超时"""
    host = get_host()
    api_key = get_api_key()

    # 1. 处理参考图
    processed_urls, uploaded_refs = _process_urls(reference_images, cos_config, timestamp)

    # 2. 构建请求体
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

    # 3. 提交
    resp_text = _api_request(f"{host}/v1/api/generate", headers, data, timeout=30)
    result = _parse_response(resp_text)
    task_id = _extract_task_id(result)

    # 4. 检查即时结果
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

    # 5. 轮询
    time.sleep(poll_delay)
    for _ in range(max_poll_rounds):
        time.sleep(poll_interval)
        try:
            poll_url = f"{host}/v1/api/result?id={urllib.parse.quote(task_id, safe='')}"
            req = urllib.request.Request(poll_url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = _parse_response(resp.read().decode("utf-8"))

            status = _extract_status(result)
            if status in ("failed", "violation"):
                return {"status": "failed", "error": _extract_failure_reason(result),
                        "task_id": task_id, "uploaded_refs": uploaded_refs}
            if status == "succeeded":
                image_url = _extract_image_url(result)
                if image_url:
                    return {"status": "completed", "image_url": image_url,
                            "oss_url": _extract_oss_url(result), "task_id": task_id,
                            "uploaded_refs": uploaded_refs}
        except Exception:
            continue

    return {"status": "timeout", "error": f"轮询超时 {max_poll_rounds * poll_interval}s",
            "task_id": task_id, "uploaded_refs": uploaded_refs}
