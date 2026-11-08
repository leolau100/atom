from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Record(Base):
    """每次 OCR 识别的记录"""
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, default="")  # 自动取前 20 字或手动命名
    raw_text = Column(Text, nullable=False)                  # OCR 识别的原始文本
    sentences = Column(JSON, nullable=False)                 # 分解后的句子列表
    image_path = Column(String(500), nullable=True)          # 原始图片路径（可选）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
