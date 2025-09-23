# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy
# from flask_migrate import Migrate
# from flask_jwt_extended import JWTManager

# db = SQLAlchemy()
# migrate = Migrate()
# jwt = JWTManager()

# def create_app(config_class=None):
#     app = Flask(__name__, static_folder='../media', static_url_path='/media')
#     if config_class is None:
#         from .config import Config
#         app.config.from_object(Config)
#     else:
#         app.config.from_object(config_class)

#     db.init_app(app)
#     migrate.init_app(app, db)
#     jwt.init_app(app)

#     # 注册路由蓝图
#     from .routers.auth import bp as auth_bp
#     app.register_blueprint(auth_bp)

#     # 注册你现有的路由（示例）
#     from .routers.health import bp as health_bp
#     app.register_blueprint(health_bp)

#     # 其他初始化（logging、cors 等）按需添加

#     return app
