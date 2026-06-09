#!/usr/bin/env python3
"""腾讯云 COS 上传模块

提供本地文件上传到腾讯云 COS 存储桶的能力，使用 HMAC-SHA256 签名认证。
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
        method,
        path,
        "",
        canonical_headers,
        signed_headers,
        content_sha256
    ])

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/tc3_request"
    string_to_sign = "\n".join([
        algorithm,
        timestamp,
        credential_scope,
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
    """上传本地文件到腾讯云 COS，返回公开 URL

    使用 timestamp 前缀避免文件名冲突，自动 URL 编码中文文件名。
    """
    original_filename = os.path.basename(local_path)

    if timestamp:
        cos_filename = f"{timestamp}_{original_filename}"
    else:
        cos_filename = original_filename

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
            return f"https://{bucket}.cos.{region}.myqcloud.com{encoded_cos_path}"
        else:
            raise Exception(f"上传失败：HTTP {resp.status}")