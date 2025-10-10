# app/features/auth/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app.schemas import ResponseModel
from .schemas import LoginRequest, LoginResponse
from .service import AuthService


router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.post("/login", response_model=ResponseModel, summary="用户登录")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    用户登录接口

    - **user_name**: 用户名
    - **password**: 密码

    返回访问令牌、会话ID和用户信息
    """
    # 验证用户
    user = AuthService.authenticate_user(db, request.user_name, request.password)
    if not user:
        return {"code": 0, "message": "用户名或密码错误", "data": None}

    # 生成 token
    token = AuthService.generate_access_token(user.user_id, user.user_name)

    # 创建会话
    session = AuthService.create_user_session(db, str(user.user_id), token)

    return {
        "code": 1,
        "message": "登录成功",
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "session_id": str(session.session_id),
            "user_info": {
                "user_id": str(user.user_id),
                "user_name": user.user_name,
                "points": user.points
            }
        }
    }


@router.post("/logout", response_model=ResponseModel, summary="用户登出")
def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    用户登出接口

    需要在 Authorization header 中提供有效的 Bearer token
    """
    success = AuthService.logout_user(db, token)
    if not success:
        return {"code": 0, "message": "Token 无效或已登出", "data": None}

    return {"code": 1, "message": "登出成功", "data": None}


@router.get("/me", response_model=ResponseModel, summary="获取当前用户信息")
def get_current_user_info(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    获取当前登录用户信息

    需要在 Authorization header 中提供有效的 Bearer token
    """
    session = AuthService.get_user_by_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="未认证或已登出")

    return {
        "code": 1,
        "message": "success",
        "data": {"user_id": str(session.user_id)}
    }


# 依赖函数：获取当前用户（供其他模块使用）
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    依赖函数：验证token并返回当前用户会话

    用于需要认证的接口
    """
    session = AuthService.get_user_by_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="未认证或已登出")
    return session
