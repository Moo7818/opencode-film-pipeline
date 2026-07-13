import os
import sys
import threading

from mcp.server.fastmcp import FastMCP

server_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, server_dir)

mcp = FastMCP("indextts-2")

model_dir = os.getenv("TTS_MODEL_DIR", os.path.join(server_dir, ".models"))
cfg_path = os.getenv("TTS_CONFIG_PATH", os.path.join(model_dir, "config.yaml"))
device = os.getenv("TTS_DEVICE", "cpu")

_tts = None
_tts_lock = threading.Lock()
_tts_error = None

# ─── 路径安全 ──────────────────────────────────────────────────
# 允许的根目录白名单：项目根目录和 temp 目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(server_dir)))
_ALLOWED_BASES = [
    _PROJECT_ROOT,
    os.path.join(_PROJECT_ROOT, "temp"),
    os.path.join(_PROJECT_ROOT, "project"),
    os.path.join(os.getcwd(), "temp"),
    os.getcwd(),
]


def _validate_path(path: str, allow_create: bool = False) -> str:
    """校验路径安全性，防止路径遍历攻击

    Args:
        path: 待校验的路径
        allow_create: 是否允许路径不存在（用于 output_dir 场景）

    Returns:
        解析后的绝对路径

    Raises:
        ValueError: 路径不在允许的根目录范围内
    """
    if not path or not path.strip():
        raise ValueError("路径不能为空")

    abs_path = os.path.realpath(os.path.abspath(path))

    # 检查路径是否在允许的根目录范围内
    in_allowed = False
    for base in _ALLOWED_BASES:
        base_abs = os.path.realpath(base)
        if abs_path == base_abs or abs_path.startswith(base_abs + os.sep):
            in_allowed = True
            break

    if not in_allowed:
        raise ValueError(
            f"路径超出允许范围: {abs_path}。"
            f"仅允许在项目目录或 temp 目录下操作。"
        )

    if not allow_create and not os.path.exists(abs_path):
        raise ValueError(f"路径不存在: {abs_path}")

    return abs_path


def _get_tts():
    global _tts, _tts_error
    if _tts is not None:
        return _tts
    with _tts_lock:
        if _tts is not None:
            return _tts
        try:
            from indextts.infer_v2 import IndexTTS2
            _tts = IndexTTS2(
                model_dir=model_dir,
                cfg_path=cfg_path,
                is_fp16=False,
                device=device,
            )
            _tts_error = None
        except Exception as e:
            _tts_error = str(e)
            raise
    return _tts


@mcp.tool()
def tts_synthesize(
    text: str,
    voice_ref: str,
    output_dir: str = "",
    emotion: str = "",
) -> dict:
    """将文本合成为语音，支持声音克隆

    Args:
        text: 要合成的文本内容
        voice_ref: 音色参考音频路径（.wav 文件）
        output_dir: 输出目录（默认为当前目录）
        emotion: 情感描述（如"高兴""悲伤"等；留空为与参考音频一致）

    Returns:
        {"output_path": "...", "message": "..."}
    """
    try:
        tts = _get_tts()
    except Exception as e:
        return {"error": f"模型加载失败: {e}"}

    # 路径安全校验
    try:
        voice_ref_safe = _validate_path(voice_ref)
    except ValueError as e:
        return {"error": str(e)}

    if not os.path.isfile(voice_ref_safe):
        return {"error": f"音色参考音频不存在: {voice_ref}"}

    try:
        output_dir_resolved = output_dir or os.getcwd()
        output_dir_safe = _validate_path(output_dir_resolved, allow_create=True)
    except ValueError as e:
        return {"error": str(e)}

    os.makedirs(output_dir_safe, exist_ok=True)

    # 输出文件名增加时间戳避免覆盖
    import time
    base_name = "".join(c for c in text[:20] if c.isalnum() or c in " _-") or "tts"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir_safe, f"{base_name}_{timestamp}.wav")

    kwargs = {}
    if emotion:
        kwargs["use_emo_text"] = True
        kwargs["emo_text"] = emotion

    try:
        result = tts.infer(
            spk_audio_prompt=voice_ref_safe,
            text=text,
            output_path=output_path,
            **kwargs,
        )
        return {"output_path": result, "message": "success"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def tts_health() -> dict:
    """检查 TTS 引擎状态"""
    status = "loading" if _tts is None and _tts_error is None else "unhealthy" if _tts_error else "healthy"
    return {
        "status": status,
        "model_loaded": _tts is not None,
        "model_dir": model_dir,
        "device": device,
        "error": _tts_error or "",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
