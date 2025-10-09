from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from . import schemas
from . import service
from app.database import get_db 


router = APIRouter(prefix="/queryquestion",
    tags=["Question Query"]
)

# 2. 定义 POST /question/get-exercises 端点
@router.post("/get-exercises",response_model=schemas.ExerciseResponse,summary="获取练习题目列表")
async def get_exercises(
    request: schemas.ExerciseRequest,
    db: Session = Depends(get_db)
):
    """
    接收前端的练习请求，并返回一个根据要求动态生成的题目列表。

    - **request**: 请求体数据，FastAPI会自动使用 `schemas.ExerciseRequest` 模型
      对其进行解析和验证。如果前端传来的数据格式不正确，FastAPI会自动返回422错误。

    - **db**: 这是一个依赖注入。`Depends(get_db)` 告诉 FastAPI，在处理这个请求之前，
      需要先调用 `get_db` 函数。`get_db` 会创建一个新的数据库会话(Session)，
      处理完请求后，会自动关闭这个会话。这确保了每个API请求都有一个独立的、
      干净的数据库连接。
    """

    exercise_session = service.create_exercise_session(db=db, request=request)
    if not exercise_session or not exercise_session.get("exercises"):
        raise HTTPException(
            status_code=404,
            detail="未能根据您的要求找到足够的题目，请尝试放宽条件或检查课程ID是否正确。"
        )

    return exercise_session