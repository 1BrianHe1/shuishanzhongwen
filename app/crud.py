# app/crud.py
from sqlalchemy.orm import Session
from . import models
from .core import security
from datetime import datetime

def get_user_by_userid(db: Session, userid: str):
    # return db.query(models.User).filter(models.User.userid == userid).first()
    return db.query(models.User).filter(models.User.user_name == userid).first()

# def create_user(db: Session, userid: str, password: str, user_nick: str = None):
#     hashed = security.hash_password(password)
#     user = models.User(userid=userid, hashed_password=hashed, user_nick=user_nick)
#     db.add(user)
#     db.commit()
#     db.refresh(user)
#     return user

def create_user(db: Session, userid: str, raw_password: str, user_extra: dict = None):
    """
    user_extra 可以包含 country/job/phone/email/init_cn_level 等
    """
    hashed = security.hash_password(raw_password)
    user = models.User(
        user_name=userid,
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