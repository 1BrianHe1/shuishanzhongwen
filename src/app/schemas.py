# app/schemas.py
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr

# 请求体
class LoginRequest(BaseModel):
    user_name: str
    password: str

# class RegisterRequest(BaseModel):
#     # userid: str
#     # password: str
#     # user_nick: Optional[str] = None
#     userid: str
#     password: str
#     country: Optional[str] = None
#     job: Optional[str] = None
#     phone: Optional[str] = None
#     email: Optional[EmailStr] = None
#     init_cn_level: Optional[int] = None

# 响应体
class UserInfo(BaseModel):
    user_nick: Optional[str] = None

class DataModel(BaseModel):
    user_info: UserInfo

class ResponseModel(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None


# 发送验证码
class SendCodeRequest(BaseModel):
    channel: Literal["email", "phone"]
    recipient: str  # email 或 phone
    action: Literal["register", "login"]

# 注册（带验证码）
class RegisterRequest(BaseModel):
    user_name: str
    password: str
    country: Optional[str] = None   
    job: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    init_cn_level: Optional[int] = None
    # 新增：验证码字段（与 phone/email 对应）
    # code: str
    # code_channel: Literal["email", "phone"]  # 指明验证码是发到哪个通道

# 手机/邮箱验证码登录
class LoginByCodeRequest(BaseModel):
    channel: Literal["email", "phone"]
    recipient: str  # email 或 phone
    code: str