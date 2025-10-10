# app/schemas.py
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, EmailStr
import uuid

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

# 题目集合相关数据模型
class QuestionRequest(BaseModel):
    phaseId: int
    topicId: int
    duration: int  # 持续时间，单位秒
    questionTypes: List[str]  # 题目类型列表，如 ["listening_comprehension", "reading_comprehension"]
    userId: Optional[str] = None  # 用户ID
    token: Optional[str] = None  # 用户token
    count: Optional[int] = 10  # 题目数量，默认10题

class QuestionContent(BaseModel):
    question: str  # 问题文本
    audioUrl: Optional[str] = None  # 音频URL（听力题目需要）
    imageUrl: Optional[str] = None  # 图片URL（看图题目需要）
    options: Optional[List[str]] = None  # 选择题选项
    correctAnswer: Optional[int] = None  # 正确答案索引（选择题）
    correctAnswers: Optional[List[int]] = None  # 多选题正确答案索引
    correctText: Optional[str] = None  # 填空题或问答题正确答案

class Question(BaseModel):
    questionId: str  # 题目ID
    questionType: str  # 题目类型
    content: QuestionContent  # 题目内容

class QuestionResponse(BaseModel):
    phase: int
    topic: int
    count: int  # 实际题目数量
    sessionId: str  # 会话标识
    duration: int  # 持续时间
    token: Optional[str] = None  # 用户token
    questions: List[Question]  # 题目列表

# 提交答案相关模型
class SubmissionItem(BaseModel):
    exerciseId: str  # 题目ID
    userAnswer: Any  # 用户答案，可以是bool、int、str等
    points: int  # 获得的分数

class SubmitAnswersRequest(BaseModel):
    sessionId: str  # 会话ID
    token: str  # 用户token
    submissionList: List[SubmissionItem]  # 提交的答案列表

class SubmitAnswersResponse(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None