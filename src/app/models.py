# app/models.py
from sqlalchemy import Column, Text, TIMESTAMP, func, text, Integer, ForeignKey, String, Numeric, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
import uuid
import enum

class User(Base):
    __tablename__ = "users"#表名
    __table_args__ = {"schema": "people"}#schema
    user_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_name = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    job = Column(Text, nullable=True)
    reg_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    phone = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    # init_cn_level = Column(Integer, nullable=True)
    init_cn_level=Column(Integer,nullable=False,server_default="0")  # 初始中文水平，默认0
    password_hash = Column(Text, nullable=False)  # 认证所需字段
    points=Column(Integer, nullable=False, server_default="0")  # 积分，默认0

class UserSession(Base):
    __tablename__ = "users_session"
    __table_args__ = {"schema": "people"}

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("people.users.user_id"))
    token = Column(String, nullable=False)
    login_time = Column(TIMESTAMP(timezone=True), server_default="now()")
    logout_time = Column(TIMESTAMP(timezone=True), nullable=True)

class VerificationCode(Base):
    __tablename__ = "verification_code"
    __table_args__ = {"schema": "people"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(16), nullable=False)     # 'email' | 'phone'
    recipient = Column(String(255), nullable=False)  # 邮箱地址或手机号
    action = Column(String(16), nullable=False)      # 'register' | 'login'
    code_hash = Column(String(128), nullable=False)  # 哈希存储验证码
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used_at = Column(TIMESTAMP(timezone=True), nullable=True)

class AttemptStatus(enum.Enum):
    in_progress = "in_progress"
    submitted = "submitted"
    completed = "completed"

class Attempt(Base):
    __tablename__ = "attempt"
    __table_args__ = {"schema": "events"}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    person_id = Column(UUID(as_uuid=True), nullable=True)
    exercise_id = Column(UUID(as_uuid=True), nullable=False)
    exercise_format = Column(Text, nullable=True)
    exercise_skill = Column(Text, nullable=True)
    exercise_hsk_level = Column(Integer, nullable=True)
    exercise_difficulty = Column(Integer, nullable=True)
    exercise_points = Column(Numeric, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    submitted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(Enum(AttemptStatus, schema='events'), nullable=False, server_default=text("'in_progress'::events.attempt_status"))
    total_score = Column(Numeric, nullable=True, server_default=text("0"))
    full_marks = Column(Numeric, nullable=True, server_default=text("0"))
    is_full_correct = Column(Boolean, nullable=True)
    attempt_meta = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())