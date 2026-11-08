"""
Happy English - Backend API
FastAPI 服务，提供 OCR 识别、TTS 朗读、历史记录管理功能。
"""
import os
import uuid
from datetime import datetime
from typing import List, Optional

import aiofiles
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db
from models import Record
from ocr_service import extract_sentences_from_image, parse_words
from tts_service import text_to_speech
from dict_service import lookup_word

# ── 初始化 ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Happy English API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 开发阶段全放通，生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
async def startup():
    init_db()
    print("✅ Happy English API 启动成功")


# ── Pydantic Schemas ────────────────────────────────────────────────────────

class SentenceItem(BaseModel):
    id: int
    text: str
    words: List[str]


class OCRResponse(BaseModel):
    raw_text: str
    sentences: List[SentenceItem]


class SaveRecordRequest(BaseModel):
    raw_text: str
    sentences: List[str]          # 用户确认/修改后的句子列表
    title: Optional[str] = None
    image_path: Optional[str] = None


class RecordResponse(BaseModel):
    id: int
    title: str
    raw_text: str
    sentences: List[SentenceItem]
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateSentencesRequest(BaseModel):
    sentences: List[str]


# ── Helper ──────────────────────────────────────────────────────────────────

def build_sentence_items(sentence_list: List[str]) -> List[SentenceItem]:
    return [
        SentenceItem(id=i, text=s, words=parse_words(s))
        for i, s in enumerate(sentence_list)
    ]


def record_to_response(record: Record) -> RecordResponse:
    return RecordResponse(
        id=record.id,
        title=record.title,
        raw_text=record.raw_text,
        sentences=build_sentence_items(record.sentences),
        created_at=record.created_at,
    )


# ── OCR 接口 ────────────────────────────────────────────────────────────────

@app.post("/api/ocr", response_model=OCRResponse, summary="上传图片进行 OCR 识别")
async def ocr_image(file: UploadFile = File(...)):
    """
    接收图片文件，返回识别的原始文本和分句结果。
    支持 jpg / png / webp 等常见格式。
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB 限制
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    try:
        raw_text, sentences = extract_sentences_from_image(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败：{str(e)}")

    if not sentences:
        raise HTTPException(status_code=422, detail="未能识别到英文内容，请换一张图片")

    return OCRResponse(
        raw_text=raw_text,
        sentences=build_sentence_items(sentences),
    )


# ── TTS 接口 ────────────────────────────────────────────────────────────────

@app.get("/api/tts", summary="文本转语音")
async def tts(text: str, speed: int = 1):
    """
    将文本转换为 MP3 语音。
    - text: 要朗读的文本（句子或单词）
    - speed: 0=超慢速, 1=慢速(默认), 2=正常速度
    返回 audio/mpeg 流。
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="文本过长，请控制在 500 字符以内")
    if speed not in (0, 1, 2):
        speed = 1

    audio_bytes = await text_to_speech(text, speed=speed)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": "inline",
        }
    )


# ── 记录管理接口 ────────────────────────────────────────────────────────────

@app.post("/api/records", response_model=RecordResponse, summary="保存识别记录")
async def save_record(request: SaveRecordRequest, db: Session = Depends(get_db)):
    """保存一次识别记录（用户确认句子后调用）"""
    if not request.sentences:
        raise HTTPException(status_code=400, detail="句子列表不能为空")

    # 自动生成标题：取前 30 个字符
    title = request.title or (request.raw_text[:30] + "..." if len(request.raw_text) > 30 else request.raw_text)

    record = Record(
        title=title,
        raw_text=request.raw_text,
        sentences=request.sentences,
        image_path=request.image_path,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record_to_response(record)


@app.get("/api/records", response_model=List[RecordResponse], summary="获取历史记录列表")
async def list_records(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """分页获取历史记录，按时间倒序"""
    records = (
        db.query(Record)
        .order_by(Record.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [record_to_response(r) for r in records]


@app.get("/api/records/{record_id}", response_model=RecordResponse, summary="获取单条记录")
async def get_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record_to_response(record)


@app.put("/api/records/{record_id}/sentences", response_model=RecordResponse, summary="更新记录的句子")
async def update_sentences(
    record_id: int,
    request: UpdateSentencesRequest,
    db: Session = Depends(get_db)
):
    """用户手动编辑句子后更新"""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    record.sentences = request.sentences
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record_to_response(record)


@app.delete("/api/records/{record_id}", summary="删除记录")
async def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(record)
    db.commit()
    return {"message": "删除成功"}


# ── 词典接口 ────────────────────────────────────────────────────────────────

class WordMeaning(BaseModel):
    cn: str
    example: str

class DictResponse(BaseModel):
    word: str
    phonetic: str
    pos: str
    meanings: List[WordMeaning]

@app.get("/api/dict/{word}", response_model=DictResponse, summary="查询单词音标和释义")
async def dict_lookup(word: str):
    """查询单词的音标、词性、中文释义和例句"""
    word = word.strip()
    if not word or len(word) > 50:
        raise HTTPException(status_code=400, detail="无效的单词")
    result = lookup_word(word)
    return DictResponse(
        word=result.get("word", word),
        phonetic=result.get("phonetic", ""),
        pos=result.get("pos", ""),
        meanings=[
            WordMeaning(cn=m.get("cn", ""), example=m.get("example", ""))
            for m in result.get("meanings", [])
        ],
    )


# ── 健康检查 ────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Happy English API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
