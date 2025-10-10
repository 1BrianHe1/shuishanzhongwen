# app/features/user/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import ResponseModel
from .schemas import RegisterRequest, SubmitAnswersRequest
from .service import UserService


router = APIRouter(prefix="/user", tags=["用户"])


@router.post("/register", response_model=ResponseModel, summary="用户注册")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    用户注册接口

    - **user_name**: 用户名（必填）
    - **password**: 密码（必填）
    - **country**: 国家（选填）
    - **job**: 职业（选填）
    - **phone**: 电话（选填）
    - **email**: 邮箱（选填）
    - **init_cn_level**: 初始中文水平（选填，默认1）

    返回注册结果
    """
    # 检查用户名是否已存在
    existing = UserService.get_user_by_username(db, request.user_name)
    if existing:
        return {"code": 0, "message": "账号已存在", "data": None}

    # 创建用户
    user = UserService.create_user(
        db,
        user_name=request.user_name,
        raw_password=request.password,
        user_extra={
            "country": request.country,
            "job": request.job,
            "phone": request.phone,
            "email": request.email,
            "init_cn_level": request.init_cn_level if request.init_cn_level is not None else 1,
            "points": 0
        }
    )

    return {
        "code": 1,
        "message": "注册成功",
        "data": {
            "user_id": str(user.user_id),
            "user_name": user.user_name
        }
    }


@router.post("/submit-answers", response_model=ResponseModel, summary="提交答案")
def submit_answers(request: SubmitAnswersRequest, db: Session = Depends(get_db)):
    """
    提交答案接口

    - **sessionId**: 会话ID（通过登录接口获取）
    - **token**: 访问令牌（通过登录接口获取）
    - **submissionList**: 提交的答案列表
        - **exerciseId**: 题目ID
        - **userAnswer**: 用户答案（可以是任何类型）
        - **points**: 获得的分数

    返回提交结果，包括：
    - 成功保存的题目数量
    - 本次获得的总积分
    - 用户当前的总积分
    - 所有保存的attempt记录
    """
    # 通过sessionId查询用户
    user = UserService.get_user_by_session_id(db, request.sessionId)
    if not user:
        return {
            "code": 0,
            "message": "无效的session或用户未登录",
            "data": None
        }

    # 提交答案并更新积分
    submissions = [item.model_dump() for item in request.submissionList]
    result = UserService.submit_answers(db, user, request.sessionId, submissions)

    return {
        "code": 1,
        "message": "答案提交成功",
        "data": result
    }
