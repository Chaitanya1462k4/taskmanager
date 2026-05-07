from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.database import engine, Base
from app.routers import auth, dashboard, projects, tasks, admin
import app.models  # ensure models are registered

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Team Task Manager", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register routers
app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(admin.router)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(
        "errors/403.html", {"request": request}, status_code=403
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(
        "errors/404.html", {"request": request}, status_code=404
    )
