from fastapi import APIRouter

from app.api.v1.endpoints import health

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)

# Future routers (Phase 1+):
# from app.api.v1.endpoints import auth, users, posts, comments, forms
# api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
# api_v1_router.include_router(posts.router, prefix="/posts", tags=["posts"])
# api_v1_router.include_router(comments.router, prefix="/comments", tags=["comments"])
# api_v1_router.include_router(forms.router, prefix="/forms", tags=["forms"])
