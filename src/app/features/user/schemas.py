# app/features/user/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict


class RegisterRequest(BaseModel):
    """用户注册请求"""
    user_name: str
    password: str
    country: Optional[str] = None
    job: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    init_cn_level: Optional[int] = None


class SubmissionItem(BaseModel):
    """单个题目提交项"""
    exerciseId: str  # 题目ID
    userAnswer: Any  # 用户答案，可以是bool、int、str等
    points: int  # 获得的分数


class SubmitAnswersRequest(BaseModel):
    """提交答案请求"""
    sessionId: str  # 会话ID
    token: str  # 用户token
    submissionList: List[SubmissionItem]  # 提交的答案列表


class AttemptInfo(BaseModel):
    """单个attempt信息"""
    attempt_id: str
    exercise_id: str
    points: int


class SubmitAnswersData(BaseModel):
    """提交答案响应数据"""
    total_submissions: int
    saved_count: int
    total_points_earned: int
    current_total_points: int
    attempts: List[Dict[str, Any]]
    errors: Optional[List[str]] = None
