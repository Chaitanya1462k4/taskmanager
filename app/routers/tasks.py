from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import get_db
from app.models import Task, TaskStatus, TaskPriority, Project, ProjectMember, User
from app.auth import get_current_user_optional
from typing import Optional

router = APIRouter(prefix="/tasks", tags=["tasks"])
templates = Jinja2Templates(directory="app/templates")


def get_user_or_redirect(request, db):
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/auth/login"})
    return user


def can_access_project(user: User, project_id: int, db: Session) -> bool:
    if user.role.value == "admin":
        return True
    project = db.query(Project).filter_by(id=project_id).first()
    if project and project.owner_id == user.id:
        return True
    return db.query(ProjectMember).filter_by(project_id=project_id, user_id=user.id).first() is not None


def can_edit_task(user: User, task: Task, db: Session) -> bool:
    if user.role.value == "admin":
        return True
    if task.created_by == user.id or task.assigned_to == user.id:
        return True
    membership = db.query(ProjectMember).filter_by(project_id=task.project_id, user_id=user.id).first()
    return membership and membership.role.value == "admin"


@router.get("/", response_class=HTMLResponse)
def list_tasks(
    request: Request,
    status: str = None,
    priority: str = None,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    query = db.query(Task)

    if user.role.value != "admin":
        ids = [m.project_id for m in db.query(ProjectMember).filter_by(user_id=user.id)]
        owned = [p.id for p in db.query(Project).filter_by(owner_id=user.id)]
        query = query.filter(Task.project_id.in_(list(set(ids + owned))))

    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if project_id:
        query = query.filter(Task.project_id == project_id)

    tasks = query.order_by(Task.created_at.desc()).all()
    projects = db.query(Project).all() if user.role.value == "admin" else \
        db.query(Project).filter(Project.id.in_([t.project_id for t in tasks])).all()

    return templates.TemplateResponse(
        "tasks/list.html",
        {
            "request": request,
            "user": user,
            "tasks": tasks,
            "projects": projects,
            "filter_status": status,
            "filter_priority": priority,
            "filter_project": project_id,
            "statuses": [s.value for s in TaskStatus],
            "priorities": [p.value for p in TaskPriority],
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_task_page(request: Request, project_id: int = None, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    if user.role.value == "admin":
        projects = db.query(Project).all()
    else:
        ids = [m.project_id for m in db.query(ProjectMember).filter_by(user_id=user.id)]
        owned = [p.id for p in db.query(Project).filter_by(owner_id=user.id)]
        projects = db.query(Project).filter(Project.id.in_(list(set(ids + owned)))).all()

    all_users = db.query(User).filter(User.is_active == True).all()
    return templates.TemplateResponse(
        "tasks/new.html",
        {
            "request": request,
            "user": user,
            "projects": projects,
            "all_users": all_users,
            "selected_project": project_id,
            "priorities": [p.value for p in TaskPriority],
        },
    )


@router.post("/new")
def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    project_id: int = Form(...),
    assigned_to: int = Form(None),
    priority: str = Form("medium"),
    due_date: str = Form(None),
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    if not can_access_project(user, project_id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    due = None
    if due_date:
        try:
            due = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    task = Task(
        title=title.strip(),
        description=description.strip(),
        project_id=project_id,
        assigned_to=assigned_to if assigned_to else None,
        priority=priority,
        due_date=due,
        created_by=user.id,
        status=TaskStatus.todo,
    )
    db.add(task)
    db.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=302)


@router.get("/{task_id}", response_class=HTMLResponse)
def task_detail(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    task = db.query(Task).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not can_access_project(user, task.project_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    all_users = db.query(User).filter(User.is_active == True).all()
    return templates.TemplateResponse(
        "tasks/detail.html",
        {
            "request": request,
            "user": user,
            "task": task,
            "can_edit": can_edit_task(user, task, db),
            "all_users": all_users,
            "statuses": [s.value for s in TaskStatus],
            "priorities": [p.value for p in TaskPriority],
        },
    )


@router.post("/{task_id}/status")
def update_status(
    task_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    task = db.query(Task).filter_by(id=task_id).first()
    if not task or not can_access_project(user, task.project_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    task.status = status
    db.commit()
    return RedirectResponse(f"/tasks/{task_id}", status_code=302)


@router.post("/{task_id}/edit")
def edit_task(
    task_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    assigned_to: int = Form(None),
    priority: str = Form("medium"),
    due_date: str = Form(None),
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    task = db.query(Task).filter_by(id=task_id).first()
    if not task or not can_edit_task(user, task, db):
        raise HTTPException(status_code=403, detail="Access denied")

    due = None
    if due_date:
        try:
            due = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    task.title = title.strip()
    task.description = description.strip()
    task.assigned_to = assigned_to if assigned_to else None
    task.priority = priority
    task.due_date = due
    db.commit()
    return RedirectResponse(f"/tasks/{task_id}", status_code=302)


@router.post("/{task_id}/delete")
def delete_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    task = db.query(Task).filter_by(id=task_id).first()
    if not task or not can_edit_task(user, task, db):
        raise HTTPException(status_code=403, detail="Access denied")
    project_id = task.project_id
    db.delete(task)
    db.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=302)
