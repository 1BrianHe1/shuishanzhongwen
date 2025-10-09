# app/routers/__init__.py
from .fetch import router as fetch_router
from .generator import router as generator_router_old
from .health import router as health_router
from .user import router as user_router  # 新增
from .auth import router as auth_router  # 新增
from .generator_router import router as new_generator_router
from .questions import router as questions_router  # 旧的题目路由
from ..question import question_router  # 新的重构后的question模块路由
from app.exercise_query.router import router as question_query_router

all_routers = [
    #fetch_router,
    #generator_router_old,
    #health_router,
    user_router,
    auth_router,
    new_generator_router,
    # questions_router  # 注释掉旧的题目路由
    question_query_router
]
