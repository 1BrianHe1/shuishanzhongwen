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
import os
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="My App")
MEDIA_ROOT=os.getenv("MEDIA_ROOT")
app.mount("/media",StaticFiles(directory=MEDIA_ROOT),name="media")

# 在启动时自动建表（开发/测试环境可用；生产建议用 Alembic）
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# 注册路由
for r in all_routers:
    app.include_router(r)

# 可保留你的现有路由（fetch/generator/health）不变

# from fastapi import FastAPI
# from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
# from starlette.staticfiles import StaticFiles
# from swagger_ui_bundle import swagger_ui_3_path  # 🔥 本地自带的 swagger 资源目录

# app = FastAPI(openapi_url="/openapi.json", docs_url=None, redoc_url=None)

# # 把 swagger 静态文件挂到 /static/swagger
# app.mount("/static/swagger", StaticFiles(directory=swagger_ui_3_path), name="swagger")

# @app.get("/docs", include_in_schema=False)
# def custom_swagger_ui_html():
#     return get_swagger_ui_html(
#         openapi_url=app.openapi_url,
#         title="API Docs",
#         swagger_js_url="/static/swagger/swagger-ui-bundle.js",
#         swagger_css_url="/static/swagger/swagger-ui.css",
#         swagger_ui_standalone_preset_js_url="/static/swagger/swagger-ui-standalone-preset.js",
#     )

# @app.get("/docs/oauth2-redirect", include_in_schema=False)
# def swagger_ui_redirect():
#     return get_swagger_ui_oauth2_redirect_html()