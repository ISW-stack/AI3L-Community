from fastapi import APIRouter

from app.api.v1.endpoints import (
    about,
    admin,
    albums,
    applications,
    auth,
    categories,
    citations,
    co_authors,
    comments,
    dm,
    export,
    files,
    forms,
    health,
    notifications,
    posts,
    preferences,
    public,
    qa,
    recommendations,
    reports,
    sigs,
    social,
    tasks,
    users,
    ws,
)

api_v1_router = APIRouter()

api_v1_router.include_router(about.router)
api_v1_router.include_router(public.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(export.router)
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(preferences.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(applications.router)
api_v1_router.include_router(categories.router)
api_v1_router.include_router(posts.router)
api_v1_router.include_router(comments.router)
api_v1_router.include_router(files.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(sigs.router)
api_v1_router.include_router(forms.router)
api_v1_router.include_router(albums.router)
api_v1_router.include_router(social.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(qa.router)
api_v1_router.include_router(co_authors.router)
api_v1_router.include_router(citations.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(tasks.router)
api_v1_router.include_router(dm.router)
api_v1_router.include_router(ws.router)
