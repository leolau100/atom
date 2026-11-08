"""
OCR Service — 使用通义千问 VL 视觉模型识别图片中的英文文本并分句。
图片 → qwen-vl-max → 直接返回干净的句子列表，无需本地 OCR。
"""
import base64
import json
import os
import re
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 通义千问 API 配置（兼容 OpenAI SDK）
_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("未找到 DASHSCOPE_API_KEY，请检查 .env 文件")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _client


# 给 AI 的提示词
_SYSTEM_PROMPT = """You are an English text extraction assistant for primary school students.
Your job is to extract English text from images and split it into complete sentences.

Rules:
1. Extract ALL English text visible in the image
2. Fix obvious OCR errors (e.g. "l" mistaken for "1", "O" for "0")
3. Split the text into complete, meaningful sentences
4. Each sentence must be grammatically complete — do NOT cut a sentence in the middle
5. Remove page numbers, headers, footnotes, or irrelevant labels
6. Return ONLY a JSON array of sentence strings, nothing else

Example output:
["The cat sat on the mat.", "She went to school every day.", "It was a sunny morning."]
"""

_USER_PROMPT = """Please extract all English sentences from this image.
Return a JSON array only, no explanation."""


def extract_sentences_from_image(image_bytes: bytes) -> Tuple[str, List[str]]:
    """
    调用通义千问 VL 识别图片，直接返回：
    - raw_text: 所有句子拼接的原始文本
    - sentences: 干净的句子列表
    """
    client = get_client()

    # 图片转 base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    # 推断 MIME 类型（简单判断文件头）
    mime = _detect_mime(image_bytes)

    response = client.chat.completions.create(
        model="qwen-vl-max",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}"
                        },
                    },
                    {"type": "text", "text": _USER_PROMPT},
                ],
            },
        ],
        max_tokens=2048,
    )

    content = response.choices[0].message.content.strip()
    sentences = _parse_sentences(content)
    raw_text = " ".join(sentences)
    return raw_text, sentences


def _detect_mime(image_bytes: bytes) -> str:
    """根据文件头简单判断图片格式"""
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"  # 默认


def _parse_sentences(content: str) -> List[str]:
    """
    解析 AI 返回的内容，提取句子列表。
    兼容以下情况：
    1. 纯 JSON 数组：["S1", "S2"]
    2. Markdown 代码块包裹：```json\n["S1"]\n```
    3. AI 多说了几句话但 JSON 数组在里面
    """
    # 去掉 markdown 代码块
    content = re.sub(r"```(?:json)?\s*", "", content)
    content = content.strip("`").strip()

    # 尝试直接解析
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return [s.strip() for s in result if isinstance(s, str) and s.strip()]
    except json.JSONDecodeError:
        pass

    # 从文本中找 JSON 数组片段
    match = re.search(r"\[.*?\]", content, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return [s.strip() for s in result if isinstance(s, str) and s.strip()]
        except json.JSONDecodeError:
            pass

    # 兜底：按行分割，每行当一个句子
    lines = [l.strip().strip('"').strip("'") for l in content.splitlines() if l.strip()]
    return [l for l in lines if len(l) > 3]


# ── 兼容旧接口，main.py 不需要改 ──────────────────────────────────────────

def extract_text_from_image(image_bytes: bytes) -> str:
    """兼容旧调用：返回原始文本"""
    raw_text, _ = extract_sentences_from_image(image_bytes)
    return raw_text


def split_into_sentences(text: str) -> List[str]:
    """
    兼容旧调用：text 是 extract_text_from_image 的返回值。
    AI 方案下，句子已经在 extract_sentences_from_image 里拿到了。
    这里做一个简单的兜底分割（实际不会走到这里）。
    """
    if not text.strip():
        return []
    # 按句号、感叹号、问号分割兜底
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_words(sentence: str) -> List[str]:
    """将句子拆分成单词列表"""
    return sentence.split()
