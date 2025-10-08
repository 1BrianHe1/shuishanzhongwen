# app/routers/questions.py
import uuid
import random
import json
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
try:
    from app.schemas import QuestionRequest, QuestionResponse, Question, QuestionContent
    from app.database import get_db
except ImportError:
    # 用于测试环境的导入
    from schemas import QuestionRequest, QuestionResponse, Question, QuestionContent
    def get_db():
        return None

router = APIRouter()

def get_exercise_types_from_db(db: Session) -> Dict[str, Dict]:
    """从数据库获取题目类型"""
    try:
        result = db.execute(text("""
            SELECT et.name, et.display_name, et.description, sc.name as skill_category
            FROM content_new.exercise_types et
            JOIN content_new.skill_categories sc ON et.skill_category_id = sc.id
            ORDER BY et.display_order
        """))

        types = result.fetchall()

        # 构建题目类型映射
        type_mapping = {}
        for t in types:
            type_mapping[t.name] = {
                "name": t.display_name,
                "description": t.description,
                "skill_category": t.skill_category,
                "requires_audio": "LISTEN" in t.name,
                "requires_image": "IMAGE" in t.name,
                "has_options": "MC" in t.name or "TRUE_FALSE" in t.name
            }

        return type_mapping
    except Exception as e:
        print(f"获取题目类型失败: {e}")
        # 如果数据库出错，返回空字典
        return {}

# 旧的通用函数已删除，现在使用专门的接口处理

# 所有题目类型和数据都从数据库获取


# 专门的LISTEN_IMAGE_TRUE_FALSE题目请求模型
from pydantic import BaseModel

class ListenImageTrueFalseRequest(BaseModel):
    count: int = 1  # 题目数量，默认1题
    userId: Optional[str] = None  # 用户ID
    token: Optional[str] = None  # 用户token
    phaseName: Optional[str] = None  # 阶段名称
    topicName: Optional[str] = None  # 主题名称
    lessonName: Optional[str] = None  # 课程名称

# 简化的题目内容模型
class SimpleQuestionContent(BaseModel):
    question: str  # 问题文本
    audioUrl: Optional[str] = None  # 音频URL
    imageUrl: Optional[str] = None  # 图片URL
    listeningText: Optional[str] = None  # 听力文本

# 简化的题目模型
class SimpleQuestion(BaseModel):
    questionId: str  # 题目ID（对应exercise_id）
    questionType: str  # 题目类型
    content: SimpleQuestionContent  # 题目内容
    correctAnswer: Optional[int] = None  # 正确答案

class ListenImageTrueFalseResponse(BaseModel):
    count: int  # 实际题目数量
    sessionId: str  # 会话标识
    questions: List[SimpleQuestion]  # 题目列表

