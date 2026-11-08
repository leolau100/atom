"""
TTS Service — 使用微软 Edge TTS（免费，无需 Key）。
声音：en-US-AnaNeural（儿童女声，自然清晰）
全程 async，直接在 FastAPI event loop 中运行，不需要 asyncio.run()。

speed=0  超慢速：rate="-30%"
speed=1  慢速：  rate="-15%"
speed=2  正常：  rate="+0%"
"""
import io
import re

import edge_tts

VOICE = "en-US-AnaNeural"

SPEED_RATE = {
    0: "-25%",   # 超慢速（-25% 是音色不失真的安全范围）
    1: "-12%",   # 慢速
    2: "+0%",    # 正常
}


async def text_to_speech(text: str, speed: int = 1) -> bytes:
    """异步生成语音，返回 MP3 字节。"""
    if not text or not text.strip():
        raise ValueError("文本不能为空")

    clean = _clean(text)
    rate = SPEED_RATE.get(speed, "-15%")

    comm = edge_tts.Communicate(clean, VOICE, rate=rate)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])

    buf.seek(0)
    data = buf.read()
    if not data:
        raise RuntimeError("Edge TTS 返回空音频，请检查网络连接")
    return data


def _clean(text: str) -> str:
    text = re.sub(r"[^\w\s.,!?'-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
