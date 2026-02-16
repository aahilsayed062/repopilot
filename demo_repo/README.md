# TaskFlow API

A lightweight task management REST API built with FastAPI and SQLAlchemy.

## Features
- User authentication with JWT tokens
- CRUD operations for tasks and projects
- Role-based access control
- SQLite database with SQLAlchemy ORM
- Input validation with Pydantic

## Quick Start
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## API Endpoints
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get JWT token
- `GET /tasks` - List tasks (requires auth)
- `POST /tasks` - Create task (requires auth)
- `PUT /tasks/{id}` - Update task (requires auth)
- `DELETE /tasks/{id}` - Delete task (requires auth)
