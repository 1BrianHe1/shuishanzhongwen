# app/question/schemas.py
from pydantic import BaseModel
from typing import List, Optional, Union, Dict, Any

# ===========================================
# 基础数据模型
# ===========================================

# 选项模型（用于选择题）
class Option(BaseModel):
    label: str  # 选项标签（A, B, C, D）
    text: Optional[str] = None  # 文本内容
    imageUrl: Optional[str] = None  # 图片URL
    pinyin: Optional[str] = None  # 拼音

# 配对题项目模型
class MatchItem(BaseModel):
    label: str  # 标签（0, 1, 2 或 A, B, C）
    text: Optional[str] = None  # 文本内容
    audioUrl: Optional[str] = None  # 音频URL
    imageUrl: Optional[str] = None  # 图片URL
    listeningText: Optional[str] = None  # 听力文本
    pinyin: Optional[str] = None  # 拼音

# 排序题词语/句子模型
class OrderItem(BaseModel):
    label: str  # 标签
    word: Optional[str] = None  # 词语（连词成句）
    sentence: Optional[str] = None  # 句子（连句成段）
    pinyin: Optional[str] = None  # 拼音

# ===========================================
# 题目内容模型（按题型分类）
# ===========================================

# TF判断题内容
class TFContent(BaseModel):
    prompt: str  # 题目提示语
    audioUrl: Optional[str] = None  # 音频URL
    listeningText: Optional[str] = None  # 听力文本
    imageUrl: Optional[str] = None  # 图片URL
    statement: Optional[str] = None  # 描述性语句
    passage: Optional[str] = None  # 阅读文章内容

# 选择题内容
class ChoiceContent(BaseModel):
    prompt: str  # 题目提示语
    audioUrl: Optional[str] = None  # 音频URL
    listeningText: Optional[str] = None  # 听力文本
    imageUrl: Optional[str] = None  # 图片URL
    passage: Optional[str] = None  # 阅读文章内容
    question: Optional[str] = None  # 题干
    options: List[Option]  # 选项列表

# 配对题内容
class MatchContent(BaseModel):
    prompt: str  # 题目提示语
    leftItems: List[MatchItem]  # 左侧项目
    rightItems: List[MatchItem]  # 右侧项目

# 排序题内容
class OrderContent(BaseModel):
    prompt: str  # 题目提示语
    words: Optional[List[OrderItem]] = None  # 词语列表（连词成句）
    sentences: Optional[List[OrderItem]] = None  # 句子列表（连句成段）

# ===========================================
# 通用题目模型
# ===========================================

class Exercise(BaseModel):
    exerciseId: str  # 题目ID
    exerciseType: str  # 题目类型
    content: Union[TFContent, ChoiceContent, MatchContent, OrderContent]  # 题目内容
    correctAnswer: Union[bool, str, List[str], Dict[str, str]]  # 正确答案

# ===========================================
# 请求模型
# ===========================================

# 通用获取题目请求
class ExerciseRequest(BaseModel):
    lessonId: Optional[str] = None  # 课程ID
    duration: Optional[int] = None  # 持续时间（秒）
    exerciseTypes: Optional[List[str]] = None  # 题目类型列表
    token: Optional[str] = None  # 用户token
    count: int = 1  # 题目数量，默认1题
    # 兼容旧版本的筛选参数
    phaseName: Optional[str] = None  # 阶段名称
    topicName: Optional[str] = None  # 主题名称
    lessonName: Optional[str] = None  # 课程名称
    userId: Optional[str] = None  # 用户ID

# 提交答案的单个题目
class SubmissionItem(BaseModel):
    exerciseId: str  # 题目ID
    userAnswer: Union[bool, str, List[str], Dict[str, str]]  # 用户答案
    points: Optional[int] = None  # 得分
    wrongAttempts: Optional[int] = 0  # 错误尝试次数

# 提交答案请求
class SubmitAnswerRequest(BaseModel):
    sessionId: str  # 会话ID
    token: Optional[str] = None  # 用户token
    submission_list: List[SubmissionItem]  # 提交的答案列表

# ===========================================
# 响应模型
# ===========================================

# 题目响应
class ExerciseResponse(BaseModel):
    phaseId: Optional[str] = None  # 阶段ID
    topicId: Optional[str] = None  # 主题ID
    duration: Optional[int] = None  # 持续时间
    count: int  # 题目数量
    sessionId: str  # 会话ID
    exercises: List[Exercise]  # 题目列表

# 提交答案响应的单个结果
class SubmissionResult(BaseModel):
    exerciseId: str  # 题目ID
    isCorrect: bool  # 是否正确
    points: int  # 得分
    correctAnswer: Union[bool, str, List[str], Dict[str, str]]  # 正确答案

# 提交答案响应
class SubmitAnswerResponse(BaseModel):
    sessionId: str  # 会话ID
    totalScore: int  # 总分
    correctCount: int  # 正确题目数
    totalCount: int  # 总题目数
    results: List[SubmissionResult]  # 详细结果

# ===========================================
# 旧版本兼容模型
# ===========================================

# 听音判断对错题目请求模型（兼容）
class ListenImageTrueFalseRequest(BaseModel):
    count: int = 1  # 题目数量，默认1题
    userId: Optional[str] = None  # 用户ID
    token: Optional[str] = None  # 用户token
    phaseName: Optional[str] = None  # 阶段名称
    topicName: Optional[str] = None  # 主题名称
    lessonName: Optional[str] = None  # 课程名称

# 简化的题目内容模型（兼容）
class SimpleQuestionContent(BaseModel):
    question: str  # 问题文本
    audioUrl: Optional[str] = None  # 音频URL
    imageUrl: Optional[str] = None  # 图片URL
    listeningText: Optional[str] = None  # 听力文本

# 简化的题目模型（兼容）
class SimpleQuestion(BaseModel):
    questionId: str  # 题目ID（对应exercise_id）
    questionType: str  # 题目类型
    content: SimpleQuestionContent  # 题目内容
    correctAnswer: Optional[int] = None  # 正确答案

# 听音判断对错题目响应模型（兼容）
class ListenImageTrueFalseResponse(BaseModel):
    count: int  # 实际题目数量
    sessionId: str  # 会话标识
    questions: List[SimpleQuestion]  # 题目列表

# 题目类型响应模型
class QuestionType(BaseModel):
    type: str
    name: str
    requiresAudio: bool
    requiresImage: bool
    hasOptions: bool
    description: Optional[str] = None
    skillCategory: Optional[str] = None

class QuestionTypesResponse(BaseModel):
    questionTypes: List[QuestionType]