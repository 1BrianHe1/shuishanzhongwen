# app/crud.py
from sqlalchemy.orm import Session
from . import models
from .core import security
from datetime import datetime

def get_user_by_username(db: Session, user_name: str):
    # return db.query(models.User).filter(models.User.userid == userid).first()
    return db.query(models.User).filter(models.User.user_name == user_name).first()

def create_user(db: Session, user_name: str, raw_password: str, user_extra: dict = None):
    """
    user_extra 可以包含 country/job/phone/email/init_cn_level 等
    """
    hashed = security.hash_password(raw_password)
    user = models.User(
        user_name=user_name,
        password_hash=hashed,
        country=(user_extra.get("country") if user_extra else None),
        job=(user_extra.get("job") if user_extra else None),
        phone=(user_extra.get("phone") if user_extra else None),
        email=(user_extra.get("email") if user_extra else None),
        init_cn_level=(user_extra.get("init_cn_level") if user_extra else None),
        points=(user_extra.get("points") if user_extra else 0),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_user_session(db: Session, user_id: str, token: str):
    session = models.UserSession(user_id=user_id, token=token)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def logout_user_session(db: Session, token: str):
    session = db.query(models.UserSession).filter(models.UserSession.token == token, models.UserSession.logout_time.is_(None)).first()
    if session:
        session.logout_time = datetime.utcnow()
        db.commit()
    return session

def get_user_by_token(db: Session, token: str):
    return db.query(models.UserSession).filter(models.UserSession.token == token, models.UserSession.logout_time.is_(None)).first()

# app/crud.py (追加)
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.core import otp as otp_core


# app/crud.py
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core import otp as otp_core

def create_verification_code(db: Session, channel: str, recipient: str, action: str):
    """
    在数据库端完成冷却判断并原子插入验证码记录。
    - channel: 'email' | 'phone'
    - recipient: 邮箱或手机号
    - action: 'register' | 'login'
    成功：返回 (明文验证码, None)
    频率限制：返回 (None, "发送过于频繁，请稍后再试")
    """
    cooldown = otp_core.cooldown_seconds()             # 冷却秒数（来自 .env）
    code = otp_core.gen_numeric_code()                 # 明文验证码（例如 6 位数字）
    code_hash = otp_core.hash_code(code)               # 哈希存储
    expires_at = otp_core.expires_at_from_now()        # 过期时间(UTC-aware)

    # 说明：
    # 1) recent CTE：最近 cooldown 秒内是否已有发送记录
    # 2) INSERT ... WHERE NOT EXISTS (recent)：若命中冷却窗口，不插入且不返回行
    # 3) RETURNING id：用于判断插入是否发生
    sql = text("""
        WITH recent AS (
          SELECT 1
          FROM people.verification_code
          WHERE recipient = :recipient
            AND action    = :action
            AND created_at > (now() - make_interval(secs => :cooldown))
          LIMIT 1
        )
        INSERT INTO people.verification_code (channel, recipient, action, code_hash, expires_at)
        SELECT :channel, :recipient, :action, :code_hash, :expires_at
        WHERE NOT EXISTS (SELECT 1 FROM recent)
        RETURNING id
    """)

    # 采用参数化，避免 SQL 注入
    params = {
        "recipient": recipient,
        "action": action,
        "cooldown": cooldown,
        "channel": channel,
        "code_hash": code_hash,
        "expires_at": expires_at,  # SQLAlchemy 会正确发送 timestamptz
    }

    result = db.execute(sql, params)
    row = result.first()

    if not row:
        # 未插入 => 命中冷却窗口
        db.rollback()  # 回滚这次事务（可选，插入未发生，但保持整洁）
        return None, "发送过于频繁，请稍后再试"

    db.commit()
    return code, None
    
    # 下面生成验证码/写入同上
    code = otp_core.gen_numeric_code()
    code_hash = otp_core.hash_code(code)
    v = models.VerificationCode(
        channel=channel,
        recipient=recipient,
        action=action,
        code_hash=code_hash,
        expires_at=otp_core.expires_at_from_now()
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return code, None  # 返回明文 code 以便发信（生产中不要回传给客户端）

def verify_and_consume_code(db: Session, channel: str, recipient: str, action: str, code_plain: str) -> bool:
    # 找到未使用、未过期的验证码记录（按时间倒序）
    candidates = (db.query(models.VerificationCode)
                    .filter(models.VerificationCode.channel == channel,
                            models.VerificationCode.recipient == recipient,
                            models.VerificationCode.action == action,
                            models.VerificationCode.used_at.is_(None),
                            models.VerificationCode.expires_at > otp_core.now_utc())
                    .order_by(desc(models.VerificationCode.created_at))
                    .all())
    if not candidates:
        return False

    code_hash_input = otp_core.hash_code(code_plain)
    for rec in candidates:
        if rec.code_hash == code_hash_input:
            rec.used_at = datetime.utcnow()
            db.commit()
            return True
    return False

def get_user_by_session_id(db: Session, session_id: str):
    """通过session_id查询用户"""
    session = db.query(models.UserSession).filter(
        models.UserSession.session_id == session_id,
        models.UserSession.logout_time.is_(None)
    ).first()
    if session:
        return db.query(models.User).filter(models.User.user_id == session.user_id).first()
    return None

def create_attempt(db: Session, attempt_data: dict):
    """创建attempt记录"""
    attempt = models.Attempt(**attempt_data)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt