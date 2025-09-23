# **项目后端组织形式**



本文档基于现有目录与功能（注册、登录、JWT、会话/Session 持久化）的结构，说明**每个文件的作用、相互依赖关系、数据流与接口约定**。



------

​	



## **1.** **app/**

## **应用目录结构**



```
app/
├─ __init__.py
├─ main.py                     # 应用入口：创建 FastAPI、注册路由、(dev)自动建表
├─ requirements.txt            # 依赖
├─ database.py                 # 数据库引擎/会话/基础模型Base
├─ models/                     # ORM 模型（people.users / people.users_session）
│  ├─ __init__.py
│  ├─ user.py                  # people."users" 表映射
│  └─ session.py               # people.users_session 表映射
├─ core/
│  └─ security.py              # 密码哈希、JWT 生成与校验、读取 .env
├─ crud.py                     # 数据库操作封装（User / Session）
├─ schemas.py                  # Pydantic 数据模型（请求/响应）
└─ routers/
   ├─ __init__.py              # 汇总并导出 all_routers
   ├─ health.py                # 健康检查（已存在）
   ├─ fetch.py                 # 业务相关（已存在）
   ├─ generator.py             # 业务相关（已存在）
   ├─ user.py                  # 只保留 “注册” 接口
   └─ auth.py                  # 登录/登出/鉴权（整合 Session 持久化）
```



------



## **2. 核心模块说明（新增/改动）**

### **2.1** 

### **app/database.py**

**作用**：数据库连接与会话管理。



- 从 .env 读取 DATABASE_URL 创建 engine。
- SessionLocal：提供事务会话。
- Base = declarative_base()：所有 ORM 模型的基类。
- get_db()：FastAPI 依赖注入，确保一次请求一个 DB 会话，结束自动关闭。

> 有的 CRUD 与路由都通过 Depends(get_db) 获取数据库会话。



------



### **2.2** 

### **app/models/user.py**

### **（**

### **people.“user”**

### **）**

**作用**：映射用户表到 ORM 模型。



- **表**：people."users"。

- **字段解释**：

  

  - user_id: uuid 主键（默认 uuid_generate_v4() 或 gen_random_uuid()）
  - user_name: text
  - country, job, phone, email, init_cn_level: text
  - reg_time: timestamptz 默认 now()
  - password_hash: text（**新增**，用于保存加密后的密码）

> 数据插入/查询均通过此模型，确保 __table_args__ = {"schema": "people"}。



------



### **2.3** 

### **app/models/session.py**

### **（**

### **people.user_session**

### **）**

**作用**：登录状态持久化（Session 记录）。



- **表**：people.user_session

- **字段**：

  

  - session_id: uuid 主键（应用层默认 uuid.uuid4）
  - user_id: uuid 外键 → people."user"(user_id)
  - token: text（保存当前 JWT）
  - login_time: timestamptz 默认 now()
  - logout_time: timestamptz（空表示在线；登出时写入）

> 用来判断 token 是否仍“在线”（未登出）。



------



### **2.4** 

### **app/core/security.py**

**作用**：安全组件（读取环境变量、密码哈希、JWT）。



- 读取 .env：

  

  - SECRET_KEY（JWT 签名密钥）
  - ALGORITHM（如 HS256）
  - ACCESS_TOKEN_EXPIRE_MINUTES（默认有效期分钟）

  

- 提供：

  

  - hash_password() / verify_password()：基于 passlib[bcrypt]。
  - create_access_token(data, expires_delta)：生成 JWT（含 exp）。
  - verify_token(token)：校验并返回 payload（失败返回 None）。

> 所有登录相关逻辑都依赖这里的配置。把密钥放 .env 避免硬编码。



------



### **2.5** 

### **app/crud.py**

**作用**：封装所有数据库读写（便于复用/单测/解耦路由）。



- 用户：

  

  - get_user_by_userid(db, userid)：按“账号标识”查用户。**通常我们把 userid 映射到 user_name**；如需用 email 登录，改查询条件即可。
  - create_user(db, userid, raw_password, user_extra)：写入 people."user"；内部进行 bcrypt 哈希，并映射 country/job/phone/email/init_cn_level 等字段，commit + refresh 后 **return user**。

  

- 会话：

  

  - create_user_session(db, user_id, token)：登录成功后记录 session。
  - logout_user_session(db, token)：将该 token 的 logout_time 置为当前时间。
  - get_user_by_token(db, token)：只返回**未登出**的会话（在线状态）。

  



------



### **2.6** 

### **app/schemas.py**

**作用**：请求/响应的 Pydantic 模型（自动校验 & OpenAPI 文档）。



