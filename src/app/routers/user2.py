# app/routers/user.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import schemas, crud
from app.database import get_db

router = APIRouter(prefix="/user", tags=["user"])

@router.post("/register", response_model=schemas.ResponseModel)
def register(request: schemas.RegisterRequest, db: Session = Depends(get_db)):
    # 校验账号是否重复（以 user_name 作为登录名）
    if crud.get_user_by_userid(db, request.userid):
        return {"code": 0, "message": "账号已存在", "data": None}

    # 需要用户提供 email 或 phone，用于发验证码的渠道
    if request.code_channel == "email":
        if not request.email:
            return {"code": 0, "message": "请提供 email 以验证", "data": None}
        recipient = request.email
    else:
        if not request.phone:
            return {"code": 0, "message": "请提供 phone 以验证", "data": None}
        recipient = request.phone

    # 校验验证码（action='register'）
    ok = crud.verify_and_consume_code(db, request.code_channel, recipient, "register", request.code)
    if not ok:
        return {"code": 0, "message": "验证码无效或已过期", "data": None}

    # 创建用户
    user = crud.create_user(
        db,
        userid=request.userid,
        raw_password=request.password,
        user_extra={
            "user_name": request.user_name,
            "country": request.country if hasattr(request, "country") else None,
            "job": request.job if hasattr(request, "job") else None,
            "phone": request.phone if hasattr(request, "phone") else None,
            "email": request.email if hasattr(request, "email") else None,
            # "init_cn_level": request.init_cn_level if hasattr(request, "init_cn_level") else None,
            "init_cn_level": request.init_cn_level if hasattr(request, "init_cn_level") and request.init_cn_level is not None else 0,
            "points": 0,
        }
    )

    return {
        "code": 1,
        "message": "success",
        "data": {
            "user_info": {
                "user_id": str(user.user_id),
                "user_name": user.user_name,
                "email": user.email,
                "phone": user.phone
            }
        }
    }