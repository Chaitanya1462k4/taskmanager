from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, ProjectMember, ProjectMemberRole, User, Task
from app.auth import get_current_user_optional

router = APIRouter(prefix="/projects", tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


def get_user_or_redirect(request, db):
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/auth/login"})
    return user


def can_manage_project(user: User, project: Project, db: Session) -> bool:
    if user.role.value == "admin":
        return True
    if project.owner_id == user.id:
        return True
    membership = db.query(ProjectMember).filter_by(project_id=project.id, user_id=user.id).first()
    return membership and membership.role.value == "admin"


def get_accessible_project(project_id: int, user: User, db: Session) -> Project:
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role.value == "admin":
        return project
    member = db.query(ProjectMember).filter_by(project_id=project_id, user_id=user.id).first()
    if not member and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


@router.get("/", response_class=HTMLResponse)
def list_projects(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    if user.role.value == "admin":
        projects = db.query(Project).all()
    else:
        ids = [m.project_id for m in db.query(ProjectMember).filter_by(user_id=user.id)]
        owned = [p.id for p in db.query(Project).filter_by(owner_id=user.id)]
        all_ids = list(set(ids + owned))
        projects = db.query(Project).filter(Project.id.in_(all_ids)).all()

    return templates.TemplateResponse(
        "projects/list.html", {"request": request, "user": user, "projects": projects}
    )


@router.get("/new", response_class=HTMLResponse)
def new_project_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    return templates.TemplateResponse("projects/new.html", {"request": request, "user": user})


@router.post("/new")
def create_project(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    if not title.strip():
        return templates.TemplateResponse(
            "projects/new.html",
            {"request": request, "user": user, "error": "Title is required"},
        )
    project = Project(title=title.strip(), description=description.strip(), owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    # Auto-add creator as admin member
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectMemberRole.admin))
    db.commit()
    return RedirectResponse(f"/projects/{project.id}", status_code=302)


@router.get("/{project_id}", response_class=HTMLResponse)
def project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    project = get_accessible_project(project_id, user, db)
    tasks = db.query(Task).filter_by(project_id=project_id).all()
    members = db.query(ProjectMember).filter_by(project_id=project_id).all()
    all_users = db.query(User).filter(User.is_active == True).all()
    member_ids = {m.user_id for m in members}
    non_members = [u for u in all_users if u.id not in member_ids]
    can_manage = can_manage_project(user, project, db)

    return templates.TemplateResponse(
        "projects/detail.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "tasks": tasks,
            "members": members,
            "non_members": non_members,
            "can_manage": can_manage,
        },
    )


@router.get("/{project_id}/edit", response_class=HTMLResponse)
def edit_project_page(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    project = get_accessible_project(project_id, user, db)
    if not can_manage_project(user, project, db):
        raise HTTPException(status_code=403, detail="Not allowed")
    return templates.TemplateResponse(
        "projects/edit.html", {"request": request, "user": user, "project": project}
    )


@router.post("/{project_id}/edit")
def edit_project(
    project_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    project = get_accessible_project(project_id, user, db)
    if not can_manage_project(user, project, db):
        raise HTTPException(status_code=403, detail="Not allowed")
    project.title = title.strip()
    project.description = description.strip()
    db.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=302)


@router.post("/{project_id}/delete")
def delete_project(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_redirect(request, db)
    project = get_accessible_project(project_id, user, db)
    if not can_manage_project(user, project, db):
        raise HTTPException(status_code=403, detail="Not allowed")
    db.delete(project)
    db.commit()
    return RedirectResponse("/projects/", status_code=302)


@router.post("/{project_id}/members/add")
def add_member(
    project_id: int,
    request: Request,
    user_id: int = Form(...),
    role: str = Form("member"),
    db: Session = Depends(get_db),
):
    print(f"DEBUG: project_id={project_id}, user_id={user_id}, role={role}")
    user = get_user_or_redirect(request, db)
    project = get_accessible_project(project_id, user, db)
    if not can_manage_project(user, project, db):
        raise HTTPException(status_code=403, detail="Not allowed")
    existing = db.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).first()
    if not existing:
        role_enum = ProjectMemberRole.admin if role == "admin" else ProjectMemberRole.member
        db.add(ProjectMember(project_id=project_id, user_id=user_id, role=role_enum))
        db.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=302)


@router.post("/{project_id}/members/{member_id}/remove")
def remove_member(
    project_id: int,
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_user_or_redirect(request, db)
    project = get_accessible_project(project_id, user, db)
    if not can_manage_project(user, project, db):
        raise HTTPException(status_code=403, detail="Not allowed")
    member = db.query(ProjectMember).filter_by(id=member_id, project_id=project_id).first()
    if member:
        db.delete(member)
        db.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=302)
