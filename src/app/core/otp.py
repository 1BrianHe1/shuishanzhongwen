# app/core/otp.py
import os, secrets, hashlib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

from .security import SECRET_KEY  # 复用你的 SECRET_KEY 作为盐

OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", 10))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", 60))
OTP_DEV_ECHO_CODE = os.getenv("OTP_DEV_ECHO_CODE", "true").lower() == "true"

def gen_numeric_code(length: int = 6) -> str:
    # 生成 6 位数字验证码（不以 0 开头）
    first = str(secrets.randbelow(9) + 1)
    rest = "".join(str(secrets.randbelow(10)) for _ in range(length - 1))
    return first + rest

def hash_code(code: str) -> str:
    # 用 SECRET_KEY 做盐
    return hashlib.sha256((code + SECRET_KEY).encode("utf-8")).hexdigest()

def to_aware_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 假如偶发拿到 naive，就直接标注为 UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def now_utc():
    return datetime.utcnow()

def expires_at_from_now():
    return now_utc() + timedelta(minutes=OTP_EXPIRE_MINUTES)

def should_echo_code_in_response() -> bool:
    return OTP_DEV_ECHO_CODE

def cooldown_seconds() -> int:
    return OTP_RESEND_COOLDOWN_SECONDS