# app/features/auth/service.py
from sqlalchemy.orm import Session
from app.core import security
from app import models
from typing import Optional, Tuple


class AuthService:
    """认证服务"""

    @staticmethod
    def authenticate_user(db: Session, user_name: str, password: str) -> Optional[models.User]:
        """
        验证用户凭证

        Args:
            db: 数据库会话
            user_name: 用户名
            password: 密码

        Returns:
            验证成功返回用户对象，失败返回 None
        """
        user = db.query(models.User).filter(models.User.user_name == user_name).first()
        if not user:
            return None
        if not security.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_user_session(db: Session, user_id: str, token: str) -> models.UserSession:
        """
        创建用户会话

        Args:
            db: 数据库会话
            user_id: 用户ID
            token: 访问令牌

        Returns:
            创建的会话对象
        """
        session = models.UserSession(user_id=user_id, token=token)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def logout_user(db: Session, token: str) -> bool:
        """
        登出用户

        Args:
            db: 数据库会话
            token: 访问令牌

        Returns:
            成功返回 True，失败返回 False
        """
        from datetime import datetime

        session = db.query(models.UserSession).filter(
            models.UserSession.token == token,
            models.UserSession.logout_time.is_(None)
        ).first()

        if not session:
            return False

        session.logout_time = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def get_user_by_token(db: Session, token: str) -> Optional[models.UserSession]:
        """
        通过 token 获取用户会话

        Args:
            db: 数据库会话
            token: 访问令牌

        Returns:
            会话对象或 None
        """
        return db.query(models.UserSession).filter(
            models.UserSession.token == token,
            models.UserSession.logout_time.is_(None)
        ).first()

    @staticmethod
    def generate_access_token(user_id: str, username: str) -> str:
        """
        生成访问令牌

        Args:
            user_id: 用户ID
            username: 用户名

        Returns:
            JWT token
        """
        return security.create_access_token({
            "user_id": str(user_id),
            "username": username
        })
