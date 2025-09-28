# app/routers/user.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, crud
from ..database import get_db
from ..core import security

router = APIRouter(prefix="/user", tags=["user"])

@router.post("/register", response_model=schemas.ResponseModel)
def register(request: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing = crud.get_user_by_username(db, request.user_name)
    if existing:
        return {"code": 0, "message": "账号已存在", "data": None}

    user = crud.create_user(
        db,
        user_name=request.user_name,
        raw_password=request.password,
        user_extra={
            "country": request.country if hasattr(request, "country") else None,
            "job": request.job if hasattr(request, "job") else None,
            "phone": request.phone if hasattr(request, "phone") else None,
            "email": request.email if hasattr(request, "email") else None,
            # "init_cn_level": request.init_cn_level if hasattr(request, "init_cn_level") else None,
            "init_cn_level": request.init_cn_level if hasattr(request, "init_cn_level") and request.init_cn_level is not None else 1,
            "points": 0,
        }
    )
    return {
        "code": 1,
        "message": "success",
        # "data": {
        #     "user_info": {
        #         "user_id": str(user.user_id),
        #         "user_name": user.user_name,
        #         "email": user.email,
        #         "phone": user.phone,
        #         "country": user.country,
        #         "job": user.job,
        #         "init_cn_level": user.init_cn_level,
        #         "reg_time": user.reg_time.isoformat() if user.reg_time else None,
        #         "points": user.points
        #     }
        # }
    }
