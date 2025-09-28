# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Development (local)
cd src && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production (Docker)
docker-compose up -d
```

### Database Operations
```bash
# Start PostgreSQL via Docker Compose
docker-compose up -d db

# Database is accessible on port 5433 (mapped from container port 5432)
# Connection details from .env file
```

### Dependencies
```bash
# Install dependencies (use virtual environment)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r src/app/requirements.txt
```

## Architecture Overview

This is a **FastAPI-based Chinese language learning platform backend** with the following key architectural components:

### Database Schema (`people` schema)
- **User Management**: `people.users` table handles user registration, authentication, and profile data
- **Session Management**: `people.users_session` table manages login sessions and JWT token persistence
- **Verification System**: `people.verification_code` table handles email/phone verification for registration/login

### Application Structure
```
src/app/
├── main.py              # FastAPI app entry point
├── database.py          # SQLAlchemy engine, session, and dependency injection
├── models.py            # Database models (User, UserSession, VerificationCode)
├── schemas.py           # Pydantic models for request/response validation
├── crud.py              # Database operations layer
├── core/
│   ├── security.py      # JWT, password hashing, environment config
│   └── otp.py           # OTP/verification code handling
├── routers/
│   ├── auth.py          # Authentication endpoints (/auth/login, /auth/logout, /auth/me)
│   ├── user.py          # User management (/user/register)
│   ├── generator_router.py # Content generation features
│   └── [legacy routers] # fetch.py, health.py, generator.py
└── service/             # Business logic layer
    └── exercise_service.py
```

### Authentication Flow
1. **Registration**: POST `/user/register` → Creates user with hashed password
2. **Login**: POST `/auth/login` → Validates credentials, generates JWT, creates session record
3. **Protected Routes**: Use `oauth2_scheme` dependency → Validates JWT + checks active session in database
4. **Logout**: POST `/auth/logout` → Marks session as logged out (sets `logout_time`)

### Key Design Patterns
- **Database Session Management**: Uses dependency injection (`Depends(get_db)`) for database sessions
- **Dual Authentication**: JWT token validation + database session persistence for logout capability
- **Schema Separation**: All tables use `people` schema for organization
- **Environment Configuration**: Sensitive settings (DATABASE_URL, SECRET_KEY) managed via `.env`

## Configuration

### Environment Variables (.env)
```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/mydb
SECRET_KEY="your-super-secret-key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Docker Setup
- PostgreSQL runs on port 5433 (host) → 5432 (container)
- Application runs on port 8000
- Database initialization scripts in `db/initdb/`
- Persistent data stored in `./postgresql/` directory

## Development Notes

### Database Models
- All models extend `Base` from `database.py`
- UUID primary keys with `uuid_generate_v4()` server defaults
- Timezone-aware timestamps using PostgreSQL `TIMESTAMP(timezone=True)`
- Foreign key relationships properly defined with schema prefixes

### Security Implementation
- Password hashing with bcrypt via `passlib`
- JWT tokens with configurable expiration
- Session-based logout tracking (tokens can be invalidated server-side)
- OTP verification system for enhanced security

### Code Organization
- **Separation of Concerns**: Database operations in `crud.py`, business logic in `service/`, API routes in `routers/`
- **Dependency Injection**: Database sessions and authentication dependencies properly implemented
- **Schema Validation**: Pydantic models ensure request/response type safety