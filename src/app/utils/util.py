import os
import psycopg2
from pypinyin import lazy_pinyin,Style
import jieba
from typing import List

DATABASE_URL = os.getenv("DATABASE_URL")

def _db():
    return psycopg2.connect(DATABASE_URL)


def to_pinyin_sentence(text: str) -> str:
    """将一个中文字符串转换为带声调的、以空格分隔的拼音字符串。"""
    if not text:
        return ""
    pinyin_list = lazy_pinyin(text, style=Style.TONE)
    return ' '.join(p for p in pinyin_list if p.strip())

def segment_sentence(sentence: str) -> List[str]:
    words = list(jieba.cut(sentence))
    return words