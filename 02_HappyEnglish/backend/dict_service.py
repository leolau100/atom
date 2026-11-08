"""
词典服务 — 用通义千问查询单词的音标和中文释义。
针对小学生，释义尽量简单易懂。
结果内存缓存，同一单词不重复请求。
"""
import json
import os
import re
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("未找到 DASHSCOPE_API_KEY")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _client


_SYSTEM = """You are an English dictionary for Chinese primary school students (ages 6-12).
Given an English word, return a JSON object with these fields:
- "word": the base form of the word (lowercase)
- "phonetic": IPA phonetic symbol, e.g. /hɛloʊ/
- "pos": part of speech in Chinese, e.g. 名词、动词、形容词、副词、代词、介词、连词
- "meanings": array of objects, each with:
    - "cn": simple Chinese meaning (1-6 characters, easy for kids)
    - "example": one short English example sentence using this word

Return ONLY the JSON object, no explanation, no markdown.

Example output for "happy":
{"word":"happy","phonetic":"/ˈhæpi/","pos":"形容词","meanings":[{"cn":"高兴的，快乐的","example":"I am very happy today."}]}"""


@lru_cache(maxsize=500)
def lookup_word(word: str) -> dict:
    """
    查询单词信息，结果 LRU 缓存（最多 500 个词）。
    返回 dict: { word, phonetic, pos, meanings: [{cn, example}] }
    出错时返回最简占位数据。
    """
    clean = re.sub(r"[^a-zA-Z'-]", "", word).strip().lower()
    if not clean:
        return _fallback(word)

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="qwen-turbo",          # 查词用轻量模型，速度快、省 token
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": clean},
            ],
            max_tokens=256,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()

        # 去 markdown 代码块
        raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        data = json.loads(raw)
        # 保证字段完整
        data.setdefault("word", clean)
        data.setdefault("phonetic", "")
        data.setdefault("pos", "")
        data.setdefault("meanings", [])
        return data

    except Exception as e:
        print(f"[dict] 查词失败 '{clean}': {e}")
        return _fallback(clean)


def _fallback(word: str) -> dict:
    return {
        "word": word.lower(),
        "phonetic": "",
        "pos": "",
        "meanings": [],
    }
