# 中文学习平台后端 - 完整项目文档

> 基于 FastAPI 的中文语言学习平台后端系统

---

## 📋 目录

1. [项目概述](#项目概述)
2. [快速开始](#快速开始)
3. [项目架构](#项目架构)
4. [数据库设计](#数据库设计)
5. [API 接口文档](#api-接口文档)
6. [开发指南](#开发指南)
7. [部署说明](#部署说明)
8. [测试指南](#测试指南)

---

## 项目概述

### 技术栈

- **框架**: FastAPI 0.100+
- **数据库**: PostgreSQL 13+
- **ORM**: SQLAlchemy 2.0+
- **认证**: JWT (python-jose)
- **密码加密**: bcrypt (passlib)
- **Python**: 3.8+

### 核心功能

- ✅ **用户认证系统**: 注册、登录、登出、JWT token 管理
- ✅ **题目管理系统**: 14种题型，支持听力、阅读、翻译
- ✅ **答案提交系统**: 批量提交答案，自动评分，积分累加
- ✅ **题目查询系统**: 按阶段、主题、课程筛选题目
- ✅ **积分系统**: 自动累加用户积分，支持积分查询

### 项目特点

- 📦 **模块化设计**: 功能模块独立，易于维护和扩展
- 🏗️ **三层架构**: Schema - Service - Router 分层设计
- 🔒 **安全可靠**: JWT认证 + Session管理 + 密码加密
- 📊 **完整数据模型**: 规范的数据库设计，支持复杂查询
- 🧪 **易于测试**: 业务逻辑与路由分离，单元测试友好

---

## 快速开始

### 环境要求

- Python 3.8+
- PostgreSQL 13+
- Docker & Docker Compose (可选)

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/your-org/chinese_platform_backend.git
cd chinese_platform_backend
```

#### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

#### 3. 安装依赖

```bash
pip install -r src/app/requirements.txt
```

#### 4. 配置环境变量

创建 `.env` 文件：

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/mydb
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

#### 5. 启动数据库 (Docker)

```bash
docker-compose up -d db
```

或手动启动 PostgreSQL 并创建数据库。

#### 6. 运行应用

```bash
cd src
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 7. 访问 API 文档

打开浏览器访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 项目架构

### 目录结构

```
src/app/
├── features/                   # 功能模块目录
│   ├── __init__.py            # 导出所有功能路由
│   ├── auth/                  # 认证功能模块
│   │   ├── __init__.py
│   │   ├── schemas.py         # 数据模型
│   │   ├── service.py         # 业务逻辑
│   │   └── router.py          # API路由
│   └── user/                  # 用户功能模块
│       ├── __init__.py
│       ├── schemas.py
│       ├── service.py
│       └── router.py
│
├── exercise_query/            # 题目查询模块
│   ├── schemas.py
│   ├── service.py
│   ├── router.py
│   ├── crud.py
│   ├── formatter.py
│   └── models.py
│
├── routers/                   # 路由目录
│   ├── __init__.py           # 路由注册
│   └── generator_router.py   # 题目生成器
│
├── core/                      # 核心工具
│   ├── security.py           # 密码加密、JWT
│   └── otp.py                # OTP验证码
│
├── service/                   # 通用服务层
│   └── exercise_service.py
│
├── utils/                     # 工具函数
│   ├── util.py
│   └── avg_time.py
│
├── models.py                  # 数据库模型
├── schemas.py                 # 通用数据模型
├── crud.py                    # 通用CRUD操作
├── database.py                # 数据库配置
└── main.py                    # 应用入口
```

### 架构设计

#### 三层架构模式

```
┌─────────────────┐
│  Router Layer   │  ← API接口定义、参数验证
└────────┬────────┘
         │
┌────────▼────────┐
│  Service Layer  │  ← 业务逻辑、数据处理
└────────┬────────┘
         │
┌────────▼────────┐
│  Database/ORM   │  ← 数据持久化
└─────────────────┘
```

#### 数据流

```
Client Request
    ↓
Router (参数验证)
    ↓
Service (业务处理)
    ↓
Database (数据存储)
    ↓
Service (数据转换)
    ↓
Router (响应格式化)
    ↓
Client Response
```

---

## 数据库设计

### Schema 组织

- **people**: 用户相关表（users, users_session, verification_code）
- **content_new**: 内容相关表（phases, topics, lessons, words, exercises）
- **events**: 事件记录表（attempt, sessions）

### 核心数据表

#### 1. people.users - 用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | UUID | 主键 |
| user_name | TEXT | 用户名 |
| password_hash | TEXT | 密码哈希 |
| email | TEXT | 邮箱 |
| phone | TEXT | 手机号 |
| country | TEXT | 国家 |
| job | TEXT | 职业 |
| init_cn_level | TEXT | 初始中文水平 |
| points | INTEGER | 用户积分 |
| reg_time | TIMESTAMPTZ | 注册时间 |

#### 2. people.users_session - 会话表

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | UUID | 主键 |
| user_id | UUID | 用户ID（外键） |
| token | TEXT | JWT token |
| login_time | TIMESTAMPTZ | 登录时间 |
| logout_time | TIMESTAMPTZ | 登出时间（NULL表示在线） |

#### 3. content_new.exercises - 题目表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| exercise_type_id | UUID | 题型ID（外键） |
| word_id | UUID | 词语ID（外键） |
| parent_exercise_id | UUID | 父题ID（用于大题） |
| prompt | TEXT | 题干 |
| metadata | JSONB | 题目元数据（选项、答案等） |
| difficulty_level | SMALLINT | 难度等级 |
| display_order | INT | 显示顺序 |

#### 4. events.attempt - 答题记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| person_id | UUID | 用户ID（外键） |
| exercise_id | UUID | 题目ID（外键→content_new.exercises） |
| submitted_at | TIMESTAMPTZ | 提交时间 |
| status | ENUM | 状态（submitted/graded） |
| total_score | NUMERIC | 得分 |
| attempt_meta | JSONB | 答题元数据（用户答案、session_id等） |

### 数据库 ERD

详见 `题型数据库设计.md` 文件中的完整 ERD 图。

---

## API 接口文档

### 认证接口 (`/auth`)

#### 1. 用户登录

**接口**: `POST /auth/login`

**请求参数**:
```json
{
  "user_name": "test_user",
  "password": "test123"
}
```

**响应示例**:
```json
{
  "code": 1,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "session_id": "ad05c5ed-8f4a-4c3e-9d12-8b5a7f3e6c2d",
    "user_info": {
      "user_id": "8ba7d3e4-0f38-40dd-af14-e56f02134136",
      "user_name": "test_user",
      "email": "test@example.com",
      "points": 48
    }
  }
}
```

#### 2. 用户登出

**接口**: `POST /auth/logout`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:
```json
{
  "code": 1,
  "message": "登出成功"
}
```

#### 3. 获取当前用户信息

**接口**: `GET /auth/me`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:
```json
{
  "code": 1,
  "message": "success",
  "data": {
    "user_id": "8ba7d3e4-0f38-40dd-af14-e56f02134136",
    "user_name": "test_user",
    "email": "test@example.com"
  }
}
```

---

### 用户接口 (`/user`)

#### 1. 用户注册

**接口**: `POST /user/register`

**请求参数**:
```json
{
  "user_name": "new_user",
  "password": "password123",
  "email": "user@example.com",
  "phone": "+86 138 0000 0000",
  "country": "中国",
  "job": "学生",
  "init_cn_level": "初级"
}
```

**响应示例**:
```json
{
  "code": 1,
  "message": "注册成功",
  "data": {
    "user_info": {
      "user_id": "...",
      "user_name": "new_user",
      "email": "user@example.com"
    }
  }
}
```

#### 2. 提交答案

**接口**: `POST /user/submit-answers`

**功能**: 批量提交答案，自动累加积分

**请求参数**:
```json
{
  "sessionId": "ad05c5ed-8f4a-4c3e-9d12-8b5a7f3e6c2d",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "submissionList": [
    {
      "exerciseId": "1fe2d43b-0fae-49ba-8650-8f8321e7604f",
      "userAnswer": true,
      "points": 10
    },
    {
      "exerciseId": "ae4233a3-ee4c-4371-a464-a5687778d00d",
      "userAnswer": "A",
      "points": 15
    }
  ]
}
```

**响应示例**:
```json
{
  "code": 1,
  "message": "答案提交成功",
  "data": {
    "total_submissions": 2,
    "saved_count": 2,
    "total_points_earned": 25,
    "current_total_points": 73,
    "attempts": [
      {
        "attempt_id": "e4cc0c14-a666-44ab-b08b-3f47d7aaaeca",
        "exercise_id": "1fe2d43b-0fae-49ba-8650-8f8321e7604f",
        "points": 10
      },
      {
        "attempt_id": "f1743d19-8aad-4cfa-90e8-11b4141dd2ee",
        "exercise_id": "ae4233a3-ee4c-4371-a464-a5687778d00d",
        "points": 15
      }
    ],
    "errors": null
  }
}
```

**注意事项**:
- `exerciseId` 必须是数据库中存在的题目ID
- `points` 既是题目分数，也会累加到用户总积分
- 积分累加与答案保存在同一事务中，保证一致性

---

### 题目接口 (`/queryquestion`)

#### 1. 获取题目类型

**接口**: `GET /api/questions/types`

**响应示例**:
```json
{
  "questionTypes": [
    {
      "type": "LISTEN_IMAGE_TRUE_FALSE",
      "name": "听录音，看图判断",
      "requiresAudio": true,
      "requiresImage": true,
      "hasOptions": true,
      "skillCategory": "听力"
    }
  ]
}
```

#### 2. 生成题目集合

**接口**: `POST /api/questions/generate`

**请求参数**:
```json
{
  "lessonId": "lesson_001",
  "duration": 1800,
  "exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE", "READ_SENTENCE_TF"],
  "count": 5,
  "phaseName": "1A",
  "topicName": "生活",
  "lessonName": "性格"
}
```

**响应示例**:
```json
{
  "phaseId": "1A",
  "topicId": "生活",
  "duration": 1800,
  "count": 2,
  "sessionId": "d0a3f49a-4913-4e0c-b311-f28bbdec2944",
  "exercises": [
    {
      "exerciseId": "1fe2d43b-0fae-49ba-8650-8f8321e7604f",
      "exerciseType": "LISTEN_IMAGE_TRUE_FALSE",
      "content": {
        "prompt": "请听录音，再看图片，判断陈述是否正确。",
        "audioUrl": "audios/2025/09/23/53/53607e37eb60.wav",
        "listeningText": "同学在教室里看书。",
        "imageUrl": "images/2025/09/23/3d/3dac5accc39635.png"
      },
      "correctAnswer": true
    }
  ]
}
```

### 支持的题目类型

系统支持 **14 种题型**，分为三大技能类别：

#### 听力类题目

1. **LISTEN_IMAGE_TRUE_FALSE** - 听录音，看图判断
2. **LISTEN_IMAGE_MC** - 听录音，看图选择
3. **LISTEN_IMAGE_MATCH** - 听录音，看图配对
4. **LISTEN_SENTENCE_QA** - 听录音，句子问答
5. **LISTEN_SENTENCE_TF** - 听录音，句子判断

#### 阅读类题目

6. **READ_IMAGE_TRUE_FALSE** - 阅读，图片判断
7. **READ_IMAGE_MATCH** - 阅读，看图配对
8. **READ_DIALOGUE_MATCH** - 阅读，对话配对
9. **READ_WORD_GAP_FILL** - 阅读，句子填空
10. **READ_SENTENCE_COMPREHENSION_CHOICE** - 句子理解(选择)
11. **READ_SENTENCE_TF** - 句子理解(判断)
12. **READ_PARAGRAPH_COMPREHENSION** - 段落理解
13. **READ_WORD_ORDER** - 连词成句

#### 翻译类题目

14. **READ_SENTENCE_TRANSLATION** - 句子翻译

详细的题型规范见 `题目设计.md` 文件。

---

## 开发指南

### 添加新功能模块

#### 1. 创建模块目录

```bash
mkdir -p src/app/features/your_module
cd src/app/features/your_module
touch __init__.py schemas.py service.py router.py
```

#### 2. 定义数据模型 (schemas.py)

```python
from pydantic import BaseModel

class YourRequest(BaseModel):
    field1: str
    field2: int

class YourResponse(BaseModel):
    result: str
```

#### 3. 实现业务逻辑 (service.py)

```python
from sqlalchemy.orm import Session
from app import models

class YourService:
    @staticmethod
    def your_method(db: Session, param: str):
        """业务逻辑处理"""
        # 查询数据库
        result = db.query(models.YourModel).filter(...).first()

        # 处理逻辑
        processed = process_data(result)

        return processed
```

#### 4. 定义 API 路由 (router.py)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from .schemas import YourRequest, YourResponse
from .service import YourService

router = APIRouter(prefix="/your-prefix", tags=["Your Module"])

@router.post("/endpoint", response_model=YourResponse)
def your_endpoint(
    request: YourRequest,
    db: Session = Depends(get_db)
):
    """API 端点文档"""
    result = YourService.your_method(db, request.field1)
    return {"code": 1, "message": "success", "data": result}
```

#### 5. 导出模块 (__init__.py)

```python
from .router import router
from .service import YourService

__all__ = ["router", "YourService"]
```

#### 6. 注册路由

在 `features/__init__.py` 中：
```python
from .your_module import router as your_router
__all__ = [..., "your_router"]
```

在 `routers/__init__.py` 中：
```python
from app.features import ..., your_router
all_routers = [..., your_router]
```

### 使用认证保护接口

```python
from app.features.auth.router import get_current_user

@router.post("/protected")
def protected_endpoint(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.user_id
    # 只有登录用户才能访问
    return {"user_id": user_id}
```

### 数据库操作最佳实践

```python
from sqlalchemy.orm import Session
from app import models

def create_record(db: Session, data: dict):
    """创建记录"""
    record = models.YourModel(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def update_record(db: Session, record_id: str, updates: dict):
    """更新记录"""
    record = db.query(models.YourModel).filter(
        models.YourModel.id == record_id
    ).first()

    if not record:
        return None

    for key, value in updates.items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return record
```

---

## 部署说明

### Docker 部署

#### 1. 使用 Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

#### 2. 单独构建镜像

```bash
# 构建镜像
docker build -t chinese-platform-backend .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e SECRET_KEY=... \
  chinese-platform-backend
```

### 生产环境配置

#### 环境变量

```env
# 数据库
DATABASE_URL=postgresql://user:pass@host:port/dbname

# 安全
SECRET_KEY=<生成一个强密钥>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# 应用
ENV=production
DEBUG=False
```

#### 生成安全密钥

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name api.yourplatform.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 测试指南

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-cov httpx

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_auth.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

### 测试示例

#### 单元测试 (Service 层)

```python
# tests/test_services/test_auth_service.py
import pytest
from sqlalchemy.orm import Session
from app.features.auth.service import AuthService

def test_authenticate_user_success(db: Session):
    """测试用户认证成功"""
    user = AuthService.authenticate_user(
        db, "test_user", "test123"
    )
    assert user is not None
    assert user.user_name == "test_user"

def test_authenticate_user_wrong_password(db: Session):
    """测试密码错误"""
    user = AuthService.authenticate_user(
        db, "test_user", "wrong_password"
    )
    assert user is None
```

#### 集成测试 (API 层)

```python
# tests/test_routers/test_auth.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    """测试登录成功"""
    response = client.post("/auth/login", json={
        "user_name": "test_user",
        "password": "test123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1
    assert "access_token" in data["data"]

def test_login_wrong_credentials():
    """测试登录失败"""
    response = client.post("/auth/login", json={
        "user_name": "test_user",
        "password": "wrong"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
```

### API 测试命令

详细的 curl 测试命令见 `API测试命令集合.md` 文件。

---

## 常见问题

### Q: 如何重置数据库？

A: 使用数据库迁移工具或手动执行 SQL 脚本：

```bash
# 使用 Alembic (推荐)
alembic downgrade base
alembic upgrade head

# 或直接删除重建
psql -U postgres -c "DROP DATABASE mydb;"
psql -U postgres -c "CREATE DATABASE mydb;"
psql -U postgres -d mydb -f db/initdb/init.sql
```

### Q: 如何修改积分逻辑？

A: 修改 `features/user/service.py` 中的 `submit_answers` 方法。

### Q: 如何添加新的题目类型？

A:
1. 在数据库 `content_new.exercise_types` 表中添加新类型
2. 在 `题目设计.md` 中定义新题型的数据结构
3. 在题目生成器中添加生成逻辑
4. 在题目格式化器中添加格式化逻辑

### Q: 外键约束错误怎么办？

A: 确保 `exerciseId` 来自 `content_new.exercises` 表。参考 `FOREIGN_KEY_FIX_SUMMARY.md`。

---

## 项目历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 2.0.0 | 2025-10-10 | 项目结构重构，采用模块化设计 |
| 1.5.0 | 2025-10-10 | 添加积分累加功能 |
| 1.4.0 | 2025-10-09 | 修复外键约束问题 |
| 1.0.0 | 2025-10-01 | 初始版本发布 |

---

## 相关文档

- **Backend-structure.md** - 后端组织形式详解
- **PROJECT_STRUCTURE.md** - 项目结构重构文档
- **REFACTORING_SUMMARY.md** - 重构总结
- **题目设计.md** - 题型规范
- **题型数据库设计.md** - 数据库 ERD
- **API_使用说明.md** - 详细 API 文档
- **API测试命令集合.md** - 测试命令
- **QUICK_REFERENCE.md** - 快速参考指南
- **submit_answers_api_doc.md** - 提交答案接口详解
- **POINTS_FEATURE_TEST.md** - 积分功能测试报告

---

## 贡献指南

### 代码风格

- 遵循 PEP 8 Python 代码规范
- 使用类型注解
- 编写清晰的文档字符串
- 保持函数职责单一

### 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型 (type):
- feat: 新功能
- fix: 修复bug
- docs: 文档修改
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建/工具修改

### Pull Request 流程

1. Fork 项目
2. 创建功能分支
3. 编写代码和测试
4. 提交 Pull Request
5. 等待代码审查

---

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

---

## 联系方式

- **项目主页**: https://github.com/your-org/chinese_platform_backend
- **问题反馈**: https://github.com/your-org/chinese_platform_backend/issues
- **邮箱**: support@yourplatform.com

---

## 致谢

感谢所有为本项目做出贡献的开发者！

---

**最后更新**: 2025-10-10
