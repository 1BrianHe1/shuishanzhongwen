# from fastapi import FastAPI
# from .routers import generator, health, fetch

# app = FastAPI(title="Generate Listen + Image TF API")

# app.include_router(generator.router)
# app.include_router(health.router)
# app.include_router(fetch.router)
# app/main.py
from fastapi import FastAPI
from .database import engine, Base
from .routers import all_routers

app = FastAPI(title="My App")

# 在启动时自动建表（开发/测试环境可用；生产建议用 Alembic）
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# 注册路由
for r in all_routers:
    app.include_router(r)

# 可保留你的现有路由（fetch/generator/health）不变