- LoginRequest：userid, password。
- RegisterRequest：userid, password，以及可选 user_name, country, job, phone, email, init_cn_level（确保与前端对齐）。
- ResponseModel：统一响应结构：code, message, data（内含 user_info 或 access_token 等）。



> 任何未在 schema 定义的字段，默认会被忽略；要存就必须在 schema 中声明。



------



### **2.7** 

### **app/routers/user.py**

### **（**

### **只保留注册**

### **）**

**作用**：POST /user/register



- 流程：

  

  1. get_user_by_userid 检查账号是否存在（按 user_name == userid）。
  2. 不存在则 create_user：写入 people."user"（含 password_hash）。
  3. 返回统一结构，data.user_info 中可回传 user_id/user_name/country/...。

  

> 注册只写用户表，不创建 session（避免注册即登录的副作用）。



------



### **2.8** 

### **app/routers/auth.py**

### **（**

### **整合 Session 的登录/登出/鉴权**

### **）**

**作用**：认证与“登录状态”管理。



- oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

  用于 Swagger 的 Authorize 按钮与 Bearer <token> 解析（tokenUrl 可改为你的登录路径）。

- **POST /auth/login**

  

  1. 按 userid 查询用户（通常匹配 user_name）。
  2. verify_password 校验密码。
  3. create_access_token 生成 JWT（payload 至少含 user_id、userid）。
  4. create_user_session 将 token 写入 people.user_session。
  5. 返回：

  



```
{
  "code": 1,
  "message": "success",
  "data": {
    "access_token": "...",
    "token_type": "bearer",
    "user_info": { "user_name": "..." }
  }
}
```



- 

- **POST /auth/logout**（需要 Authorization: Bearer <token>）

  调用 logout_user_session 设置 logout_time，使 token 失效（服务端层面登出）。

- **GET /auth/me**（受保护）

  通过 Depends(oauth2_scheme) 取出 token → get_user_by_token 检查该 token 是否在线（未登出）→ 返回当前用户基本信息（示例为 user_id；可改为完整 user_info）。





> 受保护接口的“已登录”判断，以**session 表 + token**为准（JWT 通过但 session 里已登出也会被拒绝）。



------



### **2.9** 

### **app/routers/__init__.py**

**作用**：汇总所有路由，统一在 main.py 里 include_router。



```
from .health import router as health_router
from .fetch import router as fetch_router
from .generator import router as generator_router
from .user import router as user_router
from .auth import router as auth_router

all_routers = [health_router, fetch_router, generator_router, user_router, auth_router]
```





------



### **2.10** 

### **app/main.py**

**作用**：应用入口。



- 创建 FastAPI 实例。
- （开发期可选）在 startup 事件中 Base.metadata.create_all(bind=engine) 自动建表。**生产建议使用 Alembic 做迁移**。
- 遍历 all_routers 注册路由。
- 可保留你原本的其它初始化逻辑、健康检查等。





------



## **3. 数据库与表（现状）**

- **Schema**：people

- **用户表**：people."user"

  

  - 你提供的字段 + password_hash（登录必需）。

  

- **会话表**：people.user_session

  

  - 存储每次登录的 token、login_time，登出时写 logout_time。

  

> 依赖扩展：uuid-ossp（uuid_generate_v4()）或 pgcrypto（gen_random_uuid()）。在初始化 SQL 中 CREATE EXTENSION。



------





## **4. 认证与“登录状态”的判定**

- **认证**：JWT 验证签名与过期（security.verify_token）。
- **登录状态**：token 必须在 people.user_session 中存在且 logout_time IS NULL；否则视为未登录/已登出。
- **Swagger 授权**：OAuth2PasswordBearer(tokenUrl=...) 仅影响 /docs 的 Authorize 引导，不影响运行时解析。





------





## **5. 典型请求流**

**注册** POST /user/register

前端 → 路由(user.py) → CRUD.create_user → models.user → DB(commit) → 返回 user_info



**登录** POST /auth/login

前端 → 路由(auth.py) → CRUD.get_user_by_userid & 验证密码 → security.create_access_token → CRUD.create_user_session → 返回 access_token



**受保护接口** GET /auth/me

前端携带 Authorization: Bearer <token> → 路由(auth.py) get_current_user → 先抽出 token → CRUD.get_user_by_token(校验在线) → 放行并返回数据



**登出** POST /auth/logout

前端携带 token → 路由(auth.py) → CRUD.logout_user_session(写入 logout_time) → 返回 success



------





## **7. 配置要点（.env）**





示例：

```
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/mydb
SECRET_KEY="your-super-secret"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60
```



- SECRET_KEY：务必区分开发/生产，勿入库到公开仓库。
- DATABASE_URL：docker-compose 下通常主机为服务名（如 postgres）。





