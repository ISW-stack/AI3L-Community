from fastapi import APIRouter

from app.api.v1.endpoints import (
    about,
    admin,
    applications,
    auth,
    categories,
    comments,
    files,
    forms,
    health,
    notifications,
    posts,
    public,
    reports,
    sigs,
    tasks,
    users,
    ws,
)

api_v1_router = APIRouter()

api_v1_router.include_router(about.router)
api_v1_router.include_router(public.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(applications.router)
api_v1_router.include_router(categories.router)
api_v1_router.include_router(posts.router)
api_v1_router.include_router(comments.router)
api_v1_router.include_router(files.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(sigs.router)
api_v1_router.include_router(forms.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(tasks.router)
api_v1_router.include_router(ws.router)
