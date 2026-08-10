#!/usr/bin/env python3
"""GRSAI MCP Server — 基于 FastMCP 标准范式

提供以下工具：
- grsai_health_check: 检查 API 连通性和凭证有效性
- grsai_submit_image: 提交图像生成任务，立即返回 task_id（不阻塞）
- grsai_poll_result: 根据 task_id 轮询单个任务结果
- grsai_upload_cos: 腾讯云 COS 上传
"""

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("grsai")


def _error_response(message, code="internal_error", details=None):
    """统一错误响应格式"""
    resp = {"error": message, "code": code}
    if details:
        resp["details"] = details
    return resp


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
def grsai_health_check() -> dict:
    """GRSAI 服务健康检查 — 分层检测
    - Level 1: 配置完整性
    - Level 2: API 连通性（ping GRSAI API）
    - Level 3: COS 配置状态
    """
    from .config import validate_config, _cfg, CFG_API_KEY, CFG_HOST, DEFAULT_HOST

    # Level 1: 配置检查
    cfg = validate_config()

    host = _cfg(CFG_HOST) or DEFAULT_HOST
    api_key = _cfg(CFG_API_KEY)

    # Level 2: API ping（轻量）
    api_reachable = False
    api_ping_error = None
    if api_key:
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{host}/v1/api/result?id=ping_check")
                api_reachable = True  # 任何响应都说明API可达
        except httpx.ConnectError as e:
            api_ping_error = f"Network unreachable: {e}"
        except httpx.HTTPStatusError as e:
            api_ping_error = f"HTTP {e.response.status_code}"
        except Exception as e:
            api_ping_error = str(e)

    # 构建详细结果
    checks = {
        **cfg["checks"],
        "api_reachable": api_reachable,
    }

    warnings = []
    if not cfg["checks"].get("api_key_configured"):
        warnings.append("API Key not configured")
    if not api_reachable and api_key:
        warnings.append(f"API unreachable: {api_ping_error}")

    return {
        "status": "healthy" if (cfg["valid"] and api_reachable) else "degraded" if cfg["valid"] else "unhealthy",
        "host": host,
        "config_source": cfg["config_source"],
        "checks": checks,
        "warnings": warnings,
        "tools_registered": 4,
    }


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
        "destructiveHint": False,
    }
)
async def grsai_submit_image(
    prompt: str,
    model: str = "gpt-image-2",
    aspect_ratio: str | None = None,
    image_size: str = "1K",
    reference_images: list[str] | None = None,
    oss_id: str | None = None,
    oss_path: str | None = None,
) -> dict:
    """提交图像生成任务，立即返回 task_id。不阻塞等待生成完成。

    返回 status="submitted" 时，请等待 5-10s 后使用 grsai_poll_result 传入 task_id 查询结果。
    grsai_poll_result 为非阻塞单次查询，返回 pending 时需再次调用。

    注意：reference_images 中的本地文件路径必须是绝对路径。MCP server 的 CWD 与调用方不同，
    相对路径无法被解析。远程 URL 无需转换。
    """
    from .grsai_client import submit_image
    from .config import load_cos_config, _cfg, CFG_OSS_ID, CFG_OSS_PATH
    try:
        return await submit_image(
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
        return _error_response(str(e), "submit_failed")
    except Exception as e:
        return _error_response(str(e), "submit_failed")


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
)
async def grsai_poll_result(task_id: str) -> dict:
    """非阻塞查询单个图像生成任务的状态。立即返回，不轮询。

    返回 status="pending" 时表示生成中，调用方应等待 5-10s 后再次调用本工具查询。
    返回 status="completed" 时包含 image_url。
    返回 status="failed" 时包含 error。

    推荐调用策略：
    1. submit 后等 5-10s，首次调用本工具
    2. 若 pending，sleep 5-10s 后再次调用
    3. 重复直到 completed 或 failed
    """
    from .grsai_client import check_image_status
    try:
        return await check_image_status(task_id=task_id)
    except ValueError as e:
        return _error_response(str(e), "poll_failed")
    except Exception as e:
        return _error_response(str(e), "poll_failed")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
        "destructiveHint": False,
    }
)
async def grsai_upload_cos(local_path: str) -> dict:
    """上传本地文件到腾讯云 COS，返回公开 URL"""
    from .cos_client import upload_to_cos
    from .config import load_cos_config
    try:
        cos_config = load_cos_config()
        if not cos_config:
            return _error_response("COS credentials not configured", "upload_failed")
        url = await upload_to_cos(
            local_path=local_path,
            secret_id=cos_config["secret_id"],
            secret_key=cos_config["secret_key"],
            bucket=cos_config["bucket"],
            region=cos_config["region"],
        )
        return {"url": url}
    except ValueError as e:
        return _error_response(str(e), "upload_failed")
    except Exception as e:
        return _error_response(str(e), "upload_failed")


def main():
    """MCP server 启动入口，支持 `python -m grsai_server` 和 entry_point `grsai-server`。"""
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    import argparse
    parser = argparse.ArgumentParser(description="GRSAI MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable_http"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    from .config import validate_config
    _cfg_result = validate_config()
    if not _cfg_result["valid"]:
        print("=" * 60, file=sys.stderr)
        print("WARNING: GRSAI config validation - some config missing", file=sys.stderr)
        for item in _cfg_result["missing"]:
            print(f"   - {item}", file=sys.stderr)
        print(f"   config source: {_cfg_result['config_source']}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    run_kwargs = {"transport": args.transport}
    if args.transport == "streamable_http":
        run_kwargs["host"] = args.host
        run_kwargs["port"] = args.port
    mcp.run(**run_kwargs)


if __name__ == "__main__":
    main()
