# app/features/auth/schemas.py
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    """登录请求"""
    user_name: str
    password: str


class UserInfo(BaseModel):
    """用户基本信息"""
    user_id: str
    user_name: str
    points: int


class LoginResponse(BaseModel):
    """登录响应数据"""
    access_token: str
    token_type: str
    session_id: str
    user_info: UserInfo


class LogoutRequest(BaseModel):
    """登出请求（可选，如果需要明确的请求体）"""
    pass
