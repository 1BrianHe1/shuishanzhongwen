# app/features/__init__.py
"""
Features module - 功能模块

所有业务功能模块都放在这里，每个模块包含：
- schemas.py: 数据模型和请求/响应结构
- service.py: 业务逻辑服务层
- router.py: API路由定义
"""

from .auth import router as auth_router
from .user import router as user_router

__all__ = ["auth_router", "user_router"]
