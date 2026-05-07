# TaskFlow — Team Task Manager

A full-stack web app for project and task management with role-based access control.

## Features

- **Authentication** — Signup, login, JWT via secure cookie
- **Role-based access** — Global Admin / Member roles + per-project admin/member roles
- **Projects** — Create, edit, delete; invite/remove team members
- **Tasks** — Full CRUD, priority levels, due dates, assignees, status tracking
- **Dashboard** — Stats overview, recent tasks, progress bars, overdue auto-detection
- **Admin panel** — Manage all users, change roles, activate/deactivate accounts

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI |
| ORM | SQLAlchemy + Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Templates | Jinja2 + Bootstrap 5 |
| Dev DB | SQLite |
| Prod DB | PostgreSQL (Railway) |
| Deploy | Railway |

## Local Setup

### 1. Clone and enter the project
```bash
git clone <your-repo-url>
cd taskmanager
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env — set a strong SECRET_KEY
```

### 5. Run the app
```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 — the first user you register becomes **Admin**.

## Deployment on Railway

1. Push your repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add a **PostgreSQL** plugin from the Railway dashboard
4. In your service's Variables tab, add:
   ```
   SECRET_KEY=<generate a strong random key>
   DATABASE_URL=<Railway auto-fills this from the PostgreSQL plugin>
   ```
5. Railway auto-deploys on every push

## Project Structure

```
taskmanager/
├── app/
│   ├── main.py           # FastAPI app, routes registered
│   ├── config.py         # Settings via pydantic
│   ├── database.py       # SQLAlchemy engine + session
│   ├── models.py         # User, Project, Task, ProjectMember
│   ├── auth.py           # JWT + password utils + dependencies
│   ├── routers/
│   │   ├── auth.py       # /auth/register, /auth/login, /auth/logout
│   │   ├── dashboard.py  # /dashboard
│   │   ├── projects.py   # /projects CRUD + members
│   │   ├── tasks.py      # /tasks CRUD + status
│   │   └── admin.py      # /admin user management
│   ├── templates/        # Jinja2 HTML templates
│   └── static/           # CSS / JS assets
├── requirements.txt
├── Procfile
└── railway.json
```

## RBAC Rules

| Action | Admin | Project Admin | Member | Non-member |
|---|---|---|---|---|
| View any project | ✅ | ✅ | ✅ | ❌ |
| Create project | ✅ | ✅ | ✅ | ✅ |
| Edit/delete project | ✅ | ✅ | ❌ | ❌ |
| Add/remove members | ✅ | ✅ | ❌ | ❌ |
| Create task | ✅ | ✅ | ✅ | ❌ |
| Edit/delete task | ✅ | ✅ | Creator/Assignee | ❌ |
| Manage users | ✅ | ❌ | ❌ | ❌ |
