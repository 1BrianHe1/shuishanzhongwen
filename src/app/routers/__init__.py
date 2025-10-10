# app/routers/__init__.py
"""
路由模块

此模块已废弃，新的路由定义在 app.features 中
保留此文件仅为向后兼容
"""

from app.features import auth_router, user_router
from .generator_router import router as generator_router
from app.exercise_query.router import router as exercise_query_router

# 所有启用的路由
all_routers = [
    auth_router,         # 认证相关接口
    user_router,         # 用户相关接口
    generator_router,    # 题目生成器
    exercise_query_router  # 题目查询
]

__all__ = ["all_routers"]
