#!/usr/bin/env python3
# DEPRECATED: 此文件已被 .opencode/mcp-servers/grsai-server/ 中的对应模块替代。
# 图像生成 API → grsai_client.py
# COS 上传 → cos_client.py
# 凭证管理 → config.py
# 批量生成 → grsai_batch_generate MCP tool
# 将在后续版本删除。
"""
纯 LLM API 封装 — 仅做一件事：对接外部 LLM。

三种模式:
  1) --build-request  : 接收 --system / --user 文本，写出 request.json
  2) --input / --output: 单次调用，读取 request.json → 写出 response.json
  3) --batch-dir       : 并发模式，扫描子目录下所有 request.json → 同目录写 response.json

pipeline-dir:
  所有模式均可附加 --pipeline-dir <目录>，作为输入/输出的基准路径（方便 Agent 统一管理）。
"""

import json, os, sys, time, random, urllib.error, urllib.request
from pathlib import Path

DEFAULT_HOST = "https://grsai.dakka.com.cn"
DEFAULT_MODEL = "gemini-3.1-pro"
MAX_RETRIES = 3
TIMEOUT = 300
CONFIG_FILE = Path.home() / ".trae-cn" / "media_gen_config.json"


def _cfg(key: str) -> str:
    v = os.environ.get(key, "").strip()
    if v:
        return v
    try:
        return str(json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get(key, ""))
    except Exception:
        return ""


def call(messages: list, model: str = None, temperature: float = 0.7) -> dict:
    api_key = _cfg("GRSAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GRSAI_API_KEY：请设置环境变量或 ~/.trae-cn/media_gen_config.json")

    host = _cfg("GRSAI_API_HOST") or DEFAULT_HOST
    model = model or _cfg("GRSAI_LLM_MODEL") or DEFAULT_MODEL

    body = {"model": model, "stream": False, "messages": messages, "temperature": temperature}
    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            return {
                "content": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"),
                "usage": data.get("usage", {}),
            }
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise RuntimeError(f"认证失败 (HTTP {e.code}): {body[:300]}")
            if e.code == 400 and ("context_length" in body.lower() or "token" in body.lower()):
                raise RuntimeError(f"上下文超长 (HTTP 400): {body[:300]}")
            if e.code == 400:
                raise RuntimeError(f"请求参数错误 (HTTP 400): {body[:300]}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"API 失败 (HTTP {e.code}, 已重试{MAX_RETRIES}次): {body[:300]}")
        except urllib.error.URLError as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"网络错误 (已重试{MAX_RETRIES}次): {e.reason}")
        wait = min(2 ** attempt, 60) * (0.5 + random.random())
        print(f"  \u26a0 \u7b2c{attempt}\u6b21\u5931\u8d25\uff0c{wait:.1f}s\u540e\u91cd\u8bd5...", file=sys.stderr)
        time.sleep(wait)

    raise RuntimeError("不可达状态")


def write_request(system_prompt: str, user_content: str, output_path: str):
    """构建并写出 request.json"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)
    print(f"  \u2714 {output_path}")


def process_request(req_path: Path, model: str = None, temperature: float = 0.7) -> tuple:
    """读取 request.json → 调用 LLM → 写出同目录 response.json"""
    req_data = json.loads(req_path.read_text(encoding="utf-8"))
    messages = req_data.get("messages", req_data)
    result = call(messages, model, temperature)
    resp_path = req_path.parent / "response.json"
    resp_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return req_path.name, result.get("finish_reason", "?"), result.get("usage", {}).get("total_tokens", "?")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="纯 LLM API 封装")
    parser.add_argument("--build-request", action="store_true", help="构建 request.json 模式")
    parser.add_argument("--system", help="System Prompt 文本")
    parser.add_argument("--user", help="User Message 文本")
    parser.add_argument("--input", help="request.json 路径")
    parser.add_argument("--output", help="response.json 输出路径")
    parser.add_argument("--model", help="覆盖模型名")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--batch-dir", help="批量并发模式：目录路径，扫描其中所有子目录下的 request.json")
    parser.add_argument("--pipeline-dir", help="pipeline 基准目录，用于拼接 input/output/batch-dir")
    args = parser.parse_args()

    # pipeline-dir 拼接辅助
    if args.pipeline_dir:
        pdir = Path(args.pipeline_dir)
        if args.build_request and not args.output:
            args.output = str(pdir / "01_request.json")
        if args.input and not Path(args.input).is_absolute():
            args.input = str(pdir / args.input)
        if args.output and not Path(args.output).is_absolute():
            args.output = str(pdir / args.output)
        if args.batch_dir and not Path(args.batch_dir).is_absolute():
            args.batch_dir = str(pdir / args.batch_dir)

    # ─── --build-request 模式 ──────────────────────────
    if args.build_request:
        if not args.system or not args.user:
            parser.error("--build-request 需要 --system 和 --user 参数")
        out = args.output or "request.json"
        write_request(args.system, args.user, out)
        sys.exit(0)

    # ─── --batch-dir 并发模式 ──────────────────────────
    if args.batch_dir:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        batch_dir = Path(args.batch_dir)
        request_files = sorted(batch_dir.rglob("request.json"))
        if not request_files:
            print(f"\u274c \u672a\u627e\u5230 request.json \u6587\u4ef6", file=sys.stderr)
            sys.exit(1)

        print(f"  并发处理 {len(request_files)} 个分片...")

        with ThreadPoolExecutor(max_workers=min(len(request_files), 5)) as pool:
            futures = [pool.submit(process_request, p, args.model, args.temperature) for p in request_files]
            for future in as_completed(futures):
                name, reason, tokens = future.result()
                print(f"  \u2705 {name}: {reason} | {tokens} tokens")

        print(f"  \u2705 \u6279\u91cf\u5b8c\u6210\uff0c\u54cd\u5e94\u6587\u4ef6\u5df2\u5199\u5165 {batch_dir}")
        sys.exit(0)

    # ─── 单次调用模式 ──────────────────────────────────
    if not args.input or not args.output:
        parser.print_help()
        sys.exit(1)

    result = process_request(Path(args.input), args.model, args.temperature)
    print(f"\u2705 {result[1]} | tokens: {result[2]}")