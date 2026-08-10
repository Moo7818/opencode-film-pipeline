#!/usr/bin/env python3
"""腾讯云 COS 上传模块

从 art-director/script/cos_uploader.py 提取，保持 HMAC-SHA256 签名逻辑不变。
"""

import datetime
import hashlib
import hmac
import os
import sys
import urllib.parse
import asyncio
import httpx


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


async def upload_to_cos(local_path, secret_id, secret_key, bucket, region, timestamp=None):
    """异步上传本地文件到腾讯云 COS，返回公开 URL"""
    original_filename = os.path.basename(local_path)
    cos_filename = f"{timestamp}_{original_filename}" if timestamp else original_filename

    raw_cos_path = f"/{cos_filename}"
    encoded_cos_path = urllib.parse.quote(raw_cos_path, safe='/')
    content_type = "application/octet-stream"

    sha256_hash = hashlib.sha256()
    with open(local_path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            sha256_hash.update(chunk)
    content_sha256 = sha256_hash.hexdigest()

    with open(local_path, "rb") as f:
        data = f.read()

    headers = _make_cos_auth_header(
        secret_id, secret_key, bucket, region,
        "PUT", encoded_cos_path, content_type, content_sha256
    )

    url = f"https://{bucket}.cos.{region}.myqcloud.com{encoded_cos_path}"

    max_retries = 3
    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(max_retries):
            try:
                response = await client.put(url, content=data, headers=headers)
                if response.status_code in (200, 204):
                    return url
                raise Exception(f"Upload failed: HTTP {response.status_code}")
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"Upload failed ({e}), retrying in {wait}s (attempt {attempt + 2})...", file=sys.stderr)
                    await asyncio.sleep(wait)
                else:
                    raise