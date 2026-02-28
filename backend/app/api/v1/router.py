from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, users

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)

# Future routers (Phase 1+):
# from app.api.v1.endpoints import posts, comments, forms
# api_v1_router.include_router(posts.router)
# api_v1_router.include_router(comments.router)
# api_v1_router.include_router(forms.router)
