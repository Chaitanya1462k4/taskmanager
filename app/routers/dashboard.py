from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from app.database import get_db
from app.models import Task, Project, ProjectMember, TaskStatus, User
from app.auth import get_current_user_optional

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/auth/login", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    now = datetime.now(timezone.utc)

    # Projects accessible to this user
    if user.role.value == "admin":
        projects = db.query(Project).all()
        all_tasks = db.query(Task).all()
    else:
        member_project_ids = [m.project_id for m in db.query(ProjectMember).filter_by(user_id=user.id).all()]
        projects = db.query(Project).filter(Project.id.in_(member_project_ids)).all()
        all_tasks = db.query(Task).filter(Task.project_id.in_(member_project_ids)).all()

    # Auto-mark overdue tasks
    for task in all_tasks:
        if task.due_date and task.status.value not in ("done",):
            due = task.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < now and task.status.value != "overdue":
                task.status = TaskStatus.overdue
    db.commit()

    my_tasks = db.query(Task).filter(Task.assigned_to == user.id).all()

    stats = {
        "total_projects": len(projects),
        "total_tasks": len(all_tasks),
        "todo": sum(1 for t in all_tasks if t.status.value == "todo"),
        "in_progress": sum(1 for t in all_tasks if t.status.value == "in_progress"),
        "done": sum(1 for t in all_tasks if t.status.value == "done"),
        "overdue": sum(1 for t in all_tasks if t.status.value == "overdue"),
        "my_tasks": len(my_tasks),
    }

    recent_tasks = sorted(all_tasks, key=lambda t: t.created_at, reverse=True)[:8]

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "projects": projects[:5],
            "recent_tasks": recent_tasks,
        },
    )
