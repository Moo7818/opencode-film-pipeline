#!/usr/bin/env python3
"""GRSAI 统一 MCP Server

提供以下工具：
- grsai_health_check: 检查 API 连通性和凭证有效性
- grsai_call_llm: 调用 GRSAI LLM API（Phase 2 实现）
- grsai_generate_image: 调用 GRSAI 图像生成 API（Phase 3 实现）
- grsai_batch_generate: 批量图像生成（Phase 3 实现）
- grsai_upload_cos: 腾讯云 COS 上传（Phase 3 实现）
"""

import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


server = Server("grsai")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="grsai_health_check",
            description="检查 GRSAI API 连通性和凭证有效性",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="grsai_call_llm",
            description="调用 GRSAI LLM API，支持 3 次指数退避重试",
            inputSchema={
                "type": "object",
                "required": ["messages"],
                "properties": {
                    "messages": {
                        "type": "array",
                        "description": "对话消息列表",
                        "items": {
                            "type": "object",
                            "required": ["role", "content"],
                            "properties": {
                                "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                "content": {"type": "string"},
                            },
                        },
                    },
                    "model": {
                        "type": "string",
                        "description": "模型名，如 gemini-3.1-pro",
                        "default": "gemini-3.1-pro",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "温度",
                        "default": 0.7,
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "最大 token 数（可选）",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "请求超时秒数",
                        "default": 300,
                    },
                },
            },
        ),
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
                    "oss_id": {"type": "string", "description": "OSS 存储桶 ID（默认从 credentials.json 读取）"},
                    "oss_path": {"type": "string", "description": "OSS 文件路径（默认从 credentials.json 读取）"},
                    "poll_delay": {"type": "integer", "default": 14, "description": "首次轮询等待秒数"},
                    "poll_interval": {"type": "integer", "default": 5, "description": "轮询间隔秒数"},
                    "max_poll_rounds": {"type": "integer", "default": 60, "description": "最大轮询次数"},
                },
            },
        ),
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
                    "output_dir": {"type": "string", "default": "./output"},
                    "concurrency": {"type": "integer", "default": 10},
                    "batch_type": {"type": "string", "enum": ["character_reference", "storyboard", "other"]},
                },
            },
        ),
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "grsai_health_check":
        from config import _cfg, CFG_API_KEY, CFG_HOST, CFG_COS_ID, CFG_COS_KEY, CFG_COS_BUCKET, CFG_COS_REGION, DEFAULT_HOST

        api_key = _cfg(CFG_API_KEY)
        host = _cfg(CFG_HOST) or DEFAULT_HOST
        cos_configured = all([
            _cfg(CFG_COS_ID),
            _cfg(CFG_COS_KEY),
            _cfg(CFG_COS_BUCKET),
            _cfg(CFG_COS_REGION),
        ])

        result = {
            "api_key_valid": bool(api_key),
            "host": host,
            "cos_configured": cos_configured,
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    elif name == "grsai_call_llm":
        from grsai_client import call_llm
        try:
            result = call_llm(
                messages=arguments["messages"],
                model=arguments.get("model"),
                temperature=arguments.get("temperature", 0.7),
                max_tokens=arguments.get("max_tokens"),
                timeout=arguments.get("timeout", 300),
            )
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        except RuntimeError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]

    elif name == "grsai_generate_image":
        from grsai_client import generate_image
        from config import load_cos_config, _cfg, CFG_OSS_ID, CFG_OSS_PATH
        try:
            result = generate_image(
                prompt=arguments["prompt"],
                model=arguments["model"],
                aspect_ratio=arguments.get("aspect_ratio"),
                image_size=arguments.get("image_size"),
                reference_images=arguments.get("reference_images"),
                oss_id=arguments.get("oss_id") or _cfg(CFG_OSS_ID),
                oss_path=arguments.get("oss_path") or _cfg(CFG_OSS_PATH),
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
            output_dir = arguments.get("output_dir", "./output")
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

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
