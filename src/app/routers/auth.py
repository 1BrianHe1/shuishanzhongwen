# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from app import crud, schemas
from app.database import get_db
from app.core import security

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# 登录接口
@router.post("/login", response_model=schemas.ResponseModel)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_userid(db, request.userid)
    if not user:
        return {"code": 0, "message": "用户不存在", "data": None}
    if not security.verify_password(request.password, user.password_hash):
        return {"code": 0, "message": "用户名或密码错误", "data": None}

    token = security.create_access_token({"user_id": str(user.user_id), "userid": user.user_name})
    crud.create_user_session(db, str(user.user_id), token)

    return {
        "code": 1,
        "message": "success",
        "data": {"access_token": token, "token_type": "bearer", "user_info": {"user_name": user.user_name,"points":user.points}},
    }

# 登出接口
@router.post("/logout", response_model=schemas.ResponseModel)
def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    session = crud.logout_user_session(db, token)
    if not session:
        return {"code": 0, "message": "Token 无效或已登出", "data": None}
    return {"code": 1, "message": "success", "data": None}

# 受保护接口依赖
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    session = crud.get_user_by_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="未认证或已登出")
    return session

# 测试受保护接口
@router.get("/me", response_model=schemas.ResponseModel)
def read_me(current_session=Depends(get_current_user)):
    return {
        "code": 1,
        "message": "success",
        "data": {"user_id": str(current_session.user_id)}
    }
