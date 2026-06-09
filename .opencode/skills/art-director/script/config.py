#!/usr/bin/env python3
"""配置加载模块

凭证加载优先级：环境变量 > .opencode/credentials/media_gen_config.json > ~/.trae-cn/media_gen_config.json
"""

import json
import os
import sys
from pathlib import Path

CFG_API_KEY     = "GRSAI_API_KEY"
CFG_HOST        = "GRSAI_API_HOST"
CFG_MODEL       = "GRSAI_MODEL"
CFG_OSS_ID      = "GRSAI_OSS_ID"
CFG_OSS_PATH    = "GRSAI_OSS_PATH"
CFG_COS_ID      = "TENCENT_COS_SECRET_ID"
CFG_COS_KEY     = "TENCENT_COS_SECRET_KEY"
CFG_COS_BUCKET  = "TENCENT_COS_BUCKET"
CFG_COS_REGION  = "TENCENT_COS_REGION"

DEFAULT_HOST  = "https://grsai.dakka.com.cn"
DEFAULT_MODEL = "gpt-image-2"

# 优先：工作空间下的 .opencode/credentials/media_gen_config.json
# 回退：~/.trae-cn/media_gen_config.json
CONFIG_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".opencode" / "credentials" / "media_gen_config.json"
LEGACY_CONFIG_FILE = Path.home() / ".trae-cn" / "media_gen_config.json"

_config_cache = None


def load_skill_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    # 尝试新路径：工作空间下的 .opencode/credentials/media_gen_config.json
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
            return _config_cache
        except Exception:
            pass
    # 回退旧路径：~/.trae-cn/media_gen_config.json
    if LEGACY_CONFIG_FILE.exists():
        try:
            with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
            return _config_cache
        except Exception:
            pass
    _config_cache = {}
    return _config_cache


def _cfg(key):
    val = os.environ.get(key, "")
    if val:
        return val
    return load_skill_config().get(key, "")


def get_api_key():
    key = _cfg(CFG_API_KEY)
    if not key:
        print(f"缺少 {CFG_API_KEY}，请在 {CONFIG_FILE} 或环境变量中配置", file=sys.stderr)
        sys.exit(1)
    return key


def get_host():
    return _cfg(CFG_HOST) or DEFAULT_HOST


def get_model():
    return _cfg(CFG_MODEL) or DEFAULT_MODEL


def load_cos_config():
    sid    = _cfg(CFG_COS_ID)
    skey   = _cfg(CFG_COS_KEY)
    bucket = _cfg(CFG_COS_BUCKET)
    region = _cfg(CFG_COS_REGION)

    if sid and skey and bucket and region:
        return {
            "secret_id": sid,
            "secret_key": skey,
            "bucket": bucket,
            "region": region,
        }
    return None