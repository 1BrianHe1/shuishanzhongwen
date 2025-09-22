# app/schemas.py
from typing import Optional
from pydantic import BaseModel, EmailStr

# 请求体
class LoginRequest(BaseModel):
    userid: str
    password: str

class RegisterRequest(BaseModel):
    # userid: str
    # password: str
    # user_nick: Optional[str] = None
    userid: str
    password: str
    country: Optional[str] = None
    job: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    init_cn_level: Optional[int] = None

# 响应体
class UserInfo(BaseModel):
    user_nick: Optional[str] = None

class DataModel(BaseModel):
    user_info: UserInfo

class ResponseModel(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None
