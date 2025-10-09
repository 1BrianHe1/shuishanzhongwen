import uuid
from sqlalchemy import Column, String, ForeignKey, JSON,SmallInteger,Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base 
from sqlalchemy import SmallInteger, Text 

SCHEMA="content_new"

class Word(Base):
    __tablename__ = "words"
    __table_args__ = {"schema": SCHEMA} 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    characters = Column(String(100), nullable=False, unique=True)
    pinyin = Column(String(255))
    translation = Column(Text)
    hsk_level = Column(SmallInteger)
    exercises = relationship("Exercise", back_populates="word")
    lessons = relationship("LessonWord", back_populates="word")

class LessonWord(Base):
    __tablename__ = "lesson_words"
    __table_args__ = {"schema": SCHEMA}
    lesson_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.lessons.id"), primary_key=True)  
    word_id   = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.words.id"),   primary_key=True)
    word = relationship("Word", back_populates="lessons")  # 与 Word.lessons 对应
    lesson = relationship("Lesson", back_populates="word_links")
  

class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phase_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.phases.id"), nullable=False)
    topic_name = Column(String(255), nullable=False)
    
    # 定义与 Phase 的多对一关系
    phase = relationship("Phase", back_populates="topics")
    # 定义反向关系，让我们可以从 Topic 访问其下所有的 Lesson
    lessons = relationship("Lesson", back_populates="topic")

class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.topics.id"), nullable=False)
    lesson_name = Column(String(255), nullable=False)
    
    # 定义与 Topic 的多对一关系
    topic = relationship("Topic", back_populates="lessons")
    word_links = relationship("LessonWord", back_populates="lesson")

class Phase(Base):
    __tablename__ = "phases"
    __table_args__ = {"schema": SCHEMA} 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)

    topics = relationship("Topic", back_populates="phase")

class ExerciseType(Base):
    __tablename__ = "exercise_types"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)

class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_url = Column(String, nullable=False, unique=True)
    file_type = Column(String(50), nullable=False)
    mime_type = Column(String(100))
    
    exercise_links = relationship("ExerciseMediaAsset", back_populates="media_asset")

class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = {"schema": "content_new"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # [修改] 明确外键指向，这是建立关系的基础
    parent_exercise_id = Column(UUID(as_uuid=True), ForeignKey("content_new.exercises.id"), nullable=True)

    word_id = Column(UUID(as_uuid=True), ForeignKey("content_new.words.id"))
    exercise_type_id = Column(UUID(as_uuid=True), ForeignKey("content_new.exercise_types.id"))
    meta = Column("metadata", JSON)
    prompt = Column(String)
    display_order = Column(Integer, nullable=False, default=0)
    
    type = relationship("ExerciseType")
    media_links = relationship("ExerciseMediaAsset", back_populates="exercise", cascade="all, delete-orphan")
    word = relationship("Word", back_populates="exercises")

    # [新增] 添加父子双向关系，让 SQLAlchemy 能够处理嵌套查询
    parent = relationship("Exercise", remote_side=[id], back_populates="children")
    children = relationship("Exercise", back_populates="parent", cascade="all, delete-orphan")


class ExerciseMediaAsset(Base):
    __tablename__ = "exercise_media_assets"
    __table_args__ = {"schema": SCHEMA}
    exercise_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.exercises.id"),    primary_key=True)  
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.media_assets.id"), primary_key=True)  
    usage_role = Column(String(100), primary_key=True)
    
    # 定义与两端模型的关系，完成双向链接
    exercise = relationship("Exercise", back_populates="media_links")
    media_asset = relationship("MediaAsset", back_populates="exercise_links")