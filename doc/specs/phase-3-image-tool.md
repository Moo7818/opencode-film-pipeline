# Phase 3 Spec：图像生成 API 工具化

> 目标：将图像生成 API 的提交+轮询+COS 上传封装为 MCP tool

## 输入上下文

读取以下文件（全部完整读取）：
- `.opencode/skills/art-director/script/api_client.py`（218 行）—— 图像 API 调用封装
- `.opencode/skills/art-director/script/cos_uploader.py`（110 行）—— 腾讯云 COS 上传
- `.opencode/skills/art-director/script/file_cache.py`（155 行）—— SHA256 去重缓存
- `.opencode/skills/art-director/script/batch_generator.py`（632 行）—— 批量生成 CLI 主入口
- `.opencode/mcp-servers/grsai-server/config.py`（Phase 1 产出）
- `.opencode/mcp-servers/grsai-server/grsai_client.py`（Phase 2 产出）
- `.opencode/mcp-servers/grsai-server/server.py`（Phase 0 产出）

## 任务

### 1. 创建 cos_client.py

创建 `.opencode/mcp-servers/grsai-server/cos_client.py`，从 `cos_uploader.py` 提取 COS 上传逻辑：

```python
#!/usr/bin/env python3
"""腾讯云 COS 上传模块

从 art-director/script/cos_uploader.py 提取，保持 HMAC-SHA256 签名逻辑不变。
"""

import datetime
import hashlib
import hmac
import os
import urllib.parse
import urllib.request


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key, date_stamp, region, service):
    k_date = _sign(("TC3" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "tc3_request")
    return k_signing


def _make_cos_auth_header(secret_id, secret_key, bucket, region,
                          method, path, content_type, content_sha256):
    service = "cos"
    host = f"{bucket}.cos.{region}.myqcloud.com"
    now = datetime.datetime.utcnow()
    date_stamp = now.strftime("%Y-%m-%d")
    timestamp = str(int(now.timestamp()))

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-content-sha256:{content_sha256}\n"
    )
    signed_headers = "content-type;host;x-content-sha256"
    canonical_request = "\n".join([
        method, path, "", canonical_headers, signed_headers, content_sha256
    ])

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/tc3_request"
    string_to_sign = "\n".join([
        algorithm, timestamp, credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    ])

    signing_key = _get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Host": host,
        "Content-Type": content_type,
        "X-Content-Sha256": content_sha256,
    }


def upload_to_cos(local_path, secret_id, secret_key, bucket, region, timestamp=None):
    """上传本地文件到腾讯云 COS，返回公开 URL"""
    original_filename = os.path.basename(local_path)
    cos_filename = f"{timestamp}_{original_filename}" if timestamp else original_filename

    raw_cos_path = f"/{cos_filename}"
    encoded_cos_path = urllib.parse.quote(raw_cos_path, safe='/')

    content_type = "application/octet-stream"

    with open(local_path, "rb") as f:
        data = f.read()

    content_sha256 = hashlib.sha256(data).hexdigest()
    headers = _make_cos_auth_header(
        secret_id, secret_key, bucket, region,
        "PUT", encoded_cos_path, content_type, content_sha256
    )

    url = f"https://{bucket}.cos.{region}.myqcloud.com{encoded_cos_path}"
    req = urllib.request.Request(url, data=data, method="PUT", headers=headers)

    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status in (200, 204):
            return url
        else:
            raise Exception(f"上传失败：HTTP {resp.status}")
```

### 2. 扩展 grsai_client.py

在 `.opencode/mcp-servers/grsai-server/grsai_client.py` 中追加图像生成功能。从以下文件提取核心逻辑：

从 `api_client.py` 提取：
- `ASPECT_RATIO_PIXEL_MAP`（lines 22-56）—— 比例→像素映射表
- `resolve_aspect_ratio()`（lines 59-77）—— 比例解析
- `_is_nano_banana_model()`（lines 80-81）—— 模型判断
- `api_request()`（lines 84-104）—— HTTP 请求封装
- `parse_response()`（lines 107-122）—— 响应解析
- `draw_gpt_image()`（lines 125-168）—— 提交生成任务
- `draw_result()`（lines 171-189）—— 查询结果
- `extract_task_id/image_url/oss_url/status/failure_reason`（lines 192-218）

从 `file_cache.py` 提取：
- `compute_file_hash()`（lines 47-54）
- `process_urls()`（lines 97-155）—— 本地文件→COS URL 转换

在 `grsai_client.py` 末尾追加以下函数：

```python
# ─── 图像生成 ─────────────────────────────────────────────

ASPECT_RATIO_PIXEL_MAP = {
    # 从 api_client.py lines 22-56 完整复制
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
    # 从 api_client.py lines 59-77 完整复制
    ...


def _is_nano_banana_model(model):
    return bool(model and model.lower().startswith("nano-banana"))


def _api_request(url, headers, data=None, timeout=120):
    # 从 api_client.py lines 84-104 完整复制
    ...


def _parse_response(text):
    # 从 api_client.py lines 107-122 完整复制
    ...


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
```

### 3. 在 server.py 中注册图像相关 tool

修改 `.opencode/mcp-servers/grsai-server/server.py`，在 `list_tools()` 和 `call_tool()` 中添加以下 3 个 tool：

