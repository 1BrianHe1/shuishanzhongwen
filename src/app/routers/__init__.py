# app/routers/__init__.py
from .fetch import router as fetch_router
from .generator import router as generator_router_old
from .health import router as health_router
from .user import router as user_router  # 新增
from .auth import router as auth_router  # 新增
from .generator_router import router as new_generator_router
all_routers = [
    #fetch_router,
    #generator_router_old,
    #health_router,
    user_router,
    auth_router,
    new_generator_router
]
