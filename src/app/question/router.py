# app/question/router.py
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

try:
    from app.database import get_db
except ImportError:
    # 用于测试环境的导入
    def get_db():
        return None

from .schemas import (
    ListenImageTrueFalseRequest,
    ListenImageTrueFalseResponse,
    QuestionTypesResponse,
    QuestionType,
    ExerciseRequest,
    ExerciseResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse
)
from .service import (
    generate_listen_image_true_false_questions,
    get_exercise_types_from_db,
    submit_answers,
    generate_exercises_by_types,
    generate_tf_exercises,
    generate_choice_exercises,
    generate_match_exercises,
    generate_order_exercises
)

router = APIRouter(prefix="/api/questions", tags=["Questions"])

@router.post(
    "/listen-image-true-false",
    response_model=ListenImageTrueFalseResponse,
    summary="生成听录音看图判断题目",
    description="根据用户参数生成听录音看图判断题目，支持按阶段、主题、课程筛选"
)
async def create_listen_image_true_false_questions(
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

        # 调用服务层生成题目
        response = generate_listen_image_true_false_questions(
            count=req.count,
            db=db,
            phase_name=req.phaseName,
            topic_name=req.topicName,
            lesson_name=req.lessonName
        )

        return response

    except HTTPException:
        # 重新抛出HTTP异常（保持原状态码）
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成LISTEN_IMAGE_TRUE_FALSE题目时发生错误: {str(e)}"
        )

@router.get(
    "/types",
    response_model=QuestionTypesResponse,
    summary="获取支持的题目类型列表",
    description="获取系统支持的所有题目类型及其配置信息"
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

        question_types = [
            QuestionType(
                type=qtype,
                name=config["name"],
                requiresAudio=config["requires_audio"],
                requiresImage=config["requires_image"],
                hasOptions=config["has_options"],
                description=config.get("description"),
                skillCategory=config.get("skill_category")
            )
            for qtype, config in all_types.items()
        ]

        return QuestionTypesResponse(questionTypes=question_types)

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 其他异常转换为HTTP异常
        raise HTTPException(
            status_code=500,
            detail=f"获取题目类型时发生错误: {str(e)}"
        )

# ===========================================
# 新增接口
# ===========================================

@router.post(
    "/submit",
    response_model=SubmitAnswerResponse,
    summary="提交答案",
    description="提交用户答案并获取评分结果"
)
async def submit_user_answers(
    req: SubmitAnswerRequest,
    db: Session = Depends(get_db)
):
    """
    提交答案接口

    Args:
        req: 提交答案请求参数
        db: 数据库会话

    Returns:
        SubmitAnswerResponse: 评分结果响应
    """
    try:
        # 检查数据库连接
        if db is None:
            raise HTTPException(
                status_code=500,
                detail="数据库连接不可用"
            )

        # 调用服务层提交答案
        response = submit_answers(req, db)
        return response

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"提交答案时发生错误: {str(e)}"
        )

@router.post(
    "/generate",
    response_model=ExerciseResponse,
    summary="生成题目集合",
    description="根据课程和题型要求生成题目集合"
)
async def generate_exercises(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """
    生成题目集合接口

    Args:
        req: 题目生成请求参数
        db: 数据库会话

    Returns:
        ExerciseResponse: 题目集合响应
    """
    try:
        # 检查数据库连接
        if db is None:
            raise HTTPException(
                status_code=500,
                detail="数据库连接不可用"
            )

        # 如果没有指定题型，默认使用听音看图判断
        exercise_types = req.exerciseTypes or ['LISTEN_IMAGE_TRUE_FALSE']

        # 调用服务层生成题目
        response = generate_exercises_by_types(
            exercise_types=exercise_types,
            count=req.count,
            db=db,
            phase_name=req.phaseName,
            topic_name=req.topicName,
            lesson_name=req.lessonName
        )

        # 设置duration
        if req.duration:
            response.duration = req.duration

        return response

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成题目时发生错误: {str(e)}"
        )

# ===========================================
# 按题型分类的接口
# ===========================================