@router.post(
    "/api/questions/listen-image-true-false",
    response_model=ListenImageTrueFalseResponse,
    tags=["Questions"]
)
async def generate_listen_image_true_false_questions(
    req: ListenImageTrueFalseRequest,
    db: Session = Depends(get_db)
):
    """
    生成听录音看图判断题目

    Args:
        req: 题目请求参数
        db: 数据库会话

    Returns:
        ListenImageTrueFalseResponse: 包含生成题目的响应
    """
    try:
        # 检查数据库连接
        if db is None:
            raise HTTPException(
                status_code=500,
                detail="数据库连接不可用"
            )

        # 生成会话ID
        session_id = str(uuid.uuid4())

        # 根据提供的参数选择题目
        if req.lessonName or req.phaseName or req.topicName:
            # 构建动态查询条件
            where_conditions = ["et.name = 'LISTEN_IMAGE_TRUE_FALSE'"]
            params = {"limit": req.count}

            # 添加lesson条件
            if req.lessonName:
                where_conditions.append("l.lesson_name = :lesson_name")
                params["lesson_name"] = req.lessonName

            # 添加phase条件
            if req.phaseName:
                where_conditions.append("p.name = :phase_name")
                params["phase_name"] = req.phaseName

            # 添加topic条件
            if req.topicName:
                where_conditions.append("t.topic_name = :topic_name")
                params["topic_name"] = req.topicName

            where_clause = " AND ".join(where_conditions)

            query = f"""
                SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                       et.name as exercise_type_name, et.display_name as exercise_type_display,
                       w.characters, w.pinyin, w.translation
                FROM content_new.lesson_words lw
                JOIN content_new.lessons l ON lw.lesson_id = l.id
                JOIN content_new.topics t ON l.topic_id = t.id
                JOIN content_new.phases p ON t.phase_id = p.id
                JOIN content_new.words w ON lw.word_id = w.id
                JOIN content_new.exercises e ON w.id = e.word_id
                JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
                WHERE {where_clause}
                ORDER BY RANDOM()
                LIMIT :limit
            """

            result = db.execute(text(query), params)
        else:
            # 如果没有提供lessonName，使用原有逻辑
            result = db.execute(text("""
                SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                       et.name as exercise_type_name, et.display_name as exercise_type_display,
                       w.characters, w.pinyin, w.translation
                FROM content_new.exercises e
                JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
                LEFT JOIN content_new.words w ON e.word_id = w.id
                WHERE et.name = 'LISTEN_IMAGE_TRUE_FALSE'
                ORDER BY RANDOM()
                LIMIT :limit
            """), {"limit": req.count})

        exercises = []
        for row in result:
            exercise = {
                "id": str(row.id),
                "prompt": row.prompt,
                "metadata": row.metadata,
                "difficulty_level": row.difficulty_level,
                "exercise_type_name": row.exercise_type_name,
                "exercise_type_display": row.exercise_type_display,
                "word_characters": row.characters,
                "word_pinyin": row.pinyin,
                "word_translation": row.translation
            }

            # 获取关联的媒体资源
            media_result = db.execute(text("""
                SELECT ma.file_url, ma.file_type, ma.mime_type, ema.usage_role
                FROM content_new.exercise_media_assets ema
                JOIN content_new.media_assets ma ON ema.media_asset_id = ma.id
                WHERE ema.exercise_id = :exercise_id
            """), {"exercise_id": row.id})

            exercise['media_assets'] = []
            for media_row in media_result:
                exercise['media_assets'].append({
                    "file_url": media_row.file_url,
                    "file_type": media_row.file_type,
                    "mime_type": media_row.mime_type,
                    "usage_role": media_row.usage_role
                })

            exercises.append(exercise)

        # 生成题目对象
        questions = []
        for exercise_data in exercises:
            # 使用数据库中的exercise_id作为questionId
            question_id = exercise_data["id"]

            # 解析metadata中的题目数据
            metadata = exercise_data.get('metadata', {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            # 获取媒体资源
            media_assets = exercise_data.get('media_assets', [])
            audio_url = None
            image_url = None

            for asset in media_assets:
                if asset['usage_role'] == 'prompt_audio':
                    audio_url = asset['file_url']
                elif asset['usage_role'] in ['stem_image', 'correct_image']:
                    image_url = asset['file_url']

            # 构建简化的题目内容
            content = SimpleQuestionContent(
                question=exercise_data.get('prompt', ''),
                audioUrl=audio_url,
                imageUrl=image_url,
                listeningText=metadata.get('listening_text')
            )

            # 获取正确答案
            correct_answer = metadata.get('correct_answer')

            question = SimpleQuestion(
                questionId=question_id,
                questionType="LISTEN_IMAGE_TRUE_FALSE",
                content=content,
                correctAnswer=correct_answer
            )
            questions.append(question)

        # 构建响应
        response = ListenImageTrueFalseResponse(
            count=len(questions),
            sessionId=session_id,
            questions=questions
        )

        return response

    except HTTPException:
        # 重新抛出HTTP异常（保持原状态码）
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成LISTEN_IMAGE_TRUE_FALSE题目时发生错误: {str(e)}")

@router.get(
    "/api/questions/types",
    tags=["Questions"]
)
async def get_question_types(db: Session = Depends(get_db)):
    """
    获取支持的题目类型列表
    """
    try:
        # 检查数据库连接
        if db is None:
            raise HTTPException(
                status_code=500,
                detail="数据库连接不可用"
            )

        # 从数据库获取题目类型
        all_types = get_exercise_types_from_db(db)
        if not all_types:
            raise HTTPException(
                status_code=500,
                detail="无法从数据库获取题目类型"
            )

        return {
            "questionTypes": [
                {
                    "type": qtype,
                    "name": config["name"],
                    "requiresAudio": config["requires_audio"],
                    "requiresImage": config["requires_image"],
                    "hasOptions": config["has_options"],
                    "description": config.get("description"),
                    "skillCategory": config.get("skill_category")
                }
                for qtype, config in all_types.items()
            ]
        }
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 其他异常转换为HTTP异常
        raise HTTPException(
            status_code=500,
            detail=f"获取题目类型时发生错误: {str(e)}"
        )