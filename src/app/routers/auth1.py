# app/routers/auth.py (新增/修改)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from app import schemas, crud
from app.database import get_db
from app.core import security
from app.core import otp as otp_core
from app import models

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")  # Swagger Authorize 提示

# 发送验证码（注册 / 登录）
@router.post("/send_code", response_model=schemas.ResponseModel)
def send_code(request: schemas.SendCodeRequest, db: Session = Depends(get_db)):
    # 对 recipient 的基本检查可自行增强（邮箱格式、手机号正则）
    code, err = crud.create_verification_code(db, request.channel, request.recipient, request.action)
    if err:
        return {"code": 0, "message": err, "data": None}

    # TODO: 在生产中接入真实邮件/SMS 发送，这里仅示例。
    data = {"sent_to": request.recipient, "channel": request.channel, "action": request.action}
    if otp_core.should_echo_code_in_response():
        data["echo_code"] = code  # 仅开发调试用
    return {"code": 1, "message": "success", "data": data}

# 账号密码登录
@router.post("/login", response_model=schemas.ResponseModel)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_userid(db, request.userid)
    if not user:
        return {"code": 0, "message": "用户不存在", "data": None}
    if not security.verify_password(request.password, user.password_hash):
        return {"code": 0, "message": "用户名或密码错误", "data": None}

    token = security.create_access_token({"user_id": str(user.user_id), "user_name": user.user_name})
    crud.create_user_session(db, str(user.user_id), token)

    return {
        "code": 1,
        "message": "success",
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "user_info": {
                "user_id": str(user.user_id),
                "user_name": user.user_name
            }
        }
    }

# 验证码登录（手机/邮箱）
@router.post("/login_code", response_model=schemas.ResponseModel)
def login_by_code(request: schemas.LoginByCodeRequest, db: Session = Depends(get_db)):
    # 用 email 或 phone 找用户
    if request.channel == "email":
        user = db.query(models.User).filter(models.User.email == request.recipient).first()
    else:
        user = db.query(models.User).filter(models.User.phone == request.recipient).first()

    if not user:
        return {"code": 0, "message": "用户不存在", "data": None}

    ok = crud.verify_and_consume_code(db, request.channel, request.recipient, "login", request.code)
    if not ok:
        return {"code": 0, "message": "验证码无效或已过期", "data": None}

    token = security.create_access_token({"user_id": str(user.user_id), "userid": user.user_name})
    crud.create_user_session(db, str(user.user_id), token)

    return {
        "code": 1,
        "message": "success",
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "user_info": {
                "user_id": str(user.user_id),
                "user_name": user.user_name
            }
        }
    }
