from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, Project, Task
from app.auth import get_current_user_optional

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def get_admin_or_redirect(request, db):
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/auth/login"})
    if user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_admin_or_redirect(request, db)
    users = db.query(User).all()
    projects = db.query(Project).all()
    tasks = db.query(Task).all()
    stats = {
        "total_users": len(users),
        "admins": sum(1 for u in users if u.role.value == "admin"),
        "members": sum(1 for u in users if u.role.value == "member"),
        "total_projects": len(projects),
        "total_tasks": len(tasks),
    }
    return templates.TemplateResponse(
        "admin/index.html",
        {"request": request, "user": user, "users": users, "stats": stats},
    )


@router.post("/users/{user_id}/role")
def change_role(
    user_id: int,
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = get_admin_or_redirect(request, db)
    target = db.query(User).filter_by(id=user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    target.role = UserRole.admin if role == "admin" else UserRole.member
    db.commit()
    return RedirectResponse("/admin/", status_code=302)


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_or_redirect(request, db)
    target = db.query(User).filter_by(id=user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    target.is_active = not target.is_active
    db.commit()
    return RedirectResponse("/admin/", status_code=302)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_or_redirect(request, db)
    target = db.query(User).filter_by(id=user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(target)
    db.commit()
    return RedirectResponse("/admin/", status_code=302)
