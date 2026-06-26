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

    if not os.path.isfile(voice_ref):
        return {"error": f"音色参考音频不存在: {voice_ref}"}

    output_dir = output_dir or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)
    base_name = "".join(c for c in text[:20] if c.isalnum() or c in " _-") or "tts"
    output_path = os.path.join(output_dir, f"{base_name}.wav")

    kwargs = {}
    if emotion:
        kwargs["use_emo_text"] = True
        kwargs["emo_text"] = emotion

    try:
        result = tts.infer(
            spk_audio_prompt=voice_ref,
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