@router.post(
    "/tf/listen-image",
    response_model=ExerciseResponse,
    summary="生成听音看图判断题",
    description="生成听录音看图判断对错的题目"
)
async def generate_listen_image_tf(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成听音看图判断题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_tf_exercises(
            'LISTEN_IMAGE_TRUE_FALSE', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成听音看图判断题时发生错误: {str(e)}")

@router.post(
    "/tf/read-image",
    response_model=ExerciseResponse,
    summary="生成读词看图判断题",
    description="生成读词看图判断对错的题目"
)
async def generate_read_image_tf(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成读词看图判断题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_tf_exercises(
            'READ_IMAGE_TRUE_FALSE', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成读词看图判断题时发生错误: {str(e)}")

@router.post(
    "/tf/listen-sentence",
    response_model=ExerciseResponse,
    summary="生成听音看句判断题",
    description="生成听音看句判断对错的题目"
)
async def generate_listen_sentence_tf(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成听音看句判断题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_tf_exercises(
            'LISTEN_SENTENCE_TF', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成听音看句判断题时发生错误: {str(e)}")

@router.post(
    "/tf/read-sentence",
    response_model=ExerciseResponse,
    summary="生成阅读判断题",
    description="生成阅读判断对错的题目"
)
async def generate_read_sentence_tf(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成阅读判断题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_tf_exercises(
            'READ_SENTENCE_TF', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成阅读判断题时发生错误: {str(e)}")

@router.post(
    "/choice/listen-image",
    response_model=ExerciseResponse,
    summary="生成听音选图题",
    description="生成听录音选择图片的题目"
)
async def generate_listen_image_choice(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成听音选图题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_choice_exercises(
            'LISTEN_IMAGE_MC', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成听音选图题时发生错误: {str(e)}")

@router.post(
    "/choice/listen-sentence",
    response_model=ExerciseResponse,
    summary="生成听音选择题",
    description="生成听录音选择答案的题目"
)
async def generate_listen_sentence_choice(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成听音选择题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_choice_exercises(
            'READ_SENTENCE_COMPREHENSION_CHOICE', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成听音选择题时发生错误: {str(e)}")

@router.post(
    "/choice/read-sentence",
    response_model=ExerciseResponse,
    summary="生成阅读选择题",
    description="生成阅读选择答案的题目"
)
async def generate_read_sentence_choice(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成阅读选择题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_choice_exercises(
            'READ_SENTENCE_COMPREHENSION_CHOICE', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成阅读选择题时发生错误: {str(e)}")

@router.post(
    "/match/listen-image",
    response_model=ExerciseResponse,
    summary="生成听音连图题",
    description="生成听录音与图片配对的题目"
)
async def generate_listen_image_match(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成听音连图题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_match_exercises(
            'LISTEN_IMAGE_MATCH', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成听音连图题时发生错误: {str(e)}")

@router.post(
    "/match/read-image",
    response_model=ExerciseResponse,
    summary="生成读文连图题",
    description="生成阅读文字与图片配对的题目"
)
async def generate_read_image_match(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成读文连图题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_match_exercises(
            'READ_IMAGE_MATCH', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成读文连图题时发生错误: {str(e)}")

@router.post(
    "/match/read-dialog",
    response_model=ExerciseResponse,
    summary="生成问答配对题",
    description="生成问句与答句配对的题目"
)
async def generate_read_dialog_match(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成问答配对题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_match_exercises(
            'READ_DIALOGUE_MATCH', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成问答配对题时发生错误: {str(e)}")

@router.post(
    "/order/word",
    response_model=ExerciseResponse,
    summary="生成连词成句题",
    description="生成连词成句的题目"
)
async def generate_word_order(
    req: ExerciseRequest,
    db: Session = Depends(get_db)
):
    """生成连词成句题"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="数据库连接不可用")

        exercises = generate_order_exercises(
            'READ_WORD_ORDER', req.count, db,
            req.phaseName, req.topicName, req.lessonName
        )

        return ExerciseResponse(
            phaseId=req.phaseName,
            topicId=req.topicName,
            duration=req.duration,
            count=len(exercises),
            sessionId=str(uuid.uuid4()),
            exercises=exercises
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成连词成句题时发生错误: {str(e)}")