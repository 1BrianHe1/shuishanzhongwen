# file: question/schemas.py (真正、绝对、最终的修正版)

from typing import Any, Dict, List, Literal, Union, Optional
from typing_extensions import Annotated
from pydantic import BaseModel, Field,ConfigDict

# --- I. API 输入/请求 模型 ---
class ExerciseRequest(BaseModel):
    lessonId: str = Field(..., description="课程ID")
    duration: int = Field(..., gt=0, description="期望的练习总时长（秒）")
    exerciseTypes: List[str] = Field(..., description="期望练习的题型名称列表")

# --- II. API 输出/响应 模型 ---
# -- II.A 可复用的子组件模型 --
class McOptionImage(BaseModel): label: str; imageUrl: Optional[str]
class McOptionText(BaseModel): label: str; text: str; pinyin: str
class MatchItemAudio(BaseModel): label: str; audioUrl: Optional[str]; listeningText: str
class MatchItemImage(BaseModel): label: str; imageUrl: Optional[str]
class MatchItemText(BaseModel): label: str; text: str; pinyin: str
class WordOrderItem(BaseModel):
    label: str
    text: str = Field(..., alias="word/sentence")
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)


# -- II.B 每种题型独立的 Content 模型 --
class ListenImageTrueFalseContent(BaseModel): prompt: str; audioUrl: Optional[str]; listeningText: str; imageUrl: Optional[str]
class ReadImageTrueFalseContent(BaseModel): prompt: str; statement: str; imageUrl: Optional[str]
class ListenSentenceTfContent(BaseModel): prompt: str; audioUrl: Optional[str]; listeningText: str; statement: str
class ReadSentenceTfContent(BaseModel): prompt: str; passage: str; statement: str
class ListenImageMcContent(BaseModel): prompt: str; audioUrl: Optional[str]; listeningText: str; options: List[McOptionImage]
class ListenSentenceQaContent(BaseModel): prompt: str; audioUrl: Optional[str]; listeningText: str; question: str; options: List[McOptionText]
class ReadSentenceComprehensionChoiceContent(BaseModel): prompt: str; passage: str; question: str; options: List[McOptionText]
class ReadWordGapFillContent(BaseModel): prompt: str; question: str; options: List[McOptionText]
class ListenImageMatchContent(BaseModel): prompt: str; leftItems: List[MatchItemAudio]; rightItems: List[MatchItemImage]
class ReadImageMatchContent(BaseModel): prompt: str; leftItems: List[MatchItemText]; rightItems: List[MatchItemImage]
class ReadDialogueMatchContent(BaseModel): prompt: str; leftItems: List[MatchItemText]; rightItems: List[MatchItemText]
class ReadWordOrderContent(BaseModel):
    prompt: str
    # 出参键名为 "words/sentences"
    items: List[WordOrderItem] = Field(..., alias="words/sentences")
    # 关键：用别名做序列化（让响应里真的叫 "words/sentences"）
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

# -- II.C 每种题型完整的 Exercise 模型 --
class ListenImageTrueFalseExercise(BaseModel): exerciseId: str; exerciseType: Literal["LISTEN_IMAGE_TRUE_FALSE"]; content: ListenImageTrueFalseContent; correctAnswer: bool
class ReadImageTrueFalseExercise(BaseModel): exerciseId: str; exerciseType: Literal["READ_IMAGE_TRUE_FALSE"]; content: ReadImageTrueFalseContent; correctAnswer: bool
class ListenSentenceTfExercise(BaseModel): exerciseId: str; exerciseType: Literal["LISTEN_SENTENCE_TF"]; content: ListenSentenceTfContent; correctAnswer: bool
class ReadSentenceTfExercise(BaseModel): exerciseId: str; exerciseType: Literal["READ_SENTENCE_TF"]; content: ReadSentenceTfContent; correctAnswer: bool
class ListenImageMcExercise(BaseModel): exerciseId: str; exerciseType: Literal["LISTEN_IMAGE_MC"]; content: ListenImageMcContent; correctAnswer: str
class ListenSentenceQaExercise(BaseModel): exerciseId: str; exerciseType: Literal["LISTEN_SENTENCE_QA"]; content: ListenSentenceQaContent; correctAnswer: str
class ReadSentenceComprehensionChoiceExercise(BaseModel): exerciseId: str; exerciseType: Literal["READ_SENTENCE_COMPREHENSION_CHOICE"]; content: ReadSentenceComprehensionChoiceContent; correctAnswer: str
class ReadWordGapFillExercise(BaseModel): exerciseId: str; exerciseType: Literal["READ_WORD_GAP_FILL"]; content: ReadWordGapFillContent; correctAnswer: str
class ListenImageMatchExercise(BaseModel): exerciseId: str; exerciseType: Literal["LISTEN_IMAGE_MATCH"]; content: ListenImageMatchContent; correctAnswer: Dict[str, str]
class ReadImageMatchExercise(BaseModel): exerciseId: str; exerciseType: Literal["READ_IMAGE_MATCH"]; content: ReadImageMatchContent; correctAnswer: Dict[str, str]
class ReadDialogueMatchExercise(BaseModel): exerciseId: str; exerciseType: Literal["READ_DIALOGUE_MATCH"]; content: ReadDialogueMatchContent; correctAnswer: Dict[str, str]
class ReadWordOrderExercise(BaseModel):
    exerciseId: str
    exerciseType: Literal["READ_WORD_ORDER"]
    content: ReadWordOrderContent
    # 按你的要求：["1","2",...]
    correctAnswer: List[str]

# -- II.D 最终组合的 Union 类型 --
AnyExercise = Union[
    # [最终的、绝对正确的版本] 包含12个唯一的模型，没有任何重复
    ListenImageTrueFalseExercise,
    ReadImageTrueFalseExercise,
    ListenSentenceTfExercise,
    ReadSentenceTfExercise,
    ListenImageMcExercise,
    ListenSentenceQaExercise,
    ReadSentenceComprehensionChoiceExercise,
    ReadWordGapFillExercise,
    ListenImageMatchExercise,
    ReadImageMatchExercise,
    ReadDialogueMatchExercise,
    ReadWordOrderExercise
]

# -- II.E 最终的 API 响应模型 --
class ExerciseResponse(BaseModel):
    phaseId: str
    topicId: str
    duration: int
    count: int
    sessionId: str
    exercises: List[
        Annotated[AnyExercise, Field(discriminator='exerciseType')]
    ]