**grsai_generate_image**：
```python
Tool(
    name="grsai_generate_image",
    description="调用 GRSAI 图像生成 API，阻塞直到图片生成完成或超时",
    inputSchema={
        "type": "object",
        "required": ["prompt", "model"],
        "properties": {
            "prompt": {"type": "string", "description": "正向提示词"},
            "model": {"type": "string", "description": "模型名，如 gpt-image-2, nano-banana-pro"},
            "aspect_ratio": {"type": "string", "description": "画面比例，如 16:9, 1024x1024"},
            "image_size": {"type": "string", "enum": ["1K", "2K", "4K"], "description": "分辨率等级"},
            "reference_images": {"type": "array", "items": {"type": "string"}, "description": "参考图路径或 URL"},
            "negative_prompt": {"type": "string", "description": "负向提示词"},
            "poll_delay": {"type": "integer", "default": 14, "description": "首次轮询等待秒数"},
            "poll_interval": {"type": "integer", "default": 5, "description": "轮询间隔秒数"},
            "max_poll_rounds": {"type": "integer", "default": 60, "description": "最大轮询次数"},
        },
    },
),
```

**grsai_batch_generate**：
```python
Tool(
    name="grsai_batch_generate",
    description="批量提交图像生成任务，并发轮询，下载结果到本地",
    inputSchema={
        "type": "object",
        "required": ["tasks"],
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["prompt"],
                    "properties": {
                        "prompt": {"type": "string"},
                        "model": {"type": "string"},
                        "aspect_ratio": {"type": "string"},
                        "image_size": {"type": "string"},
                        "images": {"type": "array", "items": {"type": "string"}},
                        "filename": {"type": "string"},
                    },
                },
            },
            "output_dir": {"type": "string", "default": "./generated"},
            "concurrency": {"type": "integer", "default": 10},
            "batch_type": {"type": "string", "enum": ["character_reference", "storyboard", "other"]},
        },
    },
),
```

**grsai_upload_cos**：
```python
Tool(
    name="grsai_upload_cos",
    description="上传本地文件到腾讯云 COS，返回公开 URL",
    inputSchema={
        "type": "object",
        "required": ["local_path"],
        "properties": {
            "local_path": {"type": "string", "description": "本地文件绝对路径"},
        },
    },
),
```

**call_tool 处理**（添加到 elif 链中）：

```python
elif name == "grsai_generate_image":
    from grsai_client import generate_image
    from config import load_cos_config
    try:
        result = generate_image(
            prompt=arguments["prompt"],
            model=arguments["model"],
            aspect_ratio=arguments.get("aspect_ratio"),
            image_size=arguments.get("image_size"),
            reference_images=arguments.get("reference_images"),
            cos_config=load_cos_config(),
            poll_delay=arguments.get("poll_delay", 14),
            poll_interval=arguments.get("poll_interval", 5),
            max_poll_rounds=arguments.get("max_poll_rounds", 60),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]

elif name == "grsai_batch_generate":
    from grsai_client import generate_image
    from config import load_cos_config, get_model
    import os, time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        tasks = arguments["tasks"]
        output_dir = arguments.get("output_dir", "./generated")
        concurrency = arguments.get("concurrency", 10)
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
            # 下载图片
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

        return [TextContent(type="text", text=json.dumps({
            "batch_id": batch_id, "total": len(tasks),
            "succeeded": succeeded, "failed": failed,
            "results": results,
        }, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]

elif name == "grsai_upload_cos":
    from cos_client import upload_to_cos
    from config import load_cos_config
    try:
        cos_config = load_cos_config()
        if not cos_config:
            return [TextContent(type="text", text=json.dumps({"error": "未配置 COS 凭证"}))]
        url = upload_to_cos(
            local_path=arguments["local_path"],
            secret_id=cos_config["secret_id"],
            secret_key=cos_config["secret_key"],
            bucket=cos_config["bucket"],
            region=cos_config["region"],
        )
        return [TextContent(type="text", text=json.dumps({"url": url}, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
```

### 4. 添加缺失的 import

在 `grsai_client.py` 顶部确保有：

```python
import hashlib
import time
import urllib.parse
```

## 输出文件

| 文件 | 操作 |
|------|------|
| `.opencode/mcp-servers/grsai-server/cos_client.py` | 新建 |
| `.opencode/mcp-servers/grsai-server/grsai_client.py` | 追加图像生成功能 |
| `.opencode/mcp-servers/grsai-server/server.py` | 修改（添加 3 个 tool） |

## 验收

```bash
# 1. 所有文件语法正确
for f in .opencode/mcp-servers/grsai-server/{cos_client,grsai_client,server}.py; do
  python -c "import ast; ast.parse(open('$f').read()); print('$f OK')"
done

# 2. server.py 包含所有 image tool
python -c "
code = open('.opencode/mcp-servers/grsai-server/server.py').read()
for tool in ['grsai_generate_image', 'grsai_batch_generate', 'grsai_upload_cos']:
    assert tool in code, f'{tool} not found'
print('all image tools registered OK')
"

# 3. cos_client 可导入
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from cos_client import upload_to_cos
assert callable(upload_to_cos)
print('cos_client import OK')
"

# 4. grsai_client 可导入
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from grsai_client import generate_image, call_llm, resolve_aspect_ratio
assert callable(generate_image) and callable(call_llm)
print('grsai_client import OK')
"

# 5. 完整依赖链
python -c "
import sys; sys.path.insert(0, '.opencode/mcp-servers/grsai-server')
from config import get_api_key, get_host, load_cos_config
from cos_client import upload_to_cos
from grsai_client import generate_image, call_llm
print('full dependency chain OK')
"
```
