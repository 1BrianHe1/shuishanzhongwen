import os
import json
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

from .generator import _db  # 假设在同一模块或导入

router = APIRouter()

# 通用响应模型基础（可扩展）
class BaseExerciseResp(BaseModel):
    exercise_id: str
    skill: str
    format: str
    title: str
    stem_text: str
    lang: str
    hsk_level: int
    difficulty: int
    points: float
    # 可以添加更多通用字段，如created_at

# 1. picture_tf 查询接口 (听录音看图判断)
class PictureTFReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class PictureTFDetailResp(BaseModel):
    correct_is_true: bool
    explanation: Optional[str]
    transcript_text: Optional[str]
    core_keyword: Optional[str]

class PictureTFResp(BaseModel):
    exercises: List[Dict[str, Any]]  # {base + detail + assets}

@router.post("/api/query/picture_tf", response_model=PictureTFResp)
def query_picture_tf(body: PictureTFReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 查询 exercise + tf_detail + assets (简化：先查主表，再关联)
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        tf.correct_is_true, tf.explanation, tf.transcript_text, tf.core_keyword,
                        jsonb_agg(jsonb_build_object(
                            'asset_id', ea.asset_id,
                            'role', ea.role,
                            'position', ea.position,
                            'url', a.url,
                            'media_kind', a.media_kind
                        )) as assets
                    FROM content.exercise e
                    LEFT JOIN content.exercise_tf_detail tf ON e.id = tf.exercise_id
                    LEFT JOIN content.exercise_asset ea ON e.id = ea.exercise_id
                    LEFT JOIN content.asset a ON ea.asset_id = a.id
                    WHERE e.format = 'picture_tf'
                    GROUP BY e.id, tf.correct_is_true, tf.explanation, tf.transcript_text, tf.core_keyword
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = []
                for row in rows:
                    exercise_data = dict(row)
                    exercise_data['assets'] = exercise_data.get('assets', [])
                    exercises.append(exercise_data)
                
                return PictureTFResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 2. picture_choice 查询接口 (听录音看图选择)
class PictureChoiceReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class PictureChoiceOptionResp(BaseModel):
    option_id: str
    label: str
    text: str
    is_correct: bool
    image_url: Optional[str]  # 关联的option_image

class PictureChoiceResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/picture_choice", response_model=PictureChoiceResp)
def query_picture_choice(body: PictureChoiceReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 复杂查询：exercise + options + answer_key + assets (audio + option_images)
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        jsonb_agg(DISTINCT jsonb_build_object(
                            'asset_id', ea.asset_id, 'role', ea.role, 'position', ea.position,
                            'url', a.url, 'media_kind', a.media_kind
                        )) FILTER (WHERE ea.role = 'audio' OR ea.role = 'stem_image') as general_assets,
                        json_agg(jsonb_build_object(
                            'option_id', o.id, 'label', o.label, 'text', o.text,
                            'is_correct', ak.is_correct,
                            'image_url', COALESCE(img_a.url, NULL)
                        )) as options
                    FROM content.exercise e
                    LEFT JOIN content.option o ON e.id = o.exercise_id
                    LEFT JOIN content.answer_key ak ON o.id = ak.option_id AND ak.is_correct = TRUE
                    LEFT JOIN content.exercise_asset ea ON e.id = ea.exercise_id
                    LEFT JOIN content.asset a ON ea.asset_id = a.id
                    LEFT JOIN content.exercise_asset img_ea ON e.id = img_ea.exercise_id AND img_ea.option_id = o.id AND img_ea.role = 'option_image'
                    LEFT JOIN content.asset img_a ON img_ea.asset_id = img_a.id
                    WHERE e.format = 'picture_choice'
                    GROUP BY e.id
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = [dict(row) for row in rows]
                for ex in exercises:
                    ex['general_assets'] = ex.get('general_assets', [])
                    ex['options'] = ex.get('options', [])
                
                return PictureChoiceResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 3. sentence_choice 查询接口 (句子理解·单选)
class SentenceChoiceReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class SentenceChoiceOptionResp(BaseModel):
    option_id: str
    label: str
    text: str
    is_correct: bool

class SentenceChoiceResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/sentence_choice", response_model=SentenceChoiceResp)
def query_sentence_choice(body: SentenceChoiceReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        ld.transcript_text as generated_text,
                        json_agg(jsonb_build_object(
                            'option_id', o.id, 'label', o.label, 'text', o.text,
                            'is_correct', ak.is_correct
                        )) as options
                    FROM content.exercise e
                    LEFT JOIN content.listening_detail ld ON e.id = ld.exercise_id
                    LEFT JOIN content.option o ON e.id = o.exercise_id
                    LEFT JOIN content.answer_key ak ON o.id = ak.option_id AND ak.is_correct = TRUE
                    WHERE e.format = 'sentence_choice'
                    GROUP BY e.id, ld.transcript_text
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = []
                for row in rows:
                    exercise_data = dict(row)
                    exercise_data['options'] = exercise_data.get('options', [])
                    exercises.append(exercise_data)
                
                return SentenceChoiceResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 4. dialog_ordering 查询接口 (对话排序)
class DialogOrderingReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class DialogOrderingItemResp(BaseModel):
    item_id: str
    text: str
    correct_position: int

class DialogOrderingResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/dialog_ordering", response_model=DialogOrderingResp)
def query_dialog_ordering(body: DialogOrderingReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        json_agg(jsonb_build_object(
                            'item_id', oi.id, 'text', oi.text, 'correct_position', oi.correct_position
                        ) ORDER BY oi.correct_position) as items
                    FROM content.exercise e
                    LEFT JOIN content.ordering_item oi ON e.id = oi.exercise_id
                    WHERE e.format = 'dialog_ordering'
                    GROUP BY e.id
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = [dict(row) for row in rows]
                for ex in exercises:
                    ex['items'] = ex.get('items', [])
                
                return DialogOrderingResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 5. paragraph_choice 查询接口 (阅读理解·单选，包含passage)
class ParagraphChoiceReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class ParagraphChoiceOptionResp(BaseModel):
    option_id: str
    label: str
    text: str
    is_correct: bool

class ParagraphChoiceResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/paragraph_choice", response_model=ParagraphChoiceResp)
def query_paragraph_choice(body: ParagraphChoiceReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 注意：对于bundle，context_exercise_id指向passage载体，这里简化查询单个question exercise
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        pd.passage_title, pd.passage_text,
                        json_agg(jsonb_build_object(
                            'option_id', o.id, 'label', o.label, 'text', o.text,
                            'is_correct', ak.is_correct
                        )) as options
                    FROM content.exercise e
                    LEFT JOIN content.passage_detail pd ON e.extra->>'context_exercise_id' = pd.exercise_id::text  -- 假设extra存储context_id
                    LEFT JOIN content.option o ON e.id = o.exercise_id
                    LEFT JOIN content.answer_key ak ON o.id = ak.option_id AND ak.is_correct = TRUE
                    WHERE e.format = 'paragraph_choice'
                    GROUP BY e.id, pd.passage_title, pd.passage_text
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = []
                for row in rows:
                    exercise_data = dict(row)
                    exercise_data['options'] = exercise_data.get('options', [])
                    exercises.append(exercise_data)
                
                return ParagraphChoiceResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 6. pinyin_cloze 查询接口 (拼音填空)
class PinyinClozeReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class PinyinClozeBlankResp(BaseModel):
    blank_index: int
    answer: str
    alt_answers: Optional[List[str]]

class PinyinClozeResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/pinyin_cloze", response_model=PinyinClozeResp)
def query_pinyin_cloze(body: PinyinClozeReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        cd.cloze_text,
                        json_agg(jsonb_build_object(
                            'blank_index', cb.blank_index, 'answer', cb.answer, 
                            'alt_answers', cb.alt_answers
                        ) ORDER BY cb.blank_index) as blanks
                    FROM content.exercise e
                    LEFT JOIN content.cloze_detail cd ON e.id = cd.exercise_id
                    LEFT JOIN content.cloze_blank cb ON e.id = cb.exercise_id
                    WHERE e.format = 'pinyin_cloze'
                    GROUP BY e.id, cd.cloze_text
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = [dict(row) for row in rows]
                for ex in exercises:
                    ex['blanks'] = ex.get('blanks', [])
                
                return PinyinClozeResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 7. keyword_essay 查询接口 (写作/作文)
class KeywordEssayReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class KeywordEssayResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/keyword_essay", response_model=KeywordEssayResp)
def query_keyword_essay(body: KeywordEssayReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        wd.prompt_text, wd.required_keys, wd.min_words, wd.max_words, wd.rubric
                    FROM content.exercise e
                    LEFT JOIN content.writing_detail wd ON e.id = wd.exercise_id
                    WHERE e.format = 'keyword_essay'
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = [dict(row) for row in rows]
                
                return KeywordEssayResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# 8. picture_keyword_essay 查询接口 (看图用词造句)
class PictureKeywordEssayReq(BaseModel):
    num: str = Field("10", description="查询条数，如 '10' 或 'all'")

class PictureKeywordEssayResp(BaseModel):
    exercises: List[Dict[str, Any]]

@router.post("/api/query/picture_keyword_essay", response_model=PictureKeywordEssayResp)
def query_picture_keyword_essay(body: PictureKeywordEssayReq):
    limit = "ALL" if body.num.lower() == "all" else int(body.num)
    if limit != "ALL" and (not isinstance(limit, int) or limit < 1):
        raise HTTPException(status_code=400, detail="num 必须是正整数或 'all'")
    
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e.id as exercise_id, e.skill, e.format, e.title, e.stem_text, 
                        e.lang, e.hsk_level, e.difficulty, e.points,
                        wd.prompt_text, wd.required_keys,
                        jsonb_agg(jsonb_build_object(
                            'asset_id', ea.asset_id, 'role', ea.role, 'position', ea.position,
                            'url', a.url, 'media_kind', a.media_kind
                        )) as assets
                    FROM content.exercise e
                    LEFT JOIN content.writing_detail wd ON e.id = wd.exercise_id
                    LEFT JOIN content.exercise_asset ea ON e.id = ea.exercise_id
                    LEFT JOIN content.asset a ON ea.asset_id = a.id
                    WHERE e.format = 'picture_keyword_essay'
                    GROUP BY e.id, wd.prompt_text, wd.required_keys
                    ORDER BY e.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                
                exercises = []
                for row in rows:
                    exercise_data = dict(row)
                    exercise_data['assets'] = exercise_data.get('assets', [])
                    exercises.append(exercise_data)
                
                return PictureKeywordEssayResp(exercises=exercises)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")