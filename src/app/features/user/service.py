# app/features/user/service.py
from sqlalchemy.orm import Session
from app import models
from app.core import security
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class UserService:
    """用户服务"""

    @staticmethod
    def get_user_by_username(db: Session, user_name: str) -> Optional[models.User]:
        """
        根据用户名查询用户

        Args:
            db: 数据库会话
            user_name: 用户名

        Returns:
            用户对象或 None
        """
        return db.query(models.User).filter(models.User.user_name == user_name).first()

    @staticmethod
    def get_user_by_session_id(db: Session, session_id: str) -> Optional[models.User]:
        """
        通过session_id查询用户

        Args:
            db: 数据库会话
            session_id: 会话ID

        Returns:
            用户对象或 None
        """
        session = db.query(models.UserSession).filter(
            models.UserSession.session_id == session_id,
            models.UserSession.logout_time.is_(None)
        ).first()

        if session:
            return db.query(models.User).filter(
                models.User.user_id == session.user_id
            ).first()
        return None

    @staticmethod
    def create_user(
        db: Session,
        user_name: str,
        raw_password: str,
        user_extra: Optional[Dict[str, Any]] = None
    ) -> models.User:
        """
        创建新用户

        Args:
            db: 数据库会话
            user_name: 用户名
            raw_password: 原始密码
            user_extra: 额外用户信息（country, job, phone, email, init_cn_level等）

        Returns:
            创建的用户对象
        """
        hashed = security.hash_password(raw_password)
        user_extra = user_extra or {}

        user = models.User(
            user_name=user_name,
            password_hash=hashed,
            country=user_extra.get("country"),
            job=user_extra.get("job"),
            phone=user_extra.get("phone"),
            email=user_extra.get("email"),
            init_cn_level=user_extra.get("init_cn_level", 1),
            points=user_extra.get("points", 0)
        )

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def create_attempt(db: Session, attempt_data: Dict[str, Any]) -> models.Attempt:
        """
        创建attempt记录

        Args:
            db: 数据库会话
            attempt_data: attempt数据字典

        Returns:
            创建的attempt对象
        """
        attempt = models.Attempt(**attempt_data)
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return attempt

    @staticmethod
    def submit_answers(
        db: Session,
        user: models.User,
        session_id: str,
        submissions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        提交答案并更新用户积分

        Args:
            db: 数据库会话
            user: 用户对象
            session_id: 会话ID
            submissions: 提交列表

        Returns:
            包含提交结果的字典
        """
        saved_attempts = []
        errors = []
        total_points_earned = 0

        for submission in submissions:
            try:
                # 构建attempt数据
                attempt_data = {
                    "person_id": user.user_id,
                    "exercise_id": uuid.UUID(submission["exerciseId"]),
                    "submitted_at": datetime.utcnow(),
                    "status": "submitted",
                    "total_score": submission["points"],
                    "attempt_meta": {
                        "user_answer": submission["userAnswer"],
                        "session_id": session_id
                    }
                }

                # 保存到数据库
                attempt = UserService.create_attempt(db, attempt_data)

                # 累加用户积分
                user.points = (user.points or 0) + submission["points"]
                total_points_earned += submission["points"]

                saved_attempts.append({
                    "attempt_id": str(attempt.id),
                    "exercise_id": submission["exerciseId"],
                    "points": submission["points"]
                })

            except Exception as e:
                # 如果单个题目保存失败，回滚当前事务并记录错误
                db.rollback()
                error_msg = f"Error saving attempt for exercise {submission['exerciseId']}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)
                continue

        # 提交用户积分更新
        if total_points_earned > 0:
            try:
                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                error_msg = f"Error updating user points: {str(e)}"
                print(error_msg)
                errors.append(error_msg)

        return {
            "total_submissions": len(submissions),
            "saved_count": len(saved_attempts),
            "total_points_earned": total_points_earned,
            "current_total_points": user.points,
            "attempts": saved_attempts,
            "errors": errors if errors else None
        }
